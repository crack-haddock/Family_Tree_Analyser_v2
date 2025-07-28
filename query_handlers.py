"""
Query handlers for Family Tree Analyser v2.
Contains implementations for various analysis and search queries.
"""

import json
import re
import time
from pathlib import Path
from typing import List, Optional
from gedcom_db import GedcomDB, Individual  
from ged4py_db import Ged4PyGedcomDB


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

    def find_individuals_with_no_gender(self):
        """
        Print individuals with no gender specified.
        Checks the raw GEDCOM record for a SEX tag.
        """
        print("\n--- Validity Check: Individuals with No Gender Specified ---")
        all_individuals = self.database.get_all_individuals()
        no_gender = []

        for ind in all_individuals:
            found_sex = None
            if hasattr(ind, 'raw_record') and ind.raw_record and hasattr(ind.raw_record, 'sub_records'):
                for sub in ind.raw_record.sub_records:
                    if getattr(sub, 'tag', None) == 'SEX':
                        found_sex = (sub.value or '').strip().upper()
                        break
            # Treat blank, U, UNK, UNKNOWN, or missing as "no gender"
            if not found_sex or found_sex in ["", "U", "UNK", "UNKNOWN"]:
                no_gender.append(ind)

        if not no_gender:
            print("\n✅ All individuals have gender specified.")
        else:
            print(f"\n❌ Found {len(no_gender)} individual(s) with no gender specified:\n")
            for ind in no_gender:
                print(f"• {ind.name} [{ind.xref_id}]")
            print(f"\nTotal individuals with no gender specified: {len(no_gender)}")
        input("\nPress Enter to continue...")

    def find_individuals_not_in_ancestry_tree(self):
        """
        Print individuals who are NOT in the current ancestry tree (i.e., not in ancestor_filter_ids).
        Shows a list and a total at the bottom, including year born/died in brackets by the name.
        """
        print("\n--- Validity Check: Individuals NOT in Current Ancestry Tree ---")
        if not self.ancestor_filter_ids:
            print("No ancestor filter is currently set. All individuals are considered part of the tree.")
            input("\nPress Enter to continue...")
            return

        all_individuals = self.database.get_all_individuals()
        not_in_tree = [ind for ind in all_individuals if ind.xref_id not in self.ancestor_filter_ids]

        if not not_in_tree:
            print("\n✅ All individuals are in the current ancestry tree.")
        else:
            print(f"\n❌ Found {len(not_in_tree)} individual(s) NOT in the current ancestry tree:\n")
            for ind in not_in_tree:
                birth = ind.birth_year if getattr(ind, "birth_year", None) else "?"
                death = ind.death_year if getattr(ind, "death_year", None) else "?"
                print(f"• {ind.name} [{birth}-{death}] [{ind.xref_id}]")
            print(f"\nTotal individuals NOT in current ancestry tree: {len(not_in_tree)}")
        input("\nPress Enter to continue...")

