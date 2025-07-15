"""
Query handlers for Family Tree Analyser v2.
Contains implementations for various analysis and search queries.
"""

from typing import List, Optional
from gedcom_db import GedcomDB, Individual


class SearchQueryHandler:
    """Handles search-related queries."""
    
    def __init__(self, database: GedcomDB):
        self.database = database
        self.ancestor_filter_ids: Optional[set] = None
    
    def set_ancestor_filter(self, ancestor_filter_ids: Optional[set]):
        """Set the ancestor filter for search operations."""
        self.ancestor_filter_ids = ancestor_filter_ids
    
    def find_individual_by_name(self):
        """Interactive search for individuals by name with filtering options."""
        print("\n--- Find Individual by Name ---")
        
        # Get search name
        name = input("Enter name to search for: ").strip()
        if not name:
            print("No name entered.")
            return
        
        # Get search type
        print("\nSearch type:")
        print("1. Exact match (case insensitive)")
        print("2. Pattern match (wildcards)")
        search_type = input("Choose search type (1-2, default 2): ").strip()
        exact_match = (search_type == '1')
        
        # Get birth year constraints
        print("\nBirth year constraints (press Enter to skip):")
        min_birth_str = input("Earliest birth year: ").strip()
        max_birth_str = input("Latest birth year: ").strip()
        
        min_birth_year = None
        max_birth_year = None
        try:
            if min_birth_str:
                min_birth_year = int(min_birth_str)
            if max_birth_str:
                max_birth_year = int(max_birth_str)
        except ValueError:
            print("Invalid year format. Ignoring year constraints.")
            min_birth_year = max_birth_year = None
        
        # Get death year constraints
        print("\nDeath year constraints (press Enter to skip):")
        min_death_str = input("Earliest death year: ").strip()
        max_death_str = input("Latest death year: ").strip()
        
        min_death_year = None
        max_death_year = None
        try:
            if min_death_str:
                min_death_year = int(min_death_str)
            if max_death_str:
                max_death_year = int(max_death_str)
        except ValueError:
            print("Invalid year format. Ignoring death year constraints.")
            min_death_year = max_death_year = None
        
        # Perform search
        if hasattr(self.database, 'search_individuals_advanced'):
            results = self.database.search_individuals_advanced(
                name=name,
                exact_match=exact_match,
                min_birth_year=min_birth_year,
                max_birth_year=max_birth_year,
                min_death_year=min_death_year,
                max_death_year=max_birth_year,
                ancestor_filter_ids=self.ancestor_filter_ids
            )
        else:
            print("Advanced search not supported by this database.")
            return
        
        if not results:
            print(f"\nNo individuals found matching '{name}'.")
            return
        
        # Get sort order
        print(f"\nFound {len(results)} individual(s). Sort order:")
        print("1. Birth year ascending (oldest first)")
        print("2. Birth year descending (youngest first)") 
        print("3. Name ascending")
        print("4. Name descending")
        sort_choice = input("Choose sort order (1-4, default 1): ").strip()
        
        # Sort results
        if sort_choice == '2':
            results.sort(key=lambda x: x.birth_year or 0, reverse=True)
        elif sort_choice == '3':
            results.sort(key=lambda x: x.name.lower())
        elif sort_choice == '4':
            results.sort(key=lambda x: x.name.lower(), reverse=True)
        else:  # Default to birth year ascending
            results.sort(key=lambda x: x.birth_year or 0)
        
        # Display results
        print(f"\n--- Search Results for '{name}' ---")
        print(f"Search type: {'Exact match' if exact_match else 'Pattern match'}")
        
        constraints = []
        if min_birth_year:
            constraints.append(f"birth >= {min_birth_year}")
        if max_birth_year:
            constraints.append(f"birth <= {max_birth_year}")
        if min_death_year:
            constraints.append(f"death >= {min_death_year}")
        if max_death_year:
            constraints.append(f"death <= {max_death_year}")
        
        if constraints:
            print(f"Constraints: {', '.join(constraints)}")
        
        print()
        
        for i, individual in enumerate(results, 1):
            birth_year = individual.birth_year or "Unknown"
            death_year = individual.death_year or "Living"
            age = individual.calculate_age()
            age_str = f"{age}" if age is not None else "Unknown"
            
            print(f"{i:3}. {individual.name}")
            print(f"     Birth: {birth_year} | Death: {death_year} | Age: {age_str}")
            print(f"     ID: {individual.xref_id}")
            print()
        
        print(f"Total: {len(results)} individual(s) found.")
        
        # Use reusable selection method
        selected_person = self._prompt_person_selection(results, "view details")
        if selected_person:
            self._display_individual_details(selected_person)
    
    def _display_individual_details(self, individual: Individual):
        """Display detailed information about an individual."""
        print(f"\n{'='*60}")
        print(f"DETAILED INFORMATION FOR: {individual.name}")
        print(f"{'='*60}")
        
        print(f"Record ID: {individual.xref_id}")
        
        # Basic information
        print(f"\nBASIC INFORMATION:")
        print(f"  Full Name: {individual.name}")
        
        # Birth information with more detail
        birth_date = individual.birth_date
        if birth_date:
            print(f"  Birth Date: {birth_date.strftime('%B %d, %Y')}")
        elif individual.birth_year:
            print(f"  Birth Year: {individual.birth_year}")
        else:
            print(f"  Birth: Unknown")
        
        # Birth place
        if hasattr(individual, 'birth_place') and individual.birth_place:
            print(f"  Birth Place: {individual.birth_place}")
        
        # Death information with more detail
        death_date = individual.death_date
        if death_date:
            print(f"  Death Date: {death_date.strftime('%B %d, %Y')}")
        elif individual.death_year:
            print(f"  Death Year: {individual.death_year}")
        else:
            print(f"  Status: Living or Unknown")
        
        # Age calculation with context
        age = individual.calculate_age()
        if age is not None:
            if individual.death_date or individual.death_year:
                print(f"  Age at Death: {age} years")
            else:
                print(f"  Current Age: {age} years (if still living)")
        
        # Look for additional meaningful information in the raw record
        additional_info_found = False
        if hasattr(individual, 'raw_record') and individual.raw_record:
            for sub in individual.raw_record.sub_records:
                if sub.tag == 'OCCU':
                    if not additional_info_found:
                        print(f"\nADDITIONAL INFORMATION:")
                        additional_info_found = True
                    print(f"  Occupation: {sub.value}")
                elif sub.tag == 'RESI':
                    # Residence information
                    for sub2 in sub.sub_records:
                        if sub2.tag == 'PLAC':
                            if not additional_info_found:
                                print(f"\nADDITIONAL INFORMATION:")
                                additional_info_found = True
                            print(f"  Residence: {sub2.value}")
                elif sub.tag == 'BURI':
                    # Burial information
                    for sub2 in sub.sub_records:
                        if sub2.tag == 'PLAC':
                            if not additional_info_found:
                                print(f"\nADDITIONAL INFORMATION:")
                                additional_info_found = True
                            print(f"  Burial Place: {sub2.value}")
                elif sub.tag == 'NOTE':
                    if not additional_info_found:
                        print(f"\nADDITIONAL INFORMATION:")
                        additional_info_found = True
                    # Truncate long notes
                    note_text = str(sub.value)
                    if len(note_text) > 100:
                        note_text = note_text[:100] + "..."
                    print(f"  Note: {note_text}")
        
        # Try to resolve family connections to actual names
        if hasattr(individual, 'raw_record') and individual.raw_record:
            # Get spouses by looking through families where this person is a spouse
            spouses = []
            families = []
            
            for sub in individual.raw_record.sub_records:
                if sub.tag == 'FAMC':  # Family as child
                    families.append(('child', str(sub.value)))
                elif sub.tag == 'FAMS':  # Family as spouse
                    families.append(('spouse', str(sub.value)))
                    # Find spouse in this family
                    spouse = self._find_spouse_in_family(str(sub.value), individual.xref_id)
                    if spouse:
                        spouses.append(spouse)
            
            # Display spouses using reusable method
            if spouses:
                self._display_person_list_with_selection(
                    people=spouses,
                    title="Spouses", 
                    action_name="view details",
                    action_callback=self._display_spouse_summary,
                    show_birth_death=True
                )
            
            # Display families with ordinals
            if families:
                print(f"\nFAMILIES:")
                for i, (role, family_id) in enumerate(families, 1):
                    family_members = self._get_family_members(family_id)
                    if family_members:
                        role_desc = "Child in family" if role == 'child' else "Spouse in family"
                        print(f"  {i}. {role_desc} (ID: {family_id})")
                        
                        # Show brief family overview
                        if family_members['father']:
                            print(f"     Father: {family_members['father'].name}")
                        if family_members['mother']:
                            print(f"     Mother: {family_members['mother'].name}")
                        if family_members['children']:
                            print(f"     Children: {len(family_members['children'])} child(ren)")
                
                # Prompt to view family details
                if len(families) == 1:
                    choice = input(f"\nView family details? (y/n): ").strip().lower()
                    if choice in ['y', 'yes']:
                        self._display_family_details(families[0][1])
                else:
                    choice = input(f"\nView details for which family? (1-{len(families)}, or Enter to skip): ").strip()
                    if choice:
                        try:
                            index = int(choice) - 1
                            if 0 <= index < len(families):
                                self._display_family_details(families[index][1])
                        except ValueError:
                            pass
        
        print(f"\n{'='*60}")
        print("This detailed view shows all available information for this individual.")
        print("For family relationships, use the family analysis options in the main menu.")
        input("\nPress Enter to continue...")
    
    def _display_spouse_summary(self, spouse: Individual):
        """Display summary information about a spouse without full navigation."""
        print(f"\n{'='*40}")
        print(f"SPOUSE DETAILS: {spouse.name}")
        print(f"{'='*40}")
        
        print(f"Record ID: {spouse.xref_id}")
        
        # Basic information
        print(f"\nBASIC INFORMATION:")
        print(f"  Full Name: {spouse.name}")
        
        # Birth information
        birth_date = spouse.birth_date
        if birth_date:
            print(f"  Birth Date: {birth_date.strftime('%B %d, %Y')}")
        elif spouse.birth_year:
            print(f"  Birth Year: {spouse.birth_year}")
        else:
            print(f"  Birth: Unknown")
        
        # Birth place
        if hasattr(spouse, 'birth_place') and spouse.birth_place:
            print(f"  Birth Place: {spouse.birth_place}")
        
        # Death information
        death_date = spouse.death_date
        if death_date:
            print(f"  Death Date: {death_date.strftime('%B %d, %Y')}")
        elif spouse.death_year:
            print(f"  Death Year: {spouse.death_year}")
        else:
            print(f"  Status: Living or Unknown")
        
        # Age calculation
        age = spouse.calculate_age()
        if age is not None:
            if spouse.death_date or spouse.death_year:
                print(f"  Age at Death: {age} years")
            else:
                print(f"  Current Age: {age} years (if still living)")
        
        # Look for additional information
        if hasattr(spouse, 'raw_record') and spouse.raw_record:
            additional_info = []
            for sub in spouse.raw_record.sub_records:
                if sub.tag == 'OCCU':
                    additional_info.append(f"Occupation: {sub.value}")
                elif sub.tag == 'RESI':
                    for sub2 in sub.sub_records:
                        if sub2.tag == 'PLAC':
                            additional_info.append(f"Residence: {sub2.value}")
                elif sub.tag == 'BURI':
                    for sub2 in sub.sub_records:
                        if sub2.tag == 'PLAC':
                            additional_info.append(f"Burial Place: {sub2.value}")
            
            if additional_info:
                print(f"\nADDITIONAL INFORMATION:")
                for info in additional_info:
                    print(f"  {info}")
        
        print(f"\n{'='*40}")
        
        # Option to view full details
        choice = input("View full details with family navigation? (y/n): ").strip().lower()
        if choice in ['y', 'yes']:
            self._display_individual_details(spouse)
        else:
            input("Press Enter to continue...")
    
    def _find_spouse_in_family(self, family_id: str, individual_id: str) -> Optional[Individual]:
        """Find the spouse of the given individual in the specified family."""
        try:
            # Get all individuals and find the family
            all_individuals = self.database.get_all_individuals()
            
            # Find all spouses in this family (excluding the current individual)
            spouses = []
            for person in all_individuals:
                if hasattr(person, 'raw_record') and person.raw_record:
                    for sub in person.raw_record.sub_records:
                        if sub.tag == 'FAMS' and str(sub.value) == family_id and person.xref_id != individual_id:
                            spouses.append(person)
            
            return spouses[0] if spouses else None
        except:
            return None
    
    def _get_family_members(self, family_id: str) -> dict:
        """Get all members of a family (father, mother, children)."""
        try:
            all_individuals = self.database.get_all_individuals()
            
            family_members = {
                'father': None,
                'mother': None,
                'children': []
            }
            
            # Find all family members
            spouses = []
            children = []
            
            for person in all_individuals:
                if hasattr(person, 'raw_record') and person.raw_record:
                    for sub in person.raw_record.sub_records:
                        if sub.tag == 'FAMS' and str(sub.value) == family_id:
                            # This person is a spouse in this family
                            spouses.append(person)
                        elif sub.tag == 'FAMC' and str(sub.value) == family_id:
                            # This person is a child in this family
                            children.append(person)
            
            # Assign spouses as father/mother (simplified - could be improved with gender info)
            if len(spouses) >= 1:
                family_members['father'] = spouses[0]
            if len(spouses) >= 2:
                family_members['mother'] = spouses[1]
            
            family_members['children'] = children
            
            return family_members
        except:
            return {'father': None, 'mother': None, 'children': []}
    
    def _display_family_details(self, family_id: str):
        """Display detailed information about a family."""
        print(f"\n{'='*60}")
        print(f"FAMILY DETAILS - ID: {family_id}")
        print(f"{'='*60}")
        
        family_members = self._get_family_members(family_id)
        all_members = []
        
        # Collect all family members for unified display
        if family_members['father']:
            all_members.append(('Parent/Spouse', family_members['father']))
        if family_members['mother']:
            all_members.append(('Parent/Spouse', family_members['mother']))
        for child in family_members['children']:
            all_members.append(('Child', child))
        
        if not all_members:
            print("  No family members found for this family.")
            print(f"\n{'='*60}")
            input("Press Enter to continue...")
            return
        
        # Display family members using reusable method
        people_list = [member[1] for member in all_members]
        self._display_person_list_with_selection(
            people=people_list,
            title="Family Members",
            action_name="view details",
            action_callback=self._display_individual_details,
            show_birth_death=True
        )
        
        print(f"\n{'='*60}")
        input("Press Enter to continue...")
    
    def _display_person_list(self, people: List[Individual], title: str = "People", 
                           show_details: bool = True, show_birth_death: bool = True) -> None:
        """Display a numbered list of people with consistent formatting."""
        if not people:
            print(f"No {title.lower()} found.")
            return
        
        print(f"\n{title.upper()}:")
        for i, person in enumerate(people, 1):
            print(f"  {i}. {person.name}", end="")
            
            if show_birth_death:
                birth_year = person.birth_year or "Unknown"
                death_year = person.death_year or "Living"
                age = person.calculate_age()
                age_str = f" | Age: {age}" if age is not None else ""
                print(f"\n     Birth: {birth_year} | Death: {death_year}{age_str}")
            else:
                age = person.calculate_age()
                if age is not None:
                    print(f" (Age: {age})")
                else:
                    print()
    
    def _prompt_person_selection(self, people: List[Individual], 
                               action_name: str = "view details",
                               single_prompt: str = None) -> Optional[Individual]:
        """Prompt user to select a person from a list and return the selected person."""
        if not people:
            return None
        
        if len(people) == 1:
            # Single person - use custom prompt or default
            if single_prompt is None:
                single_prompt = f"{action_name.capitalize()} for this person? (y/n): "
            
            choice = input(f"\n{single_prompt}").strip().lower()
            if choice in ['y', 'yes']:
                return people[0]
        else:
            # Multiple people - numbered selection
            choice = input(f"\n{action_name.capitalize()} for which person? (1-{len(people)}, or Enter to skip): ").strip()
            if choice:
                try:
                    index = int(choice) - 1
                    if 0 <= index < len(people):
                        return people[index]
                    else:
                        print(f"Invalid selection. Please choose 1-{len(people)}.")
                except ValueError:
                    print("Invalid input. Please enter a number.")
        
        return None
    
    def _display_person_list_with_selection(self, people: List[Individual], 
                                          title: str = "People",
                                          action_name: str = "view details",
                                          action_callback = None,
                                          show_birth_death: bool = True) -> None:
        """Display a list of people and handle user selection with callback."""
        if not people:
            return
        
        # Display the list
        self._display_person_list(people, title, show_birth_death=show_birth_death)
        
        # Handle selection
        selected_person = self._prompt_person_selection(people, action_name)
        if selected_person and action_callback:
            action_callback(selected_person)
    
    def display_people_with_selection(self, people: List[Individual], 
                                     title: str = "People",
                                     action_name: str = "view details",
                                     detailed_view: bool = True) -> None:
        """
        Public method for displaying a list of people with selection capability.
        This can be called by other parts of the application that need this functionality.
        
        Args:
            people: List of Individual objects to display
            title: Title for the list (e.g., "Search Results", "Ancestors", etc.)
            action_name: Action description (e.g., "view details", "select person")
            detailed_view: Whether to show full details or just basic info when selected
        """
        if detailed_view:
            callback = self._display_individual_details
        else:
            callback = self._display_spouse_summary
        
        self._display_person_list_with_selection(
            people=people,
            title=title,
            action_name=action_name,
            action_callback=callback,
            show_birth_death=True
        )
    
