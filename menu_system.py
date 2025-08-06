"""
Menu system for the Family Tree Analyser v2.
Dynamically builds menu options based on available database capabilities.
"""

from typing import Dict, List, Tuple, Optional, Callable
from gedcom_db import GedcomDB, Individual
from ged4py_db import Ged4PyGedcomDB
from query_handlers import SearchQueryHandler, ValidityQueryHandler, ReportQueryHandler, DataQueryHandler


class MenuOption:
    """Represents a single menu option."""
    
    def __init__(self, key: str, description: str, handler: Callable, 
                 category: str = "general", required_capabilities: List[str] = None):
        self.key = key
        self.description = description
        self.handler = handler
        self.category = category
        self.required_capabilities = required_capabilities or []
    
    def is_available(self, database: GedcomDB) -> bool:
        """Check if this option is available given the database capabilities."""
        return all(database.supports(cap) for cap in self.required_capabilities)


class MenuCategory:
    """Represents a category of menu options."""
    
    def __init__(self, name: str, description: str, key: str):
        self.name = name
        self.description = description
        self.key = key
        self.options: List[MenuOption] = []


class MenuSystem:
    """Manages the interactive menu system with categorized options."""
    
    def __init__(self, database: GedcomDB):
        self.database = database
        self.categories: Dict[str, MenuCategory] = {}
        self.options: Dict[str, MenuOption] = {}
        self.ancestor_filter_ids: Optional[set] = None
        self.current_category: Optional[str] = None
        
        # Store ancestor filtering state for switching between modes
        self.root_ancestor = None
        self.filtering_mode: Optional[str] = None  # 'direct' or 'relations'
        self.tree_constraints = None  # Store birth year constraints
        
        # Initialize query handlers
        self.search_handler = SearchQueryHandler(database)
        self.validity_handler = ValidityQueryHandler(database)
        self.report_handler = ReportQueryHandler(database)
        self.data_handler = DataQueryHandler(database)
        
        self._setup_categories()
        self._register_menu_options()
    
    def update_validity_handler_context(self):
        """Update validity handler with current context (like ancestor filtering)."""
        self.validity_handler.set_ancestor_filter(self.ancestor_filter_ids)
        self.search_handler.set_ancestor_filter(self.ancestor_filter_ids)
        self.report_handler.set_ancestor_filter(self.ancestor_filter_ids)

        if hasattr(self, "database"):
            self.database.ancestor_filter_ids = self.ancestor_filter_ids
    
    def _setup_categories(self):
        """Initialize menu categories."""
        self.categories = {
            "v": MenuCategory("Validity Tests", 
                                   "Data quality and consistency checks", "v"),
            "s": MenuCategory("Search & Navigation", 
                                 "Find individuals and set analysis scope", "s"),
            "r": MenuCategory("Analysis Reports", 
                                 "Generate statistics and analysis reports", "r"),
            "d": MenuCategory("Data Management", 
                               "Import, export, and modify data", "d")
        }

    def switch_gedcom_file(self):
        """Switch to a different GEDCOM file."""
        print("\n" + "="*50)
        print("SWITCH GEDCOM FILE")
        print("="*50)
        
        # Warn about ancestor filter reset
        if self.ancestor_filter_ids:
            print("⚠️  WARNING: You currently have a root ancestor filter active.")
            print("   This will be reset when switching files as the person may not")
            print("   exist in the new file.")
            print()
            
            confirm = input("Continue with file switch? (y/N): ").strip().lower()
            if confirm != 'y':
                print("File switch cancelled.")
                return
        
        # Load new file
        if self.database.load_file():
            # Reset ancestor filter state
            self.ancestor_filter_ids = None
            self.root_ancestor = None
            self.filtering_mode = None
            self.tree_constraints = None
            self.update_validity_handler_context()
            
            print("\n✓ GEDCOM file switched successfully!")
            input("\nPress Enter to continue...")
        else:
            print("Failed to switch GEDCOM file.")
            input("\nPress Enter to continue...")

    def _register_menu_options(self):
        """Register all available menu options organized by category."""
        
        # Note: Handlers are placeholders for now - will be implemented later
        
        # === VALIDITY TESTS ===
        self._add_option("1", "Show individuals with negative ages", 
                        self.validity_handler.find_individuals_with_negative_ages, "v", ["read", "dates"])
        
        self._add_option("2", "Show orphaned individuals (no family connections)", 
                        self.validity_handler.find_orphaned_individuals, "v", ["read", "relationships"])
        
        self._add_option("3", "To Do - Show individuals with missing critical data", 
                        self._placeholder_handler, "v", ["read"])
        
        self._add_option("4", "To Do - Show individuals with duplicate names/dates", 
                        self._placeholder_handler, "v", ["read"])

        self._add_option("5", "Show individuals with no gender specified",
                        self.validity_handler.find_individuals_with_no_gender, "v", ["read"])

        self._add_option("6", "Show individuals not in current tree",
                        self.validity_handler.find_individuals_not_in_ancestry_tree, "v", ["read"])

        self._add_option("7", "Show individuals who lived past a specific age",
                        self.validity_handler.find_individuals_who_lived_past_age, "v", ["read", "dates"])

        self._add_option("8", "Check parents who died before children were born",
                        self.validity_handler.check_parents_died_before_children_born, "v", ["read", "dates"])

        
        # === SEARCH & NAVIGATION ===
        self._add_option("1", "Find individual by name", 
                        self.search_handler.find_individual_by_name, "s", ["read", "search"])
        
        self._add_option("2", "To Do - Show recent ancestors of a person", 
                        self._placeholder_handler, "s", ["read", "relationships"])
        
        self._add_option("3", "To Do - Clear ancestor filter (analyze all individuals)", 
                        self._placeholder_handler, "s", ["read"])

        self._add_option("4", "Show tree of descendants", 
                        self.search_handler.show_descendant_tree, "s", ["read", "relationships"])

        # === ANALYSIS REPORTS ===
        self._add_option("1", "Birth place analysis (nations summary)", 
                        self.report_handler.analyze_birth_places_summary, "r", ["read", "places"])
        
        self._add_option("2", "Birth place analysis (detailed breakdown)", 
                        self.report_handler.analyze_birth_places_detailed, "r", ["read", "places"])
        
        self._add_option("3", "Occupation analysis and counts", 
                        self.report_handler.analyze_occupations, "r", ["read", "occupations"])
        
        self._add_option("4", "Oldest individuals (by birth year)", 
                        self.report_handler.analyse_oldest_individuals, "r", ["read", "dates"])

        self._add_option("5", "Plot birth places on map", self.plot_birth_places_menu, "r", ["read", "places"])

        self._add_option("6", "Analyse age ranges", 
                        self.database.analyse_years_lived, "r", ["read", "dates"])

        self._add_option("7", "Scan all census sources for occupation-like data",
                        self.database.scan_census_sources_for_occupations, "r", ["read", "occupations"])

        self._add_option("8", "Dump all data from wedding (marriage) records", 
                         self.database.dump_wedding_records, "r", ["read", "marriage"])

        self._add_option("9", "Analyse ages from wedding records", 
                         self.database.analyse_wedding_ages, "r", ["read", "marriage"])
        
        
        # === DATA MANAGEMENT ===
        self._add_option("1", "To Do - Export analysis results to file", 
                        self._placeholder_handler, "d", ["read", "export"])
        
        self._add_option("2", "To Do - Save corrected GEDCOM file", 
                        self._placeholder_handler, "d", ["read", "write"])
        
        self._add_option("3", "To Do - Import additional data", 
                        self._placeholder_handler, "d", ["read", "write"])

        self._add_option("4", "Clear geocoding cache", 
                        self.database.clear_geocoding_cache, "d", ["read"])

        self._add_option("5", "Test single address geocoding", 
                        self.database.test_single_address_mapping, "d", ["read"])

    def _add_option(self, key: str, description: str, handler: Callable, 
                   category: str, required_capabilities: List[str]):
        """Add a menu option to the specified category."""
        option = MenuOption(key, description, handler, category, required_capabilities)
        
        # Create composite key for global lookup
        composite_key = f"{category}:{key}"
        self.options[composite_key] = option
        
        # Add to category
        if category in self.categories:
            self.categories[category].options.append(option)
    
    def get_available_categories(self) -> List[MenuCategory]:
        """Get list of categories that have available options."""
        available_categories = []
        
        for category in self.categories.values():
            # Check if category has any available options
            available_options = [opt for opt in category.options 
                               if opt.is_available(self.database) and 
                               self._is_option_contextually_available(opt)]
            
            if available_options:
                available_categories.append(category)
        
        return available_categories
    
    def get_available_options_in_category(self, category_key: str) -> List[MenuOption]:
        """Get list of options available in a specific category."""
        if category_key not in self.categories:
            return []
        
        category = self.categories[category_key]
        available = []
        
        for option in category.options:
            if (option.is_available(self.database) and 
                self._is_option_contextually_available(option)):
                available.append(option)
        
        return available
    
    def _is_option_contextually_available(self, option: MenuOption) -> bool:
        """Check if option is available in current context (e.g., ancestor filtering)."""
        # Special case: orphaned individuals not available when filtering by ancestors
        if (option.description.lower().find("orphaned") != -1 and 
            self.ancestor_filter_ids is not None):
            return False
        
        return True
    
    def display_main_menu(self):
        """Display the main category selection menu."""
        available_categories = self.get_available_categories()
        
        if not available_categories:
            print("No menu categories available for the current database.")
            return
        
        print("\n" + "="*50)
        print("Family Tree Analyser v2 - Main Menu")
        print("="*50)
        
        # Show the root ancestor option first
        if self.ancestor_filter_ids:
            print("a. (Re)Set Root Ancestor - Reset or change current ancestor filter")
        else:
            print("a. (Re)Set Root Ancestor - Filter analysis to specific ancestor lineage")
        
        print("f. Switch GEDCOM file")  # Add this line
        print()
        
        for category in available_categories:
            option_count = len(self.get_available_options_in_category(category.key))
            print(f"{category.key}. {category.name} ({option_count} options)")
            print(f"   {category.description}")
        
        # Show current state
        if self.ancestor_filter_ids:
            print(f"\nCurrently filtering to {len(self.ancestor_filter_ids)} ancestors.")
        else:
            print(f"\nAnalyzing all individuals in database.")
        
        # Show database info
        caps = sorted(self.database.capabilities)
        print(f"Database: {type(self.database).__name__} | Capabilities: {', '.join(caps)}")
    
    def display_category_menu(self, category_key: str):
        """Display options within a specific category."""
        if category_key not in self.categories:
            print(f"Unknown category: {category_key}")
            return
        
        category = self.categories[category_key]
        available_options = self.get_available_options_in_category(category_key)
        
        if not available_options:
            print(f"No options available in {category.name}.")
            return
        
        print(f"\n--- {category.name} ---")
        print(f"{category.description}")
        print()
        
        for option in available_options:
            print(f"{option.key}. {option.description}")
        
        print("\nb. Back to main menu")
    
    def display_menu(self):
        """Display the current menu (main or category)."""
        if self.current_category is None:
            self.display_main_menu()
        else:
            self.display_category_menu(self.current_category)
    
    def handle_choice(self, choice: str) -> bool:
        """Handle user menu choice. Returns True to continue, False to exit."""
        choice = choice.lower().strip()
        
        if choice in ['q', 'quit', 'exit']:
            return False
        
        # Handle navigation
        if self.current_category is None:
            # Main menu - category selection or special commands
            if choice == 'a':
                # Handle (Re)Set Root Ancestor
                self._handle_set_root_ancestor()
                return True
            elif choice == 'f':  # Add this elif block
                # Handle Switch GEDCOM file
                self.switch_gedcom_file()
                return True
            elif choice in self.categories:
                self.current_category = choice
                return True
            else:
                print(f"Invalid choice: '{choice}'")
                return True
        else:
            # Category menu
            if choice == 'b':
                self.current_category = None
                return True
            
            # Look for option in current category
            composite_key = f"{self.current_category}:{choice}"
            if composite_key in self.options:
                option = self.options[composite_key]
                if (option.is_available(self.database) and 
                    self._is_option_contextually_available(option)):
                    try:
                        # Update validity handler with current context
                        self.update_validity_handler_context()
                        option.handler()
                    except Exception as e:
                        print(f"Error executing option: {e}")
                else:
                    print(f"Option '{choice}' is not available with the current database.")
            else:
                print(f"Invalid choice: '{choice}'")
        
        return True
    
    def run(self):
        """Main menu loop."""
        print(f"Family Tree Analyser v2")
        print(f"Using database: {type(self.database).__name__}")
        print(f"File: {self.database.file_path or 'Not loaded'}")
        
        if not self.database.is_loaded:
            print("Warning: No GEDCOM file loaded.")
        
        while True:
            self.display_menu()
            
            if self.current_category is None:
                choice = input(f"\nChoose a category, 'a' for ancestor filtering, 'f' to switch files (or 'q' to quit): ").strip()
            else:
                choice = input(f"\nChoose an option (1-9, 'b' for back, 'q' to quit): ").strip()
            
            if not self.handle_choice(choice):
                break
        
        print("Exiting Family Tree Analyser.")
    
    def _handle_set_root_ancestor(self):
        """Handle the (Re)Set Root Ancestor functionality."""
        while True:
            print("\n--- (Re)Set Root Ancestor ---")
            
            # If already filtering, offer enhanced options
            if self.ancestor_filter_ids:
                current_mode = "direct ancestors only" if self.filtering_mode == 'direct' else "ancestors and their relations"
                alternate_mode = "ancestors and their relations" if self.filtering_mode == 'direct' else "direct ancestors only"
                
                print(f"Currently filtering to {len(self.ancestor_filter_ids)} {current_mode}.")
                if self.root_ancestor:
                    print(f"Root ancestor: {self.root_ancestor.name}")
                
                print("\nOptions:")
                print("1. Reset to full database (clear ancestor filter)")
                print(f"2. Switch to {alternate_mode}")
                print("3. Set new root ancestor")
                print("b. Back to main menu")
                
                choice = input("\nChoose option (1-3, or 'b' to go back): ").strip().lower()
                
                if choice == '1':
                    # Clear all ancestor filter state
                    self.ancestor_filter_ids = None
                    self.root_ancestor = None
                    self.filtering_mode = None
                    self.tree_constraints = None
                    self.update_validity_handler_context()
                    print("\n✅ Ancestor filter cleared. Now analyzing all individuals in database.")
                    input("\nPress Enter to continue...")
                    continue  # Stay in menu
                elif choice == '2':
                    # Toggle filtering mode using stored root ancestor and constraints
                    if self.root_ancestor and self.tree_constraints:
                        new_mode = 'relations' if self.filtering_mode == 'direct' else 'direct'
                        self._apply_filtering_mode(self.root_ancestor, self.tree_constraints, new_mode)
                        continue  # Stay in menu
                    else:
                        print("⚠ Cannot switch mode: root ancestor or constraints not stored.")
                        input("\nPress Enter to continue...")
                        continue  # Stay in menu
                elif choice == '3':
                    # Set new root ancestor - continue to full selection process
                    if self._set_new_root_ancestor():
                        continue  # Stay in menu after successful set
                    else:
                        continue  # Stay in menu after cancelled/failed set
                elif choice == 'b':
                    return  # Back to main menu
                else:
                    print("Invalid choice.")
                    input("\nPress Enter to continue...")
                    continue  # Stay in menu
            else:
                # No current filter - show main filtering options
                print("\nAncestor filtering options:")
                print("1. Set new root ancestor filter")
                print("2. View current filter status")
                print("b. Back to main menu")
                
                choice = input("\nChoose option (1-2, or 'b' to go back): ").strip().lower()
                
                if choice == '1':
                    # Set new root ancestor - continue to full selection process
                    if self._set_new_root_ancestor():
                        continue  # Stay in menu after successful set
                    else:
                        continue  # Stay in menu after cancelled/failed set
                elif choice == '2':
                    print(f"\nCurrent filter status: No ancestor filter applied")
                    print("All individuals in the database are included in analysis.")
                    input("\nPress Enter to continue...")
                    continue  # Stay in menu
                elif choice == 'b':
                    return  # Back to main menu
                else:
                    print("Invalid choice.")
                    input("\nPress Enter to continue...")
                    continue  # Stay in menu
    
    def _set_new_root_ancestor(self) -> bool:
        """Handle the process of setting a new root ancestor. Returns True if successful, False if cancelled."""
        
        # Step 1: Get root ancestor name
        print("\nSelect a root ancestor to filter analysis.")
        name = input("Enter name to search for: ").strip()
        if not name:
            print("No name entered.")
            input("\nPress Enter to continue...")
            return False
        
        # Step 2: Get birth year range for finding the root ancestor
        print(f"\nEnter birth year range to find the root ancestor '{name}':")
        print("(Press Enter for open-ended constraints)")
        
        start_year_str = input("Earliest birth year for root ancestor: ").strip()
        end_year_str = input("Latest birth year for root ancestor: ").strip()
        
        # Parse birth year constraints for root ancestor search
        start_year = None
        end_year = None
        
        try:
            if start_year_str:
                start_year = int(start_year_str)
        except ValueError:
            print(f"Invalid start year format '{start_year_str}'. Using open-ended start.")
            start_year = None
            
        try:
            if end_year_str:
                end_year = int(end_year_str)
        except ValueError:
            print(f"Invalid end year format '{end_year_str}'. Using open-ended end.")
            end_year = None
        
        # Handle case where end date is before start date
        if start_year and end_year and end_year < start_year:
            print(f"Note: End year ({end_year}) is before start year ({start_year}). Swapping them.")
            start_year, end_year = end_year, start_year
        
        # Step 3: Search for individuals matching name and birth year range
        if hasattr(self.database, 'search_individuals_advanced'):
            results = self.database.search_individuals_advanced(
                name=name,
                exact_match=False,
                min_birth_year=start_year,
                max_birth_year=end_year,
                min_death_year=None,
                max_death_year=None
            )
        else:
            print("Search not supported by this database.")
            input("\nPress Enter to continue...")
            return False
        
        # Handle search results
        if not results:
            constraint_msg = ""
            if start_year or end_year:
                constraints = []
                if start_year:
                    constraints.append(f"born >= {start_year}")
                if end_year:
                    constraints.append(f"born <= {end_year}")
                constraint_msg = f" with birth year constraints: {' and '.join(constraints)}"
            
            print(f"\nNo individuals found matching '{name}'{constraint_msg}.")
            input("\nPress Enter to continue...")
            return False
        
        # Step 3: Handle selection based on number of matches
        selected_ancestor = None
        
        if len(results) == 1:
            # Single match - show and ask for confirmation
            individual = results[0]
            birth_year = individual.birth_year or "Unknown"
            death_year = individual.death_year or "Unknown"
            
            print(f"\nFound 1 matching individual:")
            print(f"  Name: {individual.name}")
            print(f"  Birth: {birth_year} | Death: {death_year}")
            print(f"  ID: {individual.xref_id}")
            
            choice = input(f"\nUse '{individual.name}' as root ancestor? (y/n): ").strip().lower()
            if choice in ['y', 'yes']:
                selected_ancestor = individual
            else:
                print("Selection cancelled.")
                input("\nPress Enter to continue...")
                return False
        else:
            # Multiple matches - show list and ask for selection
            print(f"\nFound {len(results)} matching individuals:")
            for i, individual in enumerate(results, 1):
                birth_year = individual.birth_year or "Unknown"
                death_year = individual.death_year or "Unknown"
                print(f"{i:3}. {individual.name}")
                print(f"     Birth: {birth_year} | Death: {death_year}")
                print(f"     ID: {individual.xref_id}")
                print()
            
            choice = input(f"Select root ancestor by number (1-{len(results)}, or Enter to cancel): ").strip()
            if not choice:
                print("Selection cancelled.")
                input("\nPress Enter to continue...")
                return False
            
            try:
                index = int(choice) - 1
                if 0 <= index < len(results):
                    selected_ancestor = results[index]
                else:
                    print(f"Invalid selection. Please choose 1-{len(results)}.")
                    input("\nPress Enter to continue...")
                    return False
            except ValueError:
                print("Invalid input. Please enter a number.")
                input("\nPress Enter to continue...")
                return False
        
        # Step 4: Get tree constraints (separate from root ancestor constraints)
        print(f"\nSelected root ancestor: {selected_ancestor.name}")
        print(f"\nNow set constraints for the family tree analysis:")
        tree_min_year, tree_max_year = self._get_birth_year_constraints()
        
        # Get filtering type
        print(f"\nChoose filtering type:")
        print("1. Direct ancestors only")
        print("   (Include only the root person and their direct ancestral line)")
        print("2. Direct ancestors and their relations")
        print("   (Include ancestors plus siblings, spouses, and children of ancestors)")
        
        filter_choice = input("\nChoose filtering type (1-2): ").strip()
        
        if filter_choice == '1':
            filtering_mode = 'direct'
        elif filter_choice == '2':
            filtering_mode = 'relations'
        else:
            print("Invalid choice.")
            input("\nPress Enter to continue...")
            return False
        
        # Store the ancestor information for future mode switching
        self.root_ancestor = selected_ancestor
        self.tree_constraints = (tree_min_year, tree_max_year)
        
        # Apply the selected filtering mode
        self._apply_filtering_mode(selected_ancestor, (tree_min_year, tree_max_year), filtering_mode)
        
        return True  # Successfully set new root ancestor
    
    def _apply_filtering_mode(self, selected_ancestor, tree_constraints, filtering_mode):
        """Apply the specified filtering mode using stored ancestor and constraints."""
        tree_min_year, tree_max_year = tree_constraints
        
        if filtering_mode == 'direct':
            # Direct ancestors only
            ancestor_ids = self._get_direct_ancestors_with_constraints(selected_ancestor, tree_min_year, tree_max_year)
            filter_type = "Direct ancestors only"
        elif filtering_mode == 'relations':
            # Direct ancestors and their relations
            ancestor_ids = self._get_ancestors_and_relations_with_constraints(selected_ancestor, tree_min_year, tree_max_year)
            filter_type = "Direct ancestors and their relations"
        else:
            print(f"⚠ Unknown filtering mode: {filtering_mode}")
            return
        
        # Store the current filtering mode
        self.filtering_mode = filtering_mode
        
        # Apply the filter
        self.ancestor_filter_ids = ancestor_ids
        self.update_validity_handler_context()
        
        # Display confirmation with final summary
        print(f"\n✅ Ancestor filter applied successfully!")
        print(f"Root ancestor: {selected_ancestor.name}")
        print(f"Filter type: {filter_type}")
        self._display_birth_year_summary(tree_min_year, tree_max_year)
        print(f"Total ancestors included in analysis: {len(ancestor_ids)}")
        
        input("\nPress Enter to continue...")
    
    def _get_direct_ancestors_with_constraints(self, root_person, min_birth_year: Optional[int], 
                                             max_birth_year: Optional[int]) -> set:
        """Get direct ancestors with birth year constraints applied."""
        ancestor_ids = set()
        ancestors_to_process = [root_person]
        
        while ancestors_to_process:
            current_person = ancestors_to_process.pop(0)
            
            # Apply birth year filter
            birth_year = current_person.birth_year
            if birth_year is None:
                # Exclude individuals with no birth year data
                continue
            
            if min_birth_year and birth_year < min_birth_year:
                continue
            
            if max_birth_year and birth_year > max_birth_year:
                continue
            
            # Add to ancestor set
            ancestor_ids.add(current_person.xref_id)
            
            # Use fast lookup if available
            if hasattr(self.database, 'get_parents_fast') and self.database._indexes_built:
                parents = self.database.get_parents_fast(current_person.xref_id)
            else:
                # Fallback to slow method - find parents through FAMC (Family as Child)
                parents = []
                if hasattr(current_person, 'raw_record') and current_person.raw_record:
                    for sub in current_person.raw_record.sub_records:
                        if sub.tag == 'FAMC':
                            family_id = str(sub.value)
                            parents.extend(self._get_parents_from_family(family_id))
            
            for parent in parents:
                if parent.xref_id not in ancestor_ids:
                    ancestors_to_process.append(parent)
        
        return ancestor_ids
    
    def _get_ancestors_and_relations_with_constraints(self, root_person, min_birth_year: Optional[int], 
                                                    max_birth_year: Optional[int]) -> set:
        """Get direct ancestors plus their relations with birth year constraints applied."""
        # Start with direct ancestors (with constraints)
        ancestor_ids = self._get_direct_ancestors_with_constraints(root_person, min_birth_year, max_birth_year)
        extended_ids = set(ancestor_ids)
        
        # For each direct ancestor, add their relations (also with constraints)
        if hasattr(self.database, '_indexes_built') and self.database._indexes_built:
            # Use fast lookups
            for individual_id in ancestor_ids:
                # Add siblings
                siblings = self.database.get_siblings_fast(individual_id)
                filtered_siblings = self._apply_birth_year_filter(siblings, min_birth_year, max_birth_year)
                for sibling in filtered_siblings:
                    extended_ids.add(sibling.xref_id)
                
                # Add spouses
                spouses = self.database.get_spouses_fast(individual_id)
                filtered_spouses = self._apply_birth_year_filter(spouses, min_birth_year, max_birth_year)
                for spouse in filtered_spouses:
                    extended_ids.add(spouse.xref_id)
                
                # Add children
                children = self.database.get_children_fast(individual_id)
                filtered_children = self._apply_birth_year_filter(children, min_birth_year, max_birth_year)
                for child in filtered_children:
                    extended_ids.add(child.xref_id)
        else:
            # Fallback to slow method
            all_individuals = self.database.get_all_individuals()
            for individual in all_individuals:
                if individual.xref_id in ancestor_ids:
                    # Add siblings (people with same parents)
                    siblings = self._get_siblings(individual)
                    filtered_siblings = self._apply_birth_year_filter(siblings, min_birth_year, max_birth_year)
                    for sibling in filtered_siblings:
                        extended_ids.add(sibling.xref_id)
                    
                    # Add spouses
                    spouses = self._get_spouses(individual)
                    filtered_spouses = self._apply_birth_year_filter(spouses, min_birth_year, max_birth_year)
                    for spouse in filtered_spouses:
                        extended_ids.add(spouse.xref_id)
                    
                    # Add children
                    children = self._get_children(individual)
                    filtered_children = self._apply_birth_year_filter(children, min_birth_year, max_birth_year)
                    for child in filtered_children:
                        extended_ids.add(child.xref_id)
        
        return extended_ids

    def _get_direct_ancestors(self, root_person) -> set:
        """Get direct ancestors only (root person + parents, grandparents, etc.)."""
        ancestor_ids = set()
        ancestors_to_process = [root_person]
        
        while ancestors_to_process:
            current_person = ancestors_to_process.pop(0)
            ancestor_ids.add(current_person.xref_id)
            
            # Use fast lookup if available
            if hasattr(self.database, 'get_parents_fast') and self.database._indexes_built:
                parents = self.database.get_parents_fast(current_person.xref_id)
            else:
                # Fallback to slow method - find parents through FAMC (Family as Child)
                parents = []
                if hasattr(current_person, 'raw_record') and current_person.raw_record:
                    for sub in current_person.raw_record.sub_records:
                        if sub.tag == 'FAMC':
                            family_id = str(sub.value)
                            parents.extend(self._get_parents_from_family(family_id))
            
            for parent in parents:
                if parent.xref_id not in ancestor_ids:
                    ancestors_to_process.append(parent)
        
        return ancestor_ids
    
    def _get_ancestors_and_relations(self, root_person) -> set:
        """Get direct ancestors plus their siblings, spouses, and children."""
        # Start with direct ancestors
        ancestor_ids = self._get_direct_ancestors(root_person)
        extended_ids = set(ancestor_ids)
        
        # For each direct ancestor, add their relations
        if hasattr(self.database, '_indexes_built') and self.database._indexes_built:
            # Use fast lookups
            for individual_id in ancestor_ids:
                # Add siblings
                siblings = self.database.get_siblings_fast(individual_id)
                for sibling in siblings:
                    extended_ids.add(sibling.xref_id)
                
                # Add spouses
                spouses = self.database.get_spouses_fast(individual_id)
                for spouse in spouses:
                    extended_ids.add(spouse.xref_id)
                
                # Add children
                children = self.database.get_children_fast(individual_id)
                for child in children:
                    extended_ids.add(child.xref_id)
        else:
            # Fallback to slow method
            all_individuals = self.database.get_all_individuals()
            for individual in all_individuals:
                if individual.xref_id in ancestor_ids:
                    # Add siblings (people with same parents)
                    siblings = self._get_siblings(individual)
                    for sibling in siblings:
                        extended_ids.add(sibling.xref_id)
                    
                    # Add spouses
                    spouses = self._get_spouses(individual)
                    for spouse in spouses:
                        extended_ids.add(spouse.xref_id)
                    
                    # Add children
                    children = self._get_children(individual)
                    for child in children:
                        extended_ids.add(child.xref_id)
        
        return extended_ids
    
    def _get_parents_from_family(self, family_id: str) -> List:
        """Get parents from a family ID."""
        if hasattr(self.database, '_family_members') and self.database._indexes_built:
            # Use fast lookup if available
            family_members = self.database._family_members.get(family_id, {})
            parent_ids = family_members.get('parents', set())
            return [self.database._individual_index[pid] for pid in parent_ids 
                   if pid in self.database._individual_index]
        else:
            # Fallback to slow method
            parents = []
            all_individuals = self.database.get_all_individuals()
            
            for person in all_individuals:
                if hasattr(person, 'raw_record') and person.raw_record:
                    for sub in person.raw_record.sub_records:
                        if sub.tag == 'FAMS' and str(sub.value) == family_id:
                            parents.append(person)
            
            return parents
    
    def _get_siblings(self, individual) -> List:
        """Get siblings of an individual (people with same parents)."""
        if hasattr(self.database, 'get_siblings_fast') and self.database._indexes_built:
            # Use fast lookup if available
            return self.database.get_siblings_fast(individual.xref_id)
        else:
            # Fallback to slow method
            siblings = []
            
            # Find families where this person is a child
            child_families = []
            if hasattr(individual, 'raw_record') and individual.raw_record:
                for sub in individual.raw_record.sub_records:
                    if sub.tag == 'FAMC':
                        child_families.append(str(sub.value))
            
            # Find other children in those families
            all_individuals = self.database.get_all_individuals()
            for person in all_individuals:
                if person.xref_id != individual.xref_id:  # Don't include self
                    if hasattr(person, 'raw_record') and person.raw_record:
                        for sub in person.raw_record.sub_records:
                            if sub.tag == 'FAMC' and str(sub.value) in child_families:
                                siblings.append(person)
                                break
            
            return siblings
    
    def _get_spouses(self, individual) -> List:
        """Get spouses of an individual."""
        if hasattr(self.database, 'get_spouses_fast') and self.database._indexes_built:
            # Use fast lookup if available
            return self.database.get_spouses_fast(individual.xref_id)
        else:
            # Fallback to slow method
            spouses = []
            
            # Find families where this person is a spouse
            spouse_families = []
            if hasattr(individual, 'raw_record') and individual.raw_record:
                for sub in individual.raw_record.sub_records:
                    if sub.tag == 'FAMS':
                        spouse_families.append(str(sub.value))
            
            # Find other spouses in those families
            all_individuals = self.database.get_all_individuals()
            for person in all_individuals:
                if person.xref_id != individual.xref_id:  # Don't include self
                    if hasattr(person, 'raw_record') and person.raw_record:
                        for sub in person.raw_record.sub_records:
                            if sub.tag == 'FAMS' and str(sub.value) in spouse_families:
                                spouses.append(person)
                                break
            
            return spouses
    
    def _get_children(self, individual) -> List:
        """Get children of an individual."""
        if hasattr(self.database, 'get_children_fast') and self.database._indexes_built:
            # Use fast lookup if available
            return self.database.get_children_fast(individual.xref_id)
        else:
            # Fallback to slow method
            children = []
            
            # Find families where this person is a spouse/parent
            parent_families = []
            if hasattr(individual, 'raw_record') and individual.raw_record:
                for sub in individual.raw_record.sub_records:
                    if sub.tag == 'FAMS':
                        parent_families.append(str(sub.value))
            
            # Find children in those families
            all_individuals = self.database.get_all_individuals()
            for person in all_individuals:
                if hasattr(person, 'raw_record') and person.raw_record:
                    for sub in person.raw_record.sub_records:
                        if sub.tag == 'FAMC' and str(sub.value) in parent_families:
                            children.append(person)
                            break
            
            return children

    def _get_birth_year_constraints(self) -> Tuple[Optional[int], Optional[int]]:
        """
        Get optional birth year constraints from user.
        Returns tuple of (min_birth_year, max_birth_year).
        Both can be None if no constraint provided.
        """
        print("\nBirth year constraints (optional - press Enter to skip):")
        
        # Get minimum birth year
        min_birth_str = input("Exclude ancestors born before year (e.g., 1776): ").strip()
        min_birth_year = None
        if min_birth_str:
            try:
                min_birth_year = int(min_birth_str)
            except ValueError:
                print(f"Invalid year format '{min_birth_str}'. Ignoring minimum constraint.")
                min_birth_year = None
        
        # Get maximum birth year
        max_birth_str = input("Exclude ancestors born after year (e.g., 1900): ").strip()
        max_birth_year = None
        if max_birth_str:
            try:
                max_birth_year = int(max_birth_str)
            except ValueError:
                print(f"Invalid year format '{max_birth_str}'. Ignoring maximum constraint.")
                max_birth_year = None
        
        # Validate constraints
        if min_birth_year and max_birth_year and min_birth_year > max_birth_year:
            print(f"Warning: Minimum year ({min_birth_year}) is after maximum year ({max_birth_year}).")
            print("This will result in no ancestors being selected.")
        
        return min_birth_year, max_birth_year
    
    def _apply_birth_year_filter(self, individuals: List, min_birth_year: Optional[int], 
                                max_birth_year: Optional[int]) -> List:
        """
        Filter a list of individuals by birth year constraints.
        Individuals with no birth year data are excluded.
        
        Args:
            individuals: List of Individual objects to filter
            min_birth_year: Minimum birth year (inclusive), or None for no minimum
            max_birth_year: Maximum birth year (inclusive), or None for no maximum
            
        Returns:
            Filtered list of individuals
        """
        if not min_birth_year and not max_birth_year:
            # No constraints - return individuals that have birth years
            return [ind for ind in individuals if ind.birth_year is not None]
        
        filtered = []
        for individual in individuals:
            birth_year = individual.birth_year
            
            # Exclude individuals with no birth year data
            if birth_year is None:
                continue
            
            # Check minimum constraint
            if min_birth_year and birth_year < min_birth_year:
                continue
            
            # Check maximum constraint
            if max_birth_year and birth_year > max_birth_year:
                continue
            
            filtered.append(individual)
        
        return filtered
    
    def _display_birth_year_summary(self, min_birth_year: Optional[int], max_birth_year: Optional[int]):
        """Display a summary of applied birth year constraints."""
        constraints = []
        if min_birth_year:
            constraints.append(f"born >= {min_birth_year}")
        if max_birth_year:
            constraints.append(f"born <= {max_birth_year}")
        
        if constraints:
            print(f"Birth year constraints: {' and '.join(constraints)}")
        else:
            print("Birth year constraints: None (excluding individuals with no birth year data)")

    def plot_birth_places_menu(self):
        """Menu for birth place mapping options - delegates to database."""
        # Simply call the database method
        self.database.plot_birth_places_menu()

    def _placeholder_handler(self):
        """Placeholder handler for menu options - to be replaced with actual implementations."""
        print("This feature is not yet implemented in v2.")
        print("Functionality will be added in subsequent development phases.")