class ReportQueryHandler:
    """Handles analysis and reporting queries."""
    
    def __init__(self, database: GedcomDB):
        self.database = database
        self.ancestor_filter_ids: Optional[set] = None
        
        # Load place configuration from JSON file
        self._load_places_config()
        
        # Load occupation configuration from JSON file
        self._load_occupations_config()
    
    def _load_places_config(self):
        """Load place mappings from JSON configuration file."""
        start_time = time.time()
        config_file = Path(__file__).parent / 'places_config.json'
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Load the mappings from JSON
            self.nation_counties = config.get('nation_counties', {})
            self.county_places = config.get('county_places', {})
            self.nation_places = config.get('nation_places', {})
            
            end_time = time.time()
            print(f"✓ Loaded places configuration ({end_time - start_time:.3f} seconds)")
            
        except FileNotFoundError:
            end_time = time.time()
            print(f"⚠ Places configuration file not found ({end_time - start_time:.3f} seconds)")
            print("Using default empty mappings.")
            self._use_default_mappings()
        except json.JSONDecodeError as e:
            print(f"⚠ Error parsing places configuration: {e}")
            print("Using default empty mappings.")
            self._use_default_mappings()
        except Exception as e:
            print(f"⚠ Unexpected error loading places configuration: {e}")
            print("Using default empty mappings.")
            self._use_default_mappings()
    
    def _load_occupations_config(self):
        """Load occupation groupings from JSON configuration file."""
        config_file = Path(__file__).parent / 'occupations_config.json'
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
            self.occupation_groups = config.get('occupation_groups', {})
            self.occupation_patterns = config.get('occupation_patterns', {})
            
            print(f"✓ Loaded {len(self.occupation_groups)} occupation groups from {config_file}")
            
        except FileNotFoundError:
            print(f"⚠ Occupation config file not found: {config_file}")
            print("  Creating default occupation mappings...")
            self._use_default_occupation_mappings()
        except json.JSONDecodeError as e:
            print(f"⚠ Error parsing occupation config file: {e}")
            print("  Using default occupation mappings...")
            self._use_default_occupation_mappings()
        except Exception as e:
            print(f"⚠ Error loading occupation config: {e}")
            print("  Using default occupation mappings...")
            self._use_default_occupation_mappings()
    
    def _use_default_occupation_mappings(self):
        """Fallback to basic default occupation mappings if config file fails to load."""
        self.occupation_groups = {
            'House Keeper': ['housewife', 'housekeeper', 'unpaid duties', 'domestic duties'],
            'Coal Worker': ['coal miner', 'coalminer', 'collier'],
            'Farm Worker': ['agricultural labourer', 'farm labourer', 'farm worker'],
            'Servant': ['servant', 'domestic servant'],
            'Labourer': ['labourer', 'laborer', 'general labourer']
        }
        self.occupation_patterns = {
            'apprentice_pattern': 'apprentice',
            'assistant_pattern': 'assistant'
        }
    
    def _use_default_mappings(self):
        """Fallback to empty default mappings if config file fails to load."""
        self.nation_counties = {
            'England': [],
            'Wales': [],
            'Scotland': [],
            'Ireland': [],
            'Jamaica': [],
            'USA': [],
            'France': [],
            'Australia': []
        }
        self.county_places = {}
        self.nation_places = {}
    
    def _group_occupation(self, occupation_text: str) -> str:
        """
        Group an occupation under a standardized category.
        
        Args:
            occupation_text: Raw occupation text from the data
            
        Returns:
            Grouped occupation name, or original text if no group found
        """
        if not occupation_text:
            return occupation_text
            
        occupation_lower = occupation_text.lower().strip()
        
        # Check each occupation group for exact matches only
        for group_name, aliases in self.occupation_groups.items():
            for alias in aliases:
                alias_lower = alias.lower()
                # Check for exact match only
                if occupation_lower == alias_lower:
                    return group_name
        
        # Check for pattern matches (apprentice, assistant, etc.)
        for pattern_name, pattern in self.occupation_patterns.items():
            if pattern.lower() in occupation_lower:
                # Try to extract the base occupation and group it
                base_occupation = occupation_lower.replace(pattern.lower(), '').strip()
                if base_occupation:
                    grouped_base = self._group_occupation(base_occupation)
                    if grouped_base != base_occupation:
                        return f"{pattern.title()} {grouped_base}"
                    else:
                        return f"{pattern.title()} {base_occupation.title()}"
                else:
                    return pattern.title()
        
        # Return original if no grouping found
        return occupation_text
        """Fallback to empty default mappings if config file fails to load."""
        self.nation_counties = {
            'England': [],
            'Wales': [],
            'Scotland': [],
            'Ireland': [],
            'Jamaica': [],
            'USA': [],
            'France': [],
            'Australia': []
        }
        self.county_places = {}
        self.nation_places = {}
    
    def add_place_to_config(self, place_name: str, county: str, nation: str = None, 
                           local2_places: List[str] = None, known_streets: List[str] = None):
        """
        Add a new place to the configuration and save it back to the JSON file.
        
        Args:
            place_name: Name of the place to add
            county: County the place belongs to
            nation: Nation the county belongs to (optional, will try to determine automatically)
            local2_places: List of smaller places within this place
            known_streets: List of known streets in this place
        """
        # Find the nation for this county if not provided
        if not nation:
            for nat, counties in self.nation_counties.items():
                if county in counties:
                    nation = nat
                    break
            
            if not nation:
                print(f"⚠ Could not determine nation for county '{county}'. Please specify nation.")
                return False
        
        # Add county to nation if not already present
        if nation not in self.nation_counties:
            self.nation_counties[nation] = []
        if county not in self.nation_counties[nation]:
            self.nation_counties[nation].append(county)
        
        # Add county section if not present
        if county not in self.county_places:
            self.county_places[county] = {}
        
        # Add the place
        self.county_places[county][place_name] = {
            'local2_places': local2_places or [],
            'known_streets': known_streets or []
        }
        
        # Save back to JSON file
        return self._save_places_config()
    
    def _save_places_config(self):
        """Save current place mappings back to the JSON configuration file."""
        config_file = Path(__file__).parent / 'places_config.json'
        
        try:
            config = {
                'nation_counties': self.nation_counties,
                'county_places': self.county_places,
                'nation_places': self.nation_places
            }
            
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            print(f"✓ Saved places configuration to {config_file}")
            return True
            
        except Exception as e:
            print(f"⚠ Error saving places configuration: {e}")
            return False
    
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
        
        # NEW: Store original addresses for debugging
        nation_addresses = {}  # nation -> list of (birth_place, name, year)
        county_addresses = {}  # "county, nation" -> list of (birth_place, name, year)
        local1_addresses = {}  # "local1, county, nation" -> list of (birth_place, name, year)
        
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
                # Add person details to each location error
                for error in result['location_errors']:
                    if isinstance(error, dict):
                        error['person_name'] = getattr(individual, 'name', 'Unknown Name')
                        error['birth_year'] = getattr(individual, 'birth_year', None) or "Unknown"
                        error['death_year'] = getattr(individual, 'death_year', None) or "Unknown"
                    else:
                        # Handle legacy string errors by converting to dict
                        enhanced_error = {
                            'error_type': 'legacy',
                            'message': str(error),
                            'birth_place': birth_place,
                            'person_name': getattr(individual, 'name', 'Unknown Name'),
                            'birth_year': getattr(individual, 'birth_year', None) or "Unknown",
                            'death_year': getattr(individual, 'death_year', None) or "Unknown"
                        }
                        result['location_errors'] = [enhanced_error if e == error else e for e in result['location_errors']]
                
                location_errors.extend(result['location_errors'])
                # Don't count entries with location errors in the main counts
                continue
            
            # TEMPORARY DEBUG: Check for Cheshire+Jamaica combination
            if result['county'] == 'Cheshire' and result['nation'] == 'Jamaica':
                print(f"\n*** CHESHIRE+JAMAICA DEBUG ***")
                print(f"Original address: '{birth_place}'")
                print(f"Person: {getattr(individual, 'name', 'Unknown Name')} (b. {getattr(individual, 'birth_year', None) or 'Unknown'})")
                print(f"Parsed as: Nation={result['nation']}, County={result['county']}, Local1={result['local1']}")
                print(f"*** END DEBUG ***\n")            # Track street addresses but don't count them
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
                
                # Store original address for this nation
                if nation not in nation_addresses:
                    nation_addresses[nation] = []
                person_info = {
                    'birth_place': birth_place,
                    'name': getattr(individual, 'name', 'Unknown Name'),
                    'birth_year': getattr(individual, 'birth_year', None) or "Unknown"
                }
                nation_addresses[nation].append(person_info)
                
                # Count county if identified (but not for direct nation places or nation-as-county cases)
                if county:
                    # Skip county counting if this is a direct nation place
                    is_direct_nation_place = (local1 and 
                                            nation in self.nation_places and 
                                            self.nation_places[nation] and 
                                            local1 in self.nation_places[nation])
                    
                    # Also skip if county name equals nation name (e.g., "Scotland, Scotland")
                    is_nation_as_county = (county == nation)
                    
                    if not is_direct_nation_place and not is_nation_as_county:
                        county_key = f"{county}, {nation}"
                        county_counts[county_key] = county_counts.get(county_key, 0) + 1
                        
                        # Store original address for this county
                        if county_key not in county_addresses:
                            county_addresses[county_key] = []
                        county_addresses[county_key].append(person_info)
                
                # Count local1 (main place) if identified
                if local1:
                    # For nations with direct nation places (non-UK + UK nations with nation_places), don't include county in the key
                    if (nation not in ['England', 'Wales', 'Scotland', 'UK']) or (nation in self.nation_places and self.nation_places[nation] and local1 in self.nation_places[nation]):
                        local1_key = f"{local1}, {nation}"
                    else:
                        local1_key = f"{local1}, {county or 'Unknown County'}, {nation}"
                    local1_counts[local1_key] = local1_counts.get(local1_key, 0) + 1
                    
                    # Store original address for this local1
                    if local1_key not in local1_addresses:
                        local1_addresses[local1_key] = []
                    local1_addresses[local1_key].append(person_info)
                
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
            'nation_addresses': nation_addresses,
            'county_addresses': county_addresses,
            'local1_addresses': local1_addresses,
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
        nation_addresses = data.get('nation_addresses', {})
        county_addresses = data.get('county_addresses', {})
        local1_addresses = data.get('local1_addresses', {})
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
                        
                        # For small datasets, show original addresses
                        if total_processed <= 50:  # Show addresses for small datasets
                            county_key = f"{county_name}, {nation}"
                            if county_key in county_addresses:
                                print(f"        → Original addresses:")
                                for addr_info in county_addresses[county_key]:
                                    print(f"          • '{addr_info['birth_place']}' - {addr_info['name']} (b. {addr_info['birth_year']})")
                        
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
                                    
                                    # Add "Other or Unspecified" for local2 if there are unaccounted local1 individuals
                                    local1_other_count = local1_count - local1_local2_total
                                    if local1_other_count > 0:
                                        local1_other_percentage = (local1_other_count / total_with_places) * 100
                                        print(f"            Other or Unspecified: {local1_other_count} ({local1_other_percentage:.1f}%)")
                            
                            # Add "Other or Unspecified" for local1 if there are unaccounted county individuals
                            county_other_count = county_count - county_local1_total
                            if county_other_count > 0:
                                county_other_percentage = (county_other_count / total_with_places) * 100
                                print(f"        Other or Unspecified: {county_other_count} ({county_other_percentage:.1f}%)")
                    
                    # Add "Other or Unspecified" for counties if there are unaccounted nation individuals
                    nation_other_count = nation_count - nation_counties_total
                    
                    # Check if this nation also has direct nation places
                    has_direct_nation_places = (nation in self.nation_places and self.nation_places[nation])
                    
                    if not has_direct_nation_places and nation_other_count > 0:
                        nation_other_percentage = (nation_other_count / total_with_places) * 100
                        print(f"    Other or Unspecified: {nation_other_count} ({nation_other_percentage:.1f}%)")
                
                # For nations with direct nation places (non-UK nations + UK nations with nation_places), show local1 places directly under the nation
                if (nation not in ['England', 'Wales', 'Scotland', 'UK']) or (nation in self.nation_places and self.nation_places[nation]):
                    nation_local1_places = []
                    nation_local1_total = 0
                    for local1_key, local1_count in local1_counts.items():
                        # Format for non-UK: "Local1, Nation"
                        local1_parts = local1_key.split(", ")
                        if len(local1_parts) == 2:
                            local1_name = local1_parts[0]
                            local1_nation = local1_parts[1]
                            
                            if local1_nation == nation:
                                nation_local1_places.append((local1_name, local1_count))
                                nation_local1_total += local1_count
                    
                    if nation_local1_places:
                        # Sort local1 places by count
                        nation_local1_places.sort(key=lambda x: x[1], reverse=True)
                        for local1_name, local1_count in nation_local1_places:
                            local1_percentage = (local1_count / total_with_places) * 100
                            print(f"    {local1_name}: {local1_count} ({local1_percentage:.1f}%)")
                            
                            # For small datasets, show original addresses
                            if total_processed <= 50:
                                local1_key = f"{local1_name}, {nation}"
                                if local1_key in local1_addresses:
                                    print(f"        → Original addresses:")
                                    for addr_info in local1_addresses[local1_key]:
                                        print(f"          • '{addr_info['birth_place']}' - {addr_info['name']} (b. {addr_info['birth_year']})")
                    
                    # For nations with direct nation places, adjust "Other or Unspecified" based on BOTH counties and local1 places
                    if nation_local1_places:
                        # For nations with both counties and direct places, account for both
                        if nation in ['England', 'Wales', 'Scotland', 'UK']:
                            # UK nations might have both counties and direct places
                            accounted_total = nation_counties_total + nation_local1_total
                        else:
                            # Non-UK nations typically only have direct places
                            accounted_total = nation_local1_total
                        
                        nation_other_count = nation_count - accounted_total
                        if nation_other_count > 0:
                            nation_other_percentage = (nation_other_count / total_with_places) * 100
                            print(f"    Other or Unspecified: {nation_other_count} ({nation_other_percentage:.1f}%)")
            
            # Add "Other or Unspecified" for nations if there are unaccounted individuals with birth places
            nations_other_count = total_with_places - total_nation_count
            if nations_other_count > 0:
                nations_other_percentage = (nations_other_count / total_with_places) * 100
                print(f"Other or Unspecified: {nations_other_count} ({nations_other_percentage:.1f}%)")
        
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
            print("These locations have incorrect geographical associations:")
            print("(Often caused by data entry errors or unfamiliarity with geography)")
            print()
            
            for error in location_errors:
                if isinstance(error, dict):
                    print(f"  • Birth place: '{error.get('birth_place', 'Unknown')}'")
                    print(f"    Problem: {error.get('message', 'Unknown error')}")
                    print(f"    Person: {error.get('person_name', 'Unknown')} (Born: {error.get('birth_year', 'Unknown')}, Died: {error.get('death_year', 'Unknown')})")
                    
                    if error.get('error_type') == 'county_nation_mismatch':
                        print(f"    Note: County '{error.get('detected_county')}' belongs to {error.get('expected_nation')}, not {error.get('detected_nation')}")
                    elif error.get('error_type') == 'uk_nation_nesting':
                        print(f"    Note: {error.get('note', 'UK nations should not be nested within each other')}")
                    elif error.get('error_type') == 'nation_misspelling':
                        print(f"    Note: '{error.get('detected_misspelling')}' might be misspelled '{error.get('suggested_correction')}'")
                else:
                    # Legacy string error
                    print(f"  • {error}")
                print()
        
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
        # Data cleansing: normalize whitespace
        birth_place = self._cleanse_birth_place_string(birth_place)
        
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
        
        # Check for nations (exact word matching, case insensitive) - prioritize specific nations over UK
        detected_nations = []
        for nation in self.nation_counties.keys():
            # Use exact word matching to avoid false positives like "Jamaica Street" matching "Jamaica"
            place_words = place_lower.replace(',', ' ').replace('.', ' ').split()  # Remove punctuation
            nation_words = nation.lower().split()
            
            # For single-word nations, check if the nation appears as a complete word
            if len(nation_words) == 1:
                if nation.lower() in place_words:
                    detected_nations.append(nation)
            else:
                # For multi-word nations, check if all words appear consecutively
                nation_phrase = nation.lower()
                if nation_phrase in place_lower:
                    # Additional check: ensure it's word-bounded
                    import re
                    pattern = r'\b' + re.escape(nation_phrase) + r'\b'
                    if re.search(pattern, place_lower):
                        detected_nations.append(nation)
        
        # Filter logic: prefer specific nations over UK
        if detected_nations:
            if len(detected_nations) == 1:
                result['nation'] = detected_nations[0]
            elif 'UK' in detected_nations and len(detected_nations) > 1:
                # UK found with other nations - use the specific nation, ignore UK
                non_uk_nations = [n for n in detected_nations if n != 'UK']
                if len(non_uk_nations) == 1:
                    result['nation'] = non_uk_nations[0]
                else:
                    # Multiple specific nations found - use the first one
                    result['nation'] = non_uk_nations[0]
            else:
                # Multiple specific nations (no UK) - use the first one
                result['nation'] = detected_nations[0]
            result['recognized_parts'] = True
            
            # TEMPORARY DEBUG: Check for UK being used when England should be used
            if result['nation'] == 'UK':
                # Check if this birth place actually contains England/Wales/Scotland
                specific_nations = ['England', 'Wales', 'Scotland', 'Northern Ireland']
                for specific in specific_nations:
                    if specific.lower() in place_lower:
                        print(f"DEBUG: UK used instead of {specific}: '{birth_place}'")
                        print(f"  Detected nations: {detected_nations}")
                        break
        else:
            # No nations detected - could be a parsing issue or genuinely foreign place
            # Don't try to guess at misspellings - let them fall through to unparseable
            pass
        
        # Determine if we should use UK place/county lookups
        # Skip UK lookups if a non-UK nation is explicitly mentioned
        uk_nations = {'UK', 'England', 'Wales', 'Scotland', 'Northern Ireland'}
        use_uk_lookups = True
        if result['nation'] and result['nation'] not in uk_nations:
            use_uk_lookups = False
        
        # Check for counties (exact word matching, case insensitive) and detect nation mismatches
        # Only do this if we should use UK lookups
        found_county_nation = None
        if use_uk_lookups:
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
                        # Skip if this "county" is actually the already-detected nation
                        # (e.g., don't treat Wales as a county when Wales is already the nation)
                        if result['nation'] and county == result['nation']:
                            continue
                            
                        result['county'] = county
                        result['recognized_parts'] = True
                        found_county_nation = nation
                        
                        # Basic nation assignment if no nation detected yet
                        if not result['nation']:
                            # If we found a county but no nation yet, assign the correct nation
                            result['nation'] = nation
                        elif result['nation'] == 'UK':
                            # Special case: if we had "UK" but found a specific county, 
                            # override UK with the specific nation for that county
                            result['nation'] = nation
                        break
                if result['county']:
                    break
        
        # Additional error detection for geographical inconsistencies
        if result['nation']:
            # Check for UK nations being incorrectly nested within each other
            # E.g., "Someplace, Wales, England" or "Town, Scotland, England"
            remaining_place_text = ' '.join(place_parts).lower()
            
            # Define UK nations and their relationships
            uk_nations = ['england', 'wales', 'scotland', 'northern ireland']
            detected_nation = result['nation'].lower()
            
            # Check if any OTHER UK nation appears in the remaining text
            for other_nation in uk_nations:
                if other_nation != detected_nation and other_nation in remaining_place_text:
                    result['location_errors'].append({
                        'error_type': 'uk_nation_nesting',
                        'message': f"'{birth_place}' - {other_nation.title()} appears with {result['nation']} - UK nations should not be nested within each other",
                        'birth_place': birth_place,
                        'detected_nation': result['nation'],
                        'conflicting_nation': other_nation.title(),
                        'note': f"Both {result['nation']} and {other_nation.title()} are parts of the UK, not parts of each other"
                    })
            
            # Check for obvious English counties listed under Wales/Scotland (and vice versa)
            if result['county']:
                expected_nation_for_county = None
                # Find which nation this county actually belongs to
                for nation, counties in self.nation_counties.items():
                    if result['county'] in counties:
                        expected_nation_for_county = nation
                        break
                
                # If we found the county belongs to a different nation, flag it
                if (expected_nation_for_county and 
                    expected_nation_for_county != result['nation'] and
                    expected_nation_for_county != 'UK'):  # Skip UK super-nation conflicts
                    
                    result['location_errors'].append({
                        'error_type': 'county_nation_mismatch',
                        'message': f"'{birth_place}' - County '{result['county']}' belongs to {expected_nation_for_county}, not {result['nation']}",
                        'birth_place': birth_place,
                        'detected_county': result['county'],
                        'detected_nation': result['nation'],
                        'expected_nation': expected_nation_for_county
                    })
        
        # Check for local1 places (main places) and local2 places (villages/hamlets)
        # Only do this if we should use UK lookups
        if use_uk_lookups and result['county'] and result['county'] in self.county_places:
            county_data = self.county_places[result['county']]
            
            # First pass: Look for local1 places (main places)
            for local1_place, local1_data in county_data.items():
                local1_found = False
                
                # Check if place name appears in individual parts (for comma-separated)
                for part in place_parts:
                    if local1_place.lower() in part.lower():
                        local1_found = True
                        break
                
                # Also check if place name appears in the original string (for space-separated multi-word places)
                if not local1_found and local1_place.lower() in place_lower:
                    local1_found = True
                
                if local1_found:
                    result['local1'] = local1_place
                    result['recognized_parts'] = True
                    
                    # Second pass: Look for local2 places under this local1
                    if 'local2_places' in local1_data:
                        for local2_place in local1_data['local2_places']:
                            local2_found = False
                            
                            # Check if local2 place appears in individual parts
                            for part in place_parts:
                                if local2_place.lower() in part.lower():
                                    local2_found = True
                                    break
                            
                            # Also check if local2 place appears in the original string
                            if not local2_found and local2_place.lower() in place_lower:
                                local2_found = True
                            
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
        # Only do this if we should use UK lookups
        if use_uk_lookups and not result['county']:
            for county, county_data in self.county_places.items():
                for local1_place, local1_data in county_data.items():
                    # Check for local1 match
                    local1_found = False
                    for part in place_parts:
                        part_words = part.lower().split()
                        if local1_place.lower() in part_words:
                            local1_found = True
                            break
                    
                    # Also check if place name appears in the original string (for space-separated multi-word places)
                    if not local1_found and local1_place.lower() in place_lower:
                        local1_found = True
                    
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
                        elif result['nation'] == 'UK':
                            # Special case: if we had "UK" but found a specific county, 
                            # override UK with the specific nation for that county
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
                                
                                # Also check if local2 place appears in the original string
                                if not local2_found and local2_place.lower() in place_lower:
                                    local2_found = True
                                
                                if local2_found:
                                    result['local2'] = local2_place
                                    result['recognized_parts'] = True
                                    break
                        break
                
                if result['local1']:
                    break
        
        # Check for direct nation-place mappings (places without intermediate counties)
        # Only do this if we should use UK lookups AND we haven't found a local1 yet
        if use_uk_lookups and not result['local1']:
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
                        elif result['nation'] == 'UK':
                            # Special case: if we had "UK" but found a specific place, 
                            # override UK with the specific nation for that place
                            result['nation'] = nation
                        # Note: No county assigned for direct nation-place mappings
                        break
                if result['local1']:
                    break
        
        # Check for non-UK nation places if we detected a non-UK nation but haven't found places yet
        if not use_uk_lookups and result['nation'] and not result['local1']:
            # Look up places in the detected nation's nation_places
            if result['nation'] in self.nation_places:
                nation_places_list = self.nation_places[result['nation']]
                for place in nation_places_list:
                    # Use exact matching against full place parts
                    place_found = False
                    for part in place_parts:
                        if place.lower() == part.lower():
                            place_found = True
                            break
                    
                    if place_found:
                        result['local1'] = place
                        result['recognized_parts'] = True
                        # Nation is already set, no county for non-UK places
                        break
        
        return result
    
    def _cleanse_birth_place_string(self, birth_place: str) -> str:
        """
        Cleanse birth place string by normalizing whitespace and removing common issues.
        
        This preprocessing step helps ensure consistent parsing regardless of data quality.
        
        Args:
            birth_place: Raw birth place string from genealogical data
            
        Returns:
            Cleansed birth place string
        """
        if not birth_place:
            return ""
        
        # Convert to string if not already (handle None, numbers, etc.)
        birth_place = str(birth_place)
        
        # Basic whitespace normalization
        birth_place = birth_place.strip()  # Remove leading/trailing whitespace
        
        # Replace multiple spaces with single space (but preserve commas)
        import re
        birth_place = re.sub(r' +', ' ', birth_place)  # Multiple spaces → single space
        
        # Clean up common data entry issues
        birth_place = re.sub(r' *, *', ', ', birth_place)  # Normalize comma spacing
        birth_place = re.sub(r'\t+', ' ', birth_place)     # Tabs → spaces
        birth_place = re.sub(r'\n+', ' ', birth_place)     # Newlines → spaces
        birth_place = re.sub(r'\r+', ' ', birth_place)     # Carriage returns → spaces
        
        # Enhanced comma cleansing - more aggressive approach
        birth_place = re.sub(r'^,+\s*', '', birth_place)   # Remove leading commas and spaces
        birth_place = re.sub(r'\s*,+$', '', birth_place)   # Remove trailing commas and spaces
        birth_place = re.sub(r',+', ',', birth_place)      # Multiple commas → single comma
        birth_place = re.sub(r'\s*,\s*,+\s*', ', ', birth_place)  # ",," patterns → ", "
        birth_place = re.sub(r',\s*,+', ',', birth_place)  # ", ," patterns → ","
        birth_place = re.sub(r'\s*,\s*', ', ', birth_place) # Normalize all comma spacing
        
        # Clean up any remaining problematic comma patterns
        birth_place = re.sub(r'^,\s*', '', birth_place)    # Remove any remaining leading commas
        birth_place = re.sub(r'\s*,$', '', birth_place)    # Remove any remaining trailing commas
        
        # Handle edge case of lone spaces between commas
        birth_place = re.sub(r',\s+,', ',', birth_place)   # ", ," → ","
        birth_place = re.sub(r'\s*,\s*', ', ', birth_place) # Final comma spacing normalization
        
        # Final cleanup: remove any remaining leading/trailing commas that might have been created
        birth_place = re.sub(r'^,+\s*', '', birth_place)   # One more pass for leading commas
        birth_place = re.sub(r'\s*,+$', '', birth_place)   # One more pass for trailing commas
        
        # Remove extra punctuation that might interfere
        birth_place = re.sub(r'[.]{2,}', '', birth_place)  # Multiple periods
        birth_place = re.sub(r'[;]{2,}', ';', birth_place) # Multiple semicolons
        
        # Final whitespace cleanup
        birth_place = birth_place.strip()
        
        return birth_place
    
    def analyze_occupations(self):
        """Option 3: Analyze occupations for each person in current sub-tree."""
        print("\n--- Occupation Analysis ---")
        
        # Get individuals to analyze (filtered or all)
        if self.ancestor_filter_ids is not None:
            print(f"Analyzing occupations for {len(self.ancestor_filter_ids)} filtered individuals...")
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
            print("Analyzing occupations for all individuals...")
            individuals = self.database.get_all_individuals()
        
        print("Processing occupation data...")
        
        # Process each individual and collect occupation data
        individuals_with_occupations = []
        total_individuals = 0
        individuals_with_data = 0
        
        for individual in individuals:
            total_individuals += 1
            occupations = self._extract_occupations(individual)
            
            if occupations:
                individuals_with_data += 1
                individuals_with_occupations.append({
                    'individual': individual,
                    'occupations': occupations
                })
        
        # Display results summary
        print(f"\n{'='*60}")
        print(f"OCCUPATION ANALYSIS RESULTS")
        print(f"{'='*60}")
        print(f"Total individuals processed: {total_individuals}")
        print(f"Individuals with occupation data: {individuals_with_data}")
        print(f"Individuals without occupation data: {total_individuals - individuals_with_data}")
        
        if individuals_with_occupations:
            # Count and group occupations
            occupation_counts = {}  # For original occupations
            grouped_occupation_counts = {}  # For grouped occupations
            all_occupations = []
            occupation_years = {}  # Track years for each occupation
            
            for entry in individuals_with_occupations:
                for occupation in entry['occupations']:
                    occ_text = occupation['occupation'].strip()
                    all_occupations.append(occ_text)
                    
                    # Count original occupation
                    if occ_text in occupation_counts:
                        occupation_counts[occ_text] += 1
                    else:
                        occupation_counts[occ_text] = 1
                    
                    # Group the occupation and count grouped version
                    grouped_occ = self._group_occupation(occ_text)
                    if grouped_occ in grouped_occupation_counts:
                        grouped_occupation_counts[grouped_occ] += 1
                    else:
                        grouped_occupation_counts[grouped_occ] = 1
                    
                    # Track years for timeline information
                    year_info = occupation.get('year')
                    if year_info:
                        if grouped_occ not in occupation_years:
                            occupation_years[grouped_occ] = []
                        occupation_years[grouped_occ].append({
                            'year': year_info,
                            'individual': entry['individual'].name,
                            'original_occupation': occ_text
                        })
            
            # Display occupation counts first - show both grouped and original
            print(f"\n--- OCCUPATION SUMMARY ---")
            print(f"Total occupation entries found: {len(all_occupations)}")
            print(f"Unique original occupations: {len(occupation_counts)}")
            print(f"Unique grouped occupations: {len(grouped_occupation_counts)}")
            
            print(f"\n--- GROUPED OCCUPATION FREQUENCY ---")
            print("(Sorted by count, showing normalized occupation groups)")
            
            # Sort grouped occupations by count (descending), then by name
            sorted_grouped = sorted(grouped_occupation_counts.items(), key=lambda x: (-x[1], x[0]))
            
            for grouped_occ, count in sorted_grouped:
                print(f"  {grouped_occ}: {count}")
                
                # Show year range if available
                if grouped_occ in occupation_years:
                    years = [entry['year'] for entry in occupation_years[grouped_occ] if entry['year']]
                    if years:
                        min_year = min(years)
                        max_year = max(years)
                        if min_year == max_year:
                            print(f"    (Year: {min_year})")
                        else:
                            print(f"    (Years: {min_year}-{max_year})")
            
            print(f"\n--- ORIGINAL OCCUPATION FREQUENCY ---")
            print("(Sorted by count, showing exact text as found in records)")
            
            # Sort original occupations by count (descending), then by name
            sorted_occupations = sorted(occupation_counts.items(), key=lambda x: (-x[1], x[0]))
            
            for occupation, count in sorted_occupations:
                grouped_version = self._group_occupation(occupation)
                if grouped_version != occupation:
                    print(f"  {occupation}: {count} → {grouped_version}")
                else:
                    print(f"  {occupation}: {count}")
            
            # Ask if user wants to see individual breakdown
            show_individuals = input(f"\nShow breakdown by individual? (y/n): ").strip().lower()
            if show_individuals in ['y', 'yes']:
                print(f"\n--- INDIVIDUALS WITH OCCUPATIONS ---")
                
                # Sort by name for consistent display
                individuals_with_occupations.sort(key=lambda x: x['individual'].name or 'Unknown')
                
                for i, entry in enumerate(individuals_with_occupations, 1):
                    individual = entry['individual']
                    occupations = entry['occupations']
                    
                    # Display individual with number and compact birth/death years
                    birth_year = individual.birth_year or "?"
                    death_year = individual.death_year or "?"
                    year_range = f"({birth_year}-{death_year})"
                    
                    print(f"\n{i:3}. {individual.name} {year_range}")
                    print(f"     ID: {individual.xref_id}")
                    
                    # Display occupations indented with grouping information
                    for occupation in occupations:
                        original_occ = occupation['occupation']
                        grouped_occ = self._group_occupation(original_occ)
                        year_info = occupation.get('year')
                        source_info = occupation.get('source_info', '')
                        
                        # Build display string - prioritize year info
                        display_parts = []
                        if year_info:
                            display_parts.append(str(year_info))
                        if source_info:
                            display_parts.append(source_info)
                        
                        context_info = f" ({', '.join(display_parts)})" if display_parts else ""
                        
                        if grouped_occ != original_occ:
                            print(f"      • {original_occ} → {grouped_occ}{context_info}")
                        else:
                            print(f"      • {original_occ}{context_info}")
        else:
            print(f"\nNo occupation data found for any individuals in the current dataset.")
            print("This could mean:")
            print("  • The GEDCOM file doesn't contain occupation information")
            print("  • Occupation data is stored in a different format")
            print("  • Occupation data is embedded within other record types")
        
        # Clean up debug flag (if it exists)
        if hasattr(self, '_debug_occupation_extraction'):
            delattr(self, '_debug_occupation_extraction')
        
        print(f"\n{'='*60}")
        input("\nPress Enter to continue...")
    
    def _extract_occupations(self, individual) -> list:
        """
        Extract occupation information from an individual's record.
        
        Returns list of dictionaries with:
        - occupation: the occupation text
        - source_info: source and date information (if available)
        """
        occupations = []
        
        # First, try to use the enhanced get_occupations method from the Individual class
        if hasattr(individual, 'get_occupations'):
            try:
                enhanced_occupations = individual.get_occupations()
                if enhanced_occupations:
                    # Convert to the format expected by this method
                    for occ_data in enhanced_occupations:
                        occupation_text = occ_data.get('occupation', '').strip()
                        if occupation_text:
                            # Skip "private" - treat same as blank/not stated
                            if occupation_text.lower().strip() == 'private':
                                continue
                                
                            source_parts = []
                            
                            # Build source info
                            source_type = occ_data.get('source', '')
                            if source_type:
                                source_parts.append(source_type)
                            
                            date_info = occ_data.get('date')
                            if date_info:
                                source_parts.append(str(date_info))
                            
                            place_info = occ_data.get('place')
                            if place_info:
                                source_parts.append(str(place_info))
                            
                            # Extract year from date_info for timeline
                            year = None
                            if date_info:
                                # Try to extract year from various date formats
                                year_match = re.search(r'\b(1[8-9]\d{2}|20[0-2]\d)\b', str(date_info))
                                if year_match:
                                    year = int(year_match.group(1))
                            
                            occupation_data = {
                                'occupation': occupation_text,
                                'source_info': ', '.join(source_parts) if source_parts else None,
                                'year': year
                            }
                            occupations.append(occupation_data)
                    
                    # If we found occupations via the enhanced method, return them
                    if occupations:
                        return occupations
            except Exception as e:
                # If enhanced method fails, fall back to manual extraction
                pass
        
        # Fallback to manual extraction if enhanced method didn't work
        if hasattr(individual, 'raw_record') and individual.raw_record:
            debug_mode = hasattr(self, '_debug_occupation_extraction') and self._debug_occupation_extraction
            
            for sub in individual.raw_record.sub_records:
                if debug_mode:
                    try:
                        value_str = str(sub.value) if sub.value else "[no value]"
                        print(f"DEBUG: Found tag '{sub.tag}' with value: '{value_str[:100]}'")
                    except Exception as e:
                        print(f"DEBUG: Found tag '{sub.tag}' with value: [error: {e}]")
                
                # Look for occupation in multiple possible tags
                occupation_value = None
                try:
                    if sub.tag == 'OCCU' and sub.value:
                        occupation_value = str(sub.value).strip()
                    elif sub.tag == 'PROF' and sub.value:  # Profession
                        occupation_value = str(sub.value).strip()
                    elif sub.tag == 'TITL' and sub.value:  # Title (sometimes used for occupation)
                        occupation_value = str(sub.value).strip()
                    elif sub.tag.startswith('_') and 'OCCU' in sub.tag.upper() and sub.value:
                        occupation_value = str(sub.value).strip()
                    elif sub.tag == 'NOTE' and sub.value:
                        # Check NOTE fields for occupation data
                        note_text = str(sub.value).strip()
                        if 'occupation:' in note_text.lower():
                            # Parse "Occupation: Coal Miner Hewer; Marital Status: Single; ..."
                            parts = note_text.split(';')
                            for part in parts:
                                part = part.strip()
                                if part.lower().startswith('occupation:'):
                                    occupation_value = part[11:].strip()  # Remove "Occupation:" prefix
                                    break
                except Exception:
                    # Skip this tag if we can't convert to string
                    continue
                
                if occupation_value:
                    # Skip "private" - treat same as blank/not stated
                    if occupation_value.lower().strip() == 'private':
                        continue
                        
                    # Extract basic occupation
                    occupation_data = {
                        'occupation': occupation_value,
                        'source_info': None,
                        'year': None
                    }
                    
                    # Look for date and source information in sub-records
                    date_info = None
                    source_info = None
                    
                    try:
                        if hasattr(sub, 'sub_records'):
                            for sub2 in sub.sub_records:
                                if sub2.tag == 'DATE' and sub2.value:
                                    date_info = str(sub2.value).strip()
                                elif sub2.tag == 'SOUR' and sub2.value:
                                    # Source reference - might contain census or other source info
                                    source_info = str(sub2.value).strip()
                                elif sub2.tag == 'NOTE' and sub2.value:
                                    # Additional notes might contain source information
                                    if not source_info:
                                        source_info = str(sub2.value).strip()
                    except Exception:
                        # Skip sub-records if there are issues
                        pass
                    
                    # Extract year from date_info for timeline
                    if date_info:
                        year_match = re.search(r'\b(1[8-9]\d{2}|20[0-2]\d)\b', str(date_info))
                        if year_match:
                            occupation_data['year'] = int(year_match.group(1))
                    
                    # Build source info string
                    source_parts = []
                    if source_info:
                        source_parts.append(source_info)
                    if date_info:
                        source_parts.append(date_info)
                    
                    if source_parts:
                        occupation_data['source_info'] = ', '.join(source_parts)
                    
                    occupations.append(occupation_data)
                
                # Also check for occupations within census records or other events (including RESI)
                elif sub.tag in ['CENS', 'RESI', 'EVEN', 'FACT']:
                    try:
                        # Look for occupation within census or event records
                        event_occupation = None
                        event_date = None
                        event_source = None
                        
                        if hasattr(sub, 'sub_records'):
                            for sub2 in sub.sub_records:
                                if sub2.tag == 'OCCU' and sub2.value:
                                    event_occupation = str(sub2.value).strip()
                                elif sub2.tag == 'DATE' and sub2.value:
                                    event_date = str(sub2.value).strip()
                                elif sub2.tag == 'SOUR' and sub2.value:
                                    event_source = str(sub2.value).strip()
                                elif sub2.tag == 'NOTE' and sub2.value:
                                    # Check NOTE within events for occupation data
                                    note_text = str(sub2.value).strip()
                                    if 'occupation:' in note_text.lower():
                                        # Parse "Occupation: Coal Miner Hewer; Marital Status: Single; ..."
                                        parts = note_text.split(';')
                                        for part in parts:
                                            part = part.strip()
                                            if part.lower().startswith('occupation:'):
                                                event_occupation = part[11:].strip()  # Remove "Occupation:" prefix
                                                break
                                elif sub2.tag == 'TYPE' and sub2.value:
                                    type_value = str(sub2.value).strip().lower()
                                    if type_value in ['census', 'occupation']:
                                        # This might be an occupation event
                                        if sub.value:
                                            event_occupation = str(sub.value).strip()
                        
                        if event_occupation:
                            # Skip "private" - treat same as blank/not stated
                            if event_occupation.lower().strip() == 'private':
                                continue
                                
                            occupation_data = {
                                'occupation': event_occupation,
                                'source_info': None,
                                'year': None
                            }
                            
                            # Extract year from event_date for timeline
                            if event_date:
                                year_match = re.search(r'\b(1[8-9]\d{2}|20[0-2]\d)\b', str(event_date))
                                if year_match:
                                    occupation_data['year'] = int(year_match.group(1))
                            
                            # Build source info for event-based occupation
                            source_parts = []
                            if event_source:
                                source_parts.append(event_source)
                            if event_date:
                                source_parts.append(event_date)
                            elif sub.tag == 'CENS':
                                source_parts.append('Census')
                            elif sub.tag == 'RESI':
                                source_parts.append('Residence')
                            
                            if source_parts:
                                occupation_data['source_info'] = ', '.join(source_parts)
                            
                            occupations.append(occupation_data)
                    except Exception:
                        # Skip this event record if there are issues
                        continue
        
        return occupations


class DataQueryHandler:
    """Handles data management operations."""
    
    def __init__(self, database: GedcomDB):
        self.database = database