class ValidityQueryHandler:
    """Handles data validity and quality checks."""
    
    def __init__(self, database: GedcomDB):
        self.database = database
        self.ancestor_filter_ids: Optional[set] = None
    
    def set_ancestor_filter(self, ancestor_filter_ids: Optional[set]):
        """Set the ancestor filter for validity checks."""
        self.ancestor_filter_ids = ancestor_filter_ids
    
    def find_individuals_with_negative_ages(self):
        """Find individuals with negative calculated ages (death before birth)."""
        print("\n--- Validity Check: Individuals with Negative Ages ---")
        print("Searching for individuals where death date is before birth date...")
        
        all_individuals = self.database.get_all_individuals()
        negative_age_individuals = []
        
        for individual in all_individuals:
            age = individual.calculate_age()
            if age is not None and age < 0:
                negative_age_individuals.append(individual)
        
        if not negative_age_individuals:
            print("\n✅ No individuals found with negative ages.")
            print("All birth and death date combinations are valid.")
            input("\nPress Enter to continue...")
            return
        
        print(f"\n❌ Found {len(negative_age_individuals)} individual(s) with negative ages:")
        print("This indicates data quality issues where death dates are before birth dates.\n")
        
        # Display results with detailed information
        for individual in negative_age_individuals:
            age = individual.calculate_age()
            birth_info = "Unknown"
            death_info = "Unknown"
            
            # Get birth information
            if individual.birth_date:
                birth_info = individual.birth_date.strftime('%B %d, %Y')
            elif individual.birth_year:
                birth_info = str(individual.birth_year)
            
            # Get death information  
            if individual.death_date:
                death_info = individual.death_date.strftime('%B %d, %Y')
            elif individual.death_year:
                death_info = str(individual.death_year)
            
            # Calculate years and months for more precise display
            age_display = "Unknown"
            if age is not None:
                if individual.birth_date and individual.death_date:
                    # Calculate precise years and months
                    birth_date = individual.birth_date
                    death_date = individual.death_date
                    
                    years = death_date.year - birth_date.year
                    months = death_date.month - birth_date.month
                    
                    # Adjust for negative months
                    if months < 0:
                        years -= 1
                        months += 12
                    
                    # Adjust for day differences within the month
                    if death_date.day < birth_date.day:
                        months -= 1
                        if months < 0:
                            years -= 1
                            months += 12
                    
                    if years == 0:
                        age_display = f"{months} months"
                    elif months == 0:
                        age_display = f"{years} years"
                    else:
                        age_display = f"{years} years, {months} months"
                else:
                    # Fallback to simple year calculation
                    years = age
                    age_display = f"{years} years"
            
            print(f"• {individual.name}")
            print(f"  Birth: {birth_info} | Death: {death_info} | Age: {age_display}")
            print()
        
        print(f"Total: {len(negative_age_individuals)} individual(s) with data quality issues.")
        
        input("\nPress Enter to continue...")
    
    def find_orphaned_individuals(self):
        """Find individuals with no family connections (no FAMS or FAMC records)."""
        print("\n--- Validity Check: Orphaned Individuals ---")
        
        # Check if we're using an ancestor filter
        if self.ancestor_filter_ids is not None:
            print("❌ This check is not available when filtering by ancestors.")
            print("Please clear the ancestor filter first to run this validity check.")
            input("\nPress Enter to continue...")
            return
        
        print("Searching for individuals with no family connections...")
        
        all_individuals = self.database.get_all_individuals()
        orphaned_individuals = []
        
        for individual in all_individuals:
            has_family_connections = False
            
            if hasattr(individual, 'raw_record') and individual.raw_record:
                for sub in individual.raw_record.sub_records:
                    if sub.tag in ['FAMS', 'FAMC']:  # Family as spouse or child
                        has_family_connections = True
                        break
            
            if not has_family_connections:
                orphaned_individuals.append(individual)
        
        if not orphaned_individuals:
            print("\n✅ No orphaned individuals found.")
            print("All individuals have family connections.")
            input("\nPress Enter to continue...")
            return
        
        print(f"\n❌ Found {len(orphaned_individuals)} orphaned individual(s):")
        print("These individuals have no family connection records (FAMS/FAMC).\n")
        
        # Display results
        for individual in orphaned_individuals:
            birth_info = "Unknown"
            death_info = "Unknown"
            
            # Get birth information
            if individual.birth_date:
                birth_info = individual.birth_date.strftime('%B %d, %Y')
            elif individual.birth_year:
                birth_info = str(individual.birth_year)
            
            # Get death information  
            if individual.death_date:
                death_info = individual.death_date.strftime('%B %d, %Y')
            elif individual.death_year:
                death_info = str(individual.death_year)
            
            print(f"• {individual.name}")
            print(f"  Birth: {birth_info} | Death: {death_info}")
            print()
        
        print(f"Total: {len(orphaned_individuals)} orphaned individual(s).")
        
        input("\nPress Enter to continue...")

