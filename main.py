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
    
    # Load GEDCOM file (will show file selection menu)
    print("Loading GEDCOM file...")

    if not database.load_file():  # Don't pass any file path - triggers file selection
        print("Failed to load GEDCOM file")
        sys.exit(1)
    
    print("File loaded successfully!")
    
    # Create and run menu system
    menu = MenuSystem(database)
    menu.run()


if __name__ == "__main__":
    main()
