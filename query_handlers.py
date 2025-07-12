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


class DataQueryHandler:
    """Handles data management operations."""
    
    def __init__(self, database: GedcomDB):
        self.database = database