class ReportQueryHandler:
    """Handles analysis and reporting queries."""
    
    def __init__(self, database: GedcomDB):
        self.database = database
        self.ancestor_filter_ids: Optional[set] = None
        
        # Nation -> Counties mapping
        self.nation_counties = {
            'England': ['Cheshire', 'Shropshire/Salop', 'Lancashire', 'Yorkshire', 'Warwickshire', 'Kent', 'Devon/Dorset', 'Staffordshire'],
            'Wales': ['Flintshire', 'Denbighshire', 'Caernarvonshire'],
            'Scotland': [],  # Add Scottish counties as needed
            'Ireland': [],   # Add Irish counties as needed
            'Jamaica': [],   # Add Jamaican parishes/counties as needed
            'USA': [],       # Add US states/counties as needed
            'France': [],    # Add French departments/regions as needed
            'Australia': []  # Add Australian states/territories as needed
        }
        
        # Hierarchical County -> Local1 -> Local2 mapping
        self.county_places = {
            'Cheshire': {
                'Chester': {
                    'local2_places': [],
                    'known_streets': ['Castle Street', 'High Street']
                },
                'Tattenhall': {
                    'local2_places': [],
                    'known_streets': []
                },
                'Bunbury': {
                    'local2_places': [],
                    'known_streets': []
                },
                'Burwardsley': {
                    'local2_places': [],
                    'known_streets': []
                }
            },
            'Flintshire': {
                'Buckley': {
                    'local2_places': [],
                    'known_streets': []
                },
                'Holywell': {
                    'local2_places': [],
                    'known_streets': []
                },
                'Mold': {
                    'local2_places': ['Llanfferes'],
                    'known_streets': ['High Street']
                },
                'Broughton': {
                    'local2_places': [],
                    'known_streets': ['Warren Drive', 'High Street']
                }
            },
            'Denbighshire': {
                'Henllan': {
                    'local2_places': [],
                    'known_streets': []
                },
                'Ruthin': {
                    'local2_places': [],
                    'known_streets': []
                }
            },
            'Caernarvonshire': {
                'Bangor': {
                    'local2_places': [],
                    'known_streets': []
                }
            },
            'Shropshire/Salop': {
                'Market Drayton': {
                    'local2_places': ['Monkhopton'],
                    'known_streets': ['High Street', 'Shropshire Street']
                },
                'Shrewsbury': {
                    'local2_places': [],
                    'known_streets': []
                },
                'Drayton': {
                    'local2_places': [],
                    'known_streets': []
                },
                'Church Stretton': {
                    'local2_places': [],
                    'known_streets': []
                },
                'Broseley': {
                    'local2_places': [],
                    'known_streets': []
                },
                'Cheswardine': {
                    'local2_places': [],
                    'known_streets': []
                }
            },
            'Devon/Dorset': {
                'Dalwood': {
                    'local2_places': [],
                    'known_streets': []
                },
                'Stockland': {
                    'local2_places': [],
                    'known_streets': []
                },
                'Musbury': {
                    'local2_places': [],
                    'known_streets': []
                },
                'Axminster': {
                    'local2_places': [],
                    'known_streets': []
                },
                'Axmouth': {
                    'local2_places': [],
                    'known_streets': []
                },
                'Colyton': {
                    'local2_places': [],
                    'known_streets': []
                },
                'Culderwell': {
                    'local2_places': [],
                    'known_streets': []
                },
                'Kilmington': {
                    'local2_places': [],
                    'known_streets': []
                }
            }
            # Add more hierarchical mappings as needed
        }
        
        # Direct Nation -> Places mapping (for places without clear county associations)
        self.nation_places = {
            'Scotland': ['Glasgow', 'Edinburgh'],
            # Add more direct nation-place mappings as needed
        }
    
    def set_ancestor_filter(self, ancestor_filter_ids: Optional[set]):
        """Set the ancestor filter for analysis operations."""
        self.ancestor_filter_ids = ancestor_filter_ids
    
    def analyze_birth_places_summary(self):
        """Option 1: Analyze birth places - nations summary only."""
        print("\n--- Birth Place Analysis: Nations Summary ---")
        
        analysis_data = self._analyze_birth_places()
        self._display_nations_summary(analysis_data)
        
        input("\nPress Enter to continue...")
    
    def analyze_birth_places_detailed(self):
        """Option 2: Analyze birth places - detailed breakdown by nation, county, and place."""
        print("\n--- Birth Place Analysis: Detailed Breakdown ---")
        
        analysis_data = self._analyze_birth_places()
        self._display_detailed_breakdown(analysis_data)
        
        input("\nPress Enter to continue...")
    
    def _analyze_birth_places(self) -> dict:
        """
        Generic birth place analysis - returns structured data for flexible reporting.
        Used by multiple reporting options.
        """
        # Get individuals to analyze (filtered or all)
        if self.ancestor_filter_ids is not None:
            print(f"Analyzing birth places for {len(self.ancestor_filter_ids)} filtered individuals...")
            # Use indexes if available
            if hasattr(self.database, '_individual_index') and self.database._indexes_built:
                individuals = [self.database._individual_index[ind_id] 
                             for ind_id in self.ancestor_filter_ids 
                             if ind_id in self.database._individual_index]
            else:
                # Fallback to scanning all individuals
                all_individuals = self.database.get_all_individuals()
                individuals = [ind for ind in all_individuals if ind.xref_id in self.ancestor_filter_ids]
        else:
            print("Analyzing birth places for all individuals...")
            individuals = self.database.get_all_individuals()
        
        # Initialize counters for hierarchical structure
        nation_counts = {}
        county_counts = {}
        local1_counts = {}  # Main places (what we used to call "place")
        local2_counts = {}  # Villages/hamlets under main places
        unrecognized_places = set()
        unparseable_places = []  # Changed to list to store individual details
        blank_places = []  # Store individuals with blank birth places
        incomplete_places = {}  # Store birth places with incomplete classification and their individuals
        location_errors = []  # Track misplaced counties/places
        street_addresses = []  # Track but don't count street addresses (local3)
        blank_count = 0
        total_processed = 0
        
        # Process each individual
        for individual in individuals:
            total_processed += 1
            birth_place = None
            
            # Get birth place from individual
            if hasattr(individual, 'birth_place') and individual.birth_place:
                birth_place = individual.birth_place.strip()
            
            if not birth_place:
                blank_count += 1
                # Store individuals with blank birth places
                birth_year = getattr(individual, 'birth_year', None) or "Unknown"
                death_year = getattr(individual, 'death_year', None) or "Unknown"
                individual_name = getattr(individual, 'name', 'Unknown Name')
                
                blank_places.append({
                    'name': individual_name,
                    'birth_year': birth_year,
                    'death_year': death_year
                })
                continue
              # Parse the birth place using new hierarchical structure
            result = self._parse_birth_place(birth_place)
            
            # Check for location errors
            if result['location_errors']:
                location_errors.extend(result['location_errors'])
                # Don't count entries with location errors in the main counts
                continue
            
            # Track street addresses but don't count them
            if result['local3']:
                street_addresses.append({
                    'address': result['local3'],
                    'birth_place': birth_place,
                    'name': getattr(individual, 'name', 'Unknown Name'),
                    'birth_year': getattr(individual, 'birth_year', None) or "Unknown",
                    'death_year': getattr(individual, 'death_year', None) or "Unknown"
                })

            if result['nation']:
                # Successfully categorized (and no location errors)
                nation = result['nation']
                county = result['county']
                local1 = result['local1']  # Main place
                local2 = result['local2']  # Village/hamlet
                
                # Check if we have fully classified all parts of the birth place
                # Split the birth place and see if we've identified all meaningful parts
                place_parts = [part.strip() for part in birth_place.split(',') if part.strip()]
                if len(place_parts) == 1:
                    # No commas, try space splitting
                    space_parts = [part.strip() for part in birth_place.split() if part.strip()]
                    if len(space_parts) > 1:
                        place_parts = space_parts
                
                # Count how many parts we've identified - improved logic
                identified_parts = 0
                total_parts = len(place_parts)
                
                # Don't count street addresses (local3) as incomplete
                if result['local3']:
                    total_parts -= 1  # Subtract street address from parts to identify
                
                # Check what we've identified
                if nation:
                    identified_parts += 1
                if county:
                    identified_parts += 1  
                if local1:
                    identified_parts += 1
                if local2:
                    identified_parts += 1
                
                # More flexible incomplete detection:
                # - If we have 2+ parts but only identified nation, it's incomplete
                # - If we have 3+ parts but only identified nation+county, it's incomplete
                # - Always incomplete if we have unidentified parts in multi-part names
                is_incomplete = False
                
                if total_parts >= 2:
                    if identified_parts == 1 and nation:
                        # Only nation identified from 2+ parts
                        is_incomplete = True
                    elif total_parts >= 3 and identified_parts == 2:
                        # Only 2 parts identified from 3+ parts
                        is_incomplete = True
                    elif identified_parts < total_parts:
                        # General case: fewer identified than total parts
                        is_incomplete = True
                
                if is_incomplete:
                    birth_year = getattr(individual, 'birth_year', None) or "Unknown"
                    death_year = getattr(individual, 'death_year', None) or "Unknown"
                    individual_name = getattr(individual, 'name', 'Unknown Name')
                    
                    if birth_place not in incomplete_places:
                        incomplete_places[birth_place] = []
                    incomplete_places[birth_place].append({
                        'name': individual_name,
                        'birth_year': birth_year,
                        'death_year': death_year
                    })
                
                # Count nation
                nation_counts[nation] = nation_counts.get(nation, 0) + 1
                
                # Count county if identified
                if county:
                    county_key = f"{county}, {nation}"
                    county_counts[county_key] = county_counts.get(county_key, 0) + 1
                
                # Count local1 (main place) if identified
                if local1:
                    local1_key = f"{local1}, {county or 'Unknown County'}, {nation}"
                    local1_counts[local1_key] = local1_counts.get(local1_key, 0) + 1
                
                # Count local2 (village/hamlet) if identified
                if local2:
                    local2_key = f"{local2}, {local1 or 'Unknown Local1'}, {county or 'Unknown County'}, {nation}"
                    local2_counts[local2_key] = local2_counts.get(local2_key, 0) + 1
            
            elif result['recognized_parts']:
                # Recognized some parts but couldn't fully categorize
                unrecognized_places.add(birth_place)
            else:
                # Completely unparseable - store with individual details
                birth_year = getattr(individual, 'birth_year', None) or "Unknown"
                death_year = getattr(individual, 'death_year', None) or "Unknown"
                individual_name = getattr(individual, 'name', 'Unknown Name')
                
                unparseable_places.append({
                    'birth_place': birth_place,
                    'name': individual_name,
                    'birth_year': birth_year,
                    'death_year': death_year
                })
        
        return {
            'total_processed': total_processed,
            'blank_count': blank_count,
            'nation_counts': nation_counts,
            'county_counts': county_counts,
            'local1_counts': local1_counts,
            'local2_counts': local2_counts,
            'unrecognized_places': unrecognized_places,
            'unparseable_places': unparseable_places,
            'blank_places': blank_places,
            'incomplete_places': incomplete_places,
            'location_errors': location_errors,
            'street_addresses': street_addresses
        }
    
    def _display_nations_summary(self, data: dict):
        """Display summary report showing only nations."""
        total_processed = data['total_processed']
        blank_count = data['blank_count']
        nation_counts = data['nation_counts']
        unrecognized_places = data['unrecognized_places']
        unparseable_places = data['unparseable_places']
        blank_places = data['blank_places']
        incomplete_places = data['incomplete_places']
        location_errors = data['location_errors']
        
        print(f"\n{'='*50}")
        print(f"BIRTH PLACE SUMMARY BY NATIONS")
        print(f"{'='*50}")
        print(f"Total individuals: {total_processed}")
        print(f"With birth place data: {total_processed - blank_count}")
        print(f"Blank birth places: {blank_count}")
        
        if nation_counts:
            print(f"\n--- NATIONS ---")
            for nation, count in sorted(nation_counts.items(), key=lambda x: x[1], reverse=True):
                percentage = (count / (total_processed - blank_count)) * 100
                print(f"  {nation}: {count} ({percentage:.1f}%)")
        
        # Summary of unprocessed
        total_unprocessed = len(unrecognized_places) + len(unparseable_places)
        if total_unprocessed > 0:
            print(f"\nUnprocessed places: {total_unprocessed}")
            if unrecognized_places:
                print(f"  Partially recognized: {len(unrecognized_places)}")
            if unparseable_places:
                print(f"  Unparseable: {len(unparseable_places)}")
            print("(Use detailed analysis for breakdown)")
        
        # Summary of location errors
        if location_errors:
            print(f"\nLocation errors found: {len(location_errors)}")
            print("(Use detailed analysis for breakdown)")
        
        print(f"\n{'='*50}")
    
    def _display_detailed_breakdown(self, data: dict):
        """Display detailed report showing nations, counties, local1, local2, and unprocessed items."""
        total_processed = data['total_processed']
        blank_count = data['blank_count']
        nation_counts = data['nation_counts']
        county_counts = data['county_counts']
        local1_counts = data['local1_counts']
        local2_counts = data['local2_counts']
        unrecognized_places = data['unrecognized_places']
        unparseable_places = data['unparseable_places']
        blank_places = data['blank_places']
        incomplete_places = data['incomplete_places']
        location_errors = data['location_errors']
        street_addresses = data['street_addresses']
        
        print(f"\n{'='*60}")
        print(f"DETAILED BIRTH PLACE ANALYSIS")
        print(f"{'='*60}")
        print(f"Total individuals processed: {total_processed}")
        print(f"Individuals with blank birth places: {blank_count}")
        print(f"Individuals with birth place data: {total_processed - blank_count}")
        
        # Nations, counties, local1, and local2 grouped hierarchically
        if nation_counts:
            print(f"\n--- HIERARCHICAL BIRTH PLACE BREAKDOWN ---")
            
            # Calculate total nation count for "Other" calculation
            total_nation_count = sum(nation_counts.values())
            total_with_places = total_processed - blank_count
            
            # Sort nations by count
            sorted_nations = sorted(nation_counts.items(), key=lambda x: x[1], reverse=True)
            for nation, nation_count in sorted_nations:
                percentage = (nation_count / total_with_places) * 100
                print(f"{nation}: {nation_count} ({percentage:.1f}%)")
                
                # Show counties for this nation
                nation_counties = []
                nation_counties_total = 0
                for county_key, county_count in county_counts.items():
                    if county_key.endswith(f", {nation}"):
                        county_name = county_key.split(", ")[0]
                        nation_counties.append((county_name, county_count))
                        nation_counties_total += county_count
                
                if nation_counties:
                    # Sort counties by count
                    nation_counties.sort(key=lambda x: x[1], reverse=True)
                    for county_name, county_count in nation_counties:
                        county_percentage = (county_count / total_with_places) * 100
                        print(f"    {county_name}: {county_count} ({county_percentage:.1f}%)")
                        
                        # Show local1 places for this county under this nation
                        county_local1_places = []
                        county_local1_total = 0
                        for local1_key, local1_count in local1_counts.items():
                            # Format is: "Local1, County, Nation"
                            local1_parts = local1_key.split(", ")
                            if len(local1_parts) >= 3:
                                local1_name = local1_parts[0]
                                local1_county = local1_parts[1]
                                local1_nation = local1_parts[2]
                                
                                if local1_county == county_name and local1_nation == nation:
                                    county_local1_places.append((local1_name, local1_count))
                                    county_local1_total += local1_count
                        
                        if county_local1_places:
                            # Sort local1 places by count
                            county_local1_places.sort(key=lambda x: x[1], reverse=True)
                            for local1_name, local1_count in county_local1_places:
                                local1_percentage = (local1_count / total_with_places) * 100
                                print(f"        {local1_name}: {local1_count} ({local1_percentage:.1f}%)")
                                
                                # Show local2 places for this local1
                                local1_local2_places = []
                                local1_local2_total = 0
                                for local2_key, local2_count in local2_counts.items():
                                    # Format is: "Local2, Local1, County, Nation"
                                    local2_parts = local2_key.split(", ")
                                    if len(local2_parts) >= 4:
                                        local2_name = local2_parts[0]
                                        local2_local1 = local2_parts[1]
                                        local2_county = local2_parts[2]
                                        local2_nation = local2_parts[3]
                                        
                                        if (local2_local1 == local1_name and 
                                            local2_county == county_name and 
                                            local2_nation == nation):
                                            local1_local2_places.append((local2_name, local2_count))
                                            local1_local2_total += local2_count
                                
                                if local1_local2_places:
                                    # Sort local2 places by count
                                    local1_local2_places.sort(key=lambda x: x[1], reverse=True)
                                    for local2_name, local2_count in local1_local2_places:
                                        local2_percentage = (local2_count / total_with_places) * 100
                                        print(f"            {local2_name}: {local2_count} ({local2_percentage:.1f}%)")
                                    
                                    # Add "Other" for local2 if there are unaccounted local1 individuals
                                    local1_other_count = local1_count - local1_local2_total
                                    if local1_other_count > 0:
                                        local1_other_percentage = (local1_other_count / total_with_places) * 100
                                        print(f"            Other: {local1_other_count} ({local1_other_percentage:.1f}%)")
                            
                            # Add "Other" for local1 if there are unaccounted county individuals
                            county_other_count = county_count - county_local1_total
                            if county_other_count > 0:
                                county_other_percentage = (county_other_count / total_with_places) * 100
                                print(f"        Other: {county_other_count} ({county_other_percentage:.1f}%)")
                    
                    # Add "Other" for counties if there are unaccounted nation individuals
                    nation_other_count = nation_count - nation_counties_total
                    if nation_other_count > 0:
                        nation_other_percentage = (nation_other_count / total_with_places) * 100
                        print(f"    Other: {nation_other_count} ({nation_other_percentage:.1f}%)")
            
            # Add "Other" for nations if there are unaccounted individuals with birth places
            nations_other_count = total_with_places - total_nation_count
            if nations_other_count > 0:
                nations_other_percentage = (nations_other_count / total_with_places) * 100
                print(f"Other: {nations_other_count} ({nations_other_percentage:.1f}%)")
        
        # Places without clear hierarchical associations
        if local1_counts:
            # Find local1 places that weren't shown above (those with "Unknown County")
            remaining_local1_places = []
            for local1_key, count in local1_counts.items():
                local1_parts = local1_key.split(", ")
                if len(local1_parts) >= 3:
                    local1_county = local1_parts[1]
                    if local1_county == "Unknown County":
                        remaining_local1_places.append((local1_key, count))
            
            if remaining_local1_places:
                print(f"\n--- PLACES WITHOUT CLEAR HIERARCHICAL ASSOCIATIONS ---")
                sorted_remaining = sorted(remaining_local1_places, key=lambda x: x[1], reverse=True)
                for place_info, count in sorted_remaining:
                    percentage = (count / (total_processed - blank_count)) * 100
                    print(f"  {place_info}: {count} ({percentage:.1f}%)")
        
        # Street addresses (tracked but not counted in main analysis)
        if street_addresses:
            print(f"\n--- STREET ADDRESSES DETECTED ({len(street_addresses)}) ---")
            show_details = input(f"Show street address details? (y/n): ").strip().lower()
            if show_details in ['y', 'yes']:
                print("Street addresses found in birth places (not counted in main analysis):")
                # Group by address for summary
                address_counts = {}
                for entry in street_addresses:
                    address = entry['address']
                    if address not in address_counts:
                        address_counts[address] = []
                    address_counts[address].append(entry)
                
                # Sort by count then alphabetically
                sorted_addresses = sorted(address_counts.items(), key=lambda x: (-len(x[1]), x[0]))
                for address, entries in sorted_addresses:
                    count = len(entries)
                    print(f"  • '{address}' ({count} occurrence{'s' if count != 1 else ''})")
                    for entry in sorted(entries, key=lambda x: x['name']):
                        print(f"    {entry['name']} (Born: {entry['birth_year']}, Died: {entry['death_year']})")
                        print(f"    Full birth place: '{entry['birth_place']}'")
                    print()
            else:
                print("(Street address details skipped - use detailed analysis to review)")
        
        # Location errors
        if location_errors:
            print(f"\n--- LOCATION ERRORS ({len(location_errors)}) ---")
            print("These locations have incorrect nation/county associations:")
            for error in location_errors:
                print(f"  • {error}")
        
        # Incomplete places (partially classified)
        if incomplete_places:
            total_incomplete_count = sum(len(individuals) for individuals in incomplete_places.values())
            print(f"\n--- INCOMPLETE CLASSIFICATIONS ({total_incomplete_count}) ---")
            show_details = input(f"Show individual details for {total_incomplete_count} incomplete classifications? (y/n): ").strip().lower()
            if show_details in ['y', 'yes']:
                print("Birth places where not all parts were identified:")
                # Sort by count (descending) then by place name
                sorted_incomplete = sorted(incomplete_places.items(), key=lambda x: (-len(x[1]), x[0]))
                for place, individuals in sorted_incomplete:
                    count = len(individuals)
                    print(f"  • '{place}' ({count} occurrence{'s' if count != 1 else ''})")
                    # Sort individuals by name for consistent display
                    sorted_individuals = sorted(individuals, key=lambda x: x['name'])
                    for person in sorted_individuals:
                        name = person['name']
                        birth_year = person['birth_year']
                        death_year = person['death_year']
                        print(f"    Individual: {name} (Born: {birth_year}, Died: {death_year})")
                    print()
            else:
                print("Birth places where not all parts were identified:")
                # Sort by count (descending) then by place name  
                sorted_incomplete = sorted(incomplete_places.items(), key=lambda x: (-len(x[1]), x[0]))
                for place, individuals in sorted_incomplete:
                    count = len(individuals)
                    print(f"  • {place} ({count} occurrence{'s' if count != 1 else ''})")
                print("(Individual details skipped - use detailed analysis to review)")
        
        # Unrecognized places (partially recognized)
        if unrecognized_places:
            print(f"\n--- UNRECOGNIZED PLACES ({len(unrecognized_places)}) ---")
            print("These places were partially recognized but couldn't be fully categorized:")
            for place in sorted(unrecognized_places):
                print(f"  • {place}")
        
        # Unparseable places
        if unparseable_places:
            print(f"\n--- UNPARSEABLE PLACES ({len(unparseable_places)}) ---")
            show_details = input(f"Show individual details for {len(unparseable_places)} unparseable places? (y/n): ").strip().lower()
            if show_details in ['y', 'yes']:
                print("These places couldn't be parsed or recognized:")
                # Sort by birth place name for consistent display
                sorted_unparseable = sorted(unparseable_places, key=lambda x: x['birth_place'])
                for entry in sorted_unparseable:
                    birth_place = entry['birth_place']
                    name = entry['name']
                    birth_year = entry['birth_year']
                    death_year = entry['death_year']
                    print(f"  • '{birth_place}'")
                    print(f"    Individual: {name} (Born: {birth_year}, Died: {death_year})")
                    print()
            else:
                print("(Individual details skipped - use detailed analysis to review)")
        
        # Blank birth places
        if blank_places:
            print(f"\n--- BLANK BIRTH PLACES ({len(blank_places)}) ---")
            show_details = input(f"Show individual details for {len(blank_places)} individuals with blank birth places? (y/n): ").strip().lower()
            if show_details in ['y', 'yes']:
                print("These individuals have no birth place data:")
                # Sort by name for consistent display
                sorted_blanks = sorted(blank_places, key=lambda x: x['name'])
                for entry in sorted_blanks:
                    name = entry['name']
                    birth_year = entry['birth_year']
                    death_year = entry['death_year']
                    print(f"  • {name} (Born: {birth_year}, Died: {death_year})")
                print()
            else:
                print("(Individual details skipped - use detailed analysis to review)")
        
        print(f"\n{'='*60}")
        
        if unrecognized_places or unparseable_places or blank_places or location_errors:
            print("Note: Unrecognized, unparseable, blank, and error locations can be reviewed")
            print("to improve data quality and mapping tables for future analysis accuracy.")
        
        print(f"\n{'='*60}")
    
    def _parse_birth_place(self, birth_place: str) -> dict:
        """
        Parse a birth place string and categorize it using hierarchical structure.
        
        Returns dict with:
        - nation: identified nation or None
        - county: identified county or None  
        - local1: identified main place or None
        - local2: identified village/hamlet or None
        - local3: identified street address or None (detected but not counted)
        - recognized_parts: True if any parts were recognized
        - location_errors: List of error messages for misplaced locations
        """
        place_lower = birth_place.lower().strip()
        
        # First try splitting by comma
        place_parts = [part.strip() for part in birth_place.split(',') if part.strip()]
        
        # If only one part (no commas), try splitting by space
        if len(place_parts) == 1:
            space_parts = [part.strip() for part in birth_place.split() if part.strip()]
            if len(space_parts) > 1:
                place_parts = space_parts
        
        result = {
            'nation': None,
            'county': None,
            'local1': None,
            'local2': None,
            'local3': None,
            'recognized_parts': False,
            'location_errors': []
        }
        
        # Check for street address (local3) - any part with a number at the start
        street_address_part = None
        remaining_parts = []
        for part in place_parts:
            # Check if part starts with a number (street address indicator)
            part_words = part.strip().split()
            if part_words and part_words[0].isdigit():
                street_address_part = part.strip()
                result['local3'] = street_address_part
                result['recognized_parts'] = True
            else:
                remaining_parts.append(part)
        
        # Use remaining parts for geographical analysis
        place_parts = remaining_parts
        
        # Check for nations (case insensitive)
        for nation in self.nation_counties.keys():
            if nation.lower() in place_lower:
                result['nation'] = nation
                result['recognized_parts'] = True
                break
        
        # Check for counties (exact word matching, case insensitive) and detect nation mismatches
        found_county_nation = None
        for nation, counties in self.nation_counties.items():
            for county in counties:
                county_found = False
                
                # Special handling for combined counties
                if county == 'Devon/Dorset':
                    for part in place_parts:
                        part_words = part.lower().split()
                        if 'devon' in part_words or 'dorset' in part_words:
                            county_found = True
                            break
                elif county == 'Shropshire/Salop':
                    for part in place_parts:
                        part_words = part.lower().split()
                        if 'shropshire' in part_words or 'salop' in part_words:
                            county_found = True
                            break
                else:
                    # Use exact word matching for other counties
                    for part in place_parts:
                        part_words = part.lower().split()
                        if county.lower() in part_words:
                            county_found = True
                            break
                
                if county_found:
                    result['county'] = county
                    result['recognized_parts'] = True
                    found_county_nation = nation
                    
                    # Check if this county is being associated with the wrong nation
                    if result['nation'] and result['nation'] != nation:
                        error_msg = f"'{birth_place}' - County '{county}' belongs to {nation}, not {result['nation']}"
                        result['location_errors'].append(error_msg)
                        # Don't override the nation here - keep the error for reporting
                    elif not result['nation']:
                        # If we found a county but no nation yet, assign the correct nation
                        result['nation'] = nation
                    break
            if result['county']:
                break
        
        # Check for local1 places (main places) and local2 places (villages/hamlets)
        if result['county'] and result['county'] in self.county_places:
            county_data = self.county_places[result['county']]
            
            # First pass: Look for local1 places (main places)
            for local1_place, local1_data in county_data.items():
                local1_found = False
                for part in place_parts:
                    part_words = part.lower().split()
                    if local1_place.lower() in part_words:
                        local1_found = True
                        break
                
                if local1_found:
                    result['local1'] = local1_place
                    result['recognized_parts'] = True
                    
                    # Second pass: Look for local2 places under this local1
                    if 'local2_places' in local1_data:
                        for local2_place in local1_data['local2_places']:
                            local2_found = False
                            for part in place_parts:
                                part_words = part.lower().split()
                                if local2_place.lower() in part_words:
                                    local2_found = True
                                    break
                            
                            if local2_found:
                                result['local2'] = local2_place
                                result['recognized_parts'] = True
                                break
                    
                    # Check for known streets in this local1 (validates local3 if present)
                    if result['local3'] and 'known_streets' in local1_data:
                        street_name = ' '.join(result['local3'].split()[1:])  # Remove house number
                        if street_name and street_name not in local1_data['known_streets']:
                            # Street not recognized, but keep it as local3 anyway
                            pass
                    
                    break
            
            # If no local1 found, check if any local2 places match without local1 context
            if not result['local1']:
                for local1_place, local1_data in county_data.items():
                    if 'local2_places' in local1_data:
                        for local2_place in local1_data['local2_places']:
                            local2_found = False
                            for part in place_parts:
                                part_words = part.lower().split()
                                if local2_place.lower() in part_words:
                                    local2_found = True
                                    break
                            
                            if local2_found:
                                result['local2'] = local2_place
                                result['local1'] = local1_place  # Assign parent local1
                                result['recognized_parts'] = True
                                break
                    if result['local2']:
                        break
        
        # If no county found yet, check all counties for local1/local2 matches
        if not result['county']:
            for county, county_data in self.county_places.items():
                for local1_place, local1_data in county_data.items():
                    # Check for local1 match
                    local1_found = False
                    for part in place_parts:
                        part_words = part.lower().split()
                        if local1_place.lower() in part_words:
                            local1_found = True
                            break
                    
                    if local1_found:
                        result['local1'] = local1_place
                        result['county'] = county
                        result['recognized_parts'] = True
                        
                        # Also assign the nation for this county
                        if not result['nation']:
                            for nation, counties in self.nation_counties.items():
                                if county in counties:
                                    result['nation'] = nation
                                    break
                        
                        # Check for local2 under this local1
                        if 'local2_places' in local1_data:
                            for local2_place in local1_data['local2_places']:
                                local2_found = False
                                for part in place_parts:
                                    part_words = part.lower().split()
                                    if local2_place.lower() in part_words:
                                        local2_found = True
                                        break
                                
                                if local2_found:
                                    result['local2'] = local2_place
                                    result['recognized_parts'] = True
                                    break
                        break
                
                if result['local1']:
                    break
        
        # Check for direct nation-place mappings (places without intermediate counties)
        if not result['local1']:  # Only check if we haven't found a local1 yet
            for nation, places in self.nation_places.items():
                for place in places:
                    # Use exact word matching
                    place_found = False
                    for part in place_parts:
                        part_words = part.lower().split()
                        if place.lower() in part_words:
                            place_found = True
                            break
                    
                    if place_found:
                        result['local1'] = place
                        result['recognized_parts'] = True
                        
                        # Check if this place is being associated with the wrong nation
                        if result['nation'] and result['nation'] != nation:
                            error_msg = f"'{birth_place}' - Place '{place}' belongs to {nation}, not {result['nation']}"
                            result['location_errors'].append(error_msg)
                            # Don't override the nation here - keep the error for reporting
                        elif not result['nation']:
                            # If we found a place but no nation yet, assign the correct nation
                            result['nation'] = nation
                        # Note: No county assigned for direct nation-place mappings
                        break
                if result['local1']:
                    break
        
        return result


class DataQueryHandler:
    """Handles data management operations."""
    
    def __init__(self, database: GedcomDB):
        self.database = database
