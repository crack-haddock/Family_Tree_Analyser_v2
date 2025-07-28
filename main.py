"""
Family Tree Analyser v2 - Main Entry Point
Object-oriented rewrite with library-agnostic design.
"""

import sys
from pathlib import Path
from typing import Optional

from gedcom_db import GedcomDB
from ged4py_db import Ged4PyGedcomDB
from menu_system import MenuSystem


def choose_library() -> str:
    """Allow user to choose GEDCOM library (for future expansion)."""
    print("Available GEDCOM libraries:")
    print("1. ged4py (default, read-only)")
    print("2. [Future: other libraries will be listed here]")
    
    choice = input("Choose library (1-1, default 1): ").strip()
    
    if choice in ['', '1']:
        return 'ged4py'
    else:
        print(f"Invalid choice '{choice}', defaulting to ged4py")
        return 'ged4py'


def create_database(library_name: str) -> Optional[GedcomDB]:
    """Create database instance based on library choice."""
    if library_name == 'ged4py':
        return Ged4PyGedcomDB()
    else:
        print(f"Unsupported library: {library_name}")
        return None


def get_gedcom_file() -> Optional[str]:
    """Get GEDCOM file path from user."""
    # Check for default file
    default_files = ['moss_tree.ged']
    
    for default_file in default_files:
        if Path(default_file).exists():
            use_default = input(f"Use default file '{default_file}'? (y/n, default y): ").strip().lower()
            if use_default in ['', 'y', 'yes']:
                return default_file
    
    # Ask user for file path
    while True:
        file_path = input("Enter path to GEDCOM file: ").strip()
        
        if not file_path:
            print("Please enter a file path.")
            continue
        
        if Path(file_path).exists():
            return file_path
        else:
            print(f"File not found: {file_path}")
            retry = input("Try again? (y/n): ").strip().lower()
            if retry not in ['y', 'yes']:
                return None


def main():
    """Main entry point for Family Tree Analyser v2."""
    print("Family Tree Analyser v2")
    print("========================")
    
    # Choose library
    library_name = choose_library()
    
    # Create database instance
    database = create_database(library_name)
    if not database:
        print("Failed to create database instance.")
        sys.exit(1)
    
    # Get GEDCOM file
    file_path = get_gedcom_file()
    if not file_path:
        print("No GEDCOM file specified. Exiting.")
        sys.exit(1)
    
    # Load the file
    print(f"Loading {file_path}...")
    
    if not database.load_file(file_path):
        print(f"Failed to load GEDCOM file: {file_path}")
        sys.exit(1)
    
    print("File loaded successfully!")
    
    # Create and run menu system
    menu = MenuSystem(database)
    menu.run()


if __name__ == "__main__":
    main()
