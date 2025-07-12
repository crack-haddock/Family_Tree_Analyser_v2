#!/usr/bin/env python3
"""Quick debug test to see why search options aren't showing."""

from ged4py_db import Ged4PyGedcomDB
from menu_system import MenuSystem
import os

def test_capabilities():
    print("Testing capability detection...")
    
    # Create database instance BEFORE loading file (like main.py does)
    db = Ged4PyGedcomDB()
    print(f"Database capabilities (before loading): {sorted(db.capabilities)}")
    print(f"Database is_loaded: {db.is_loaded}")
    
    # Create menu system BEFORE loading file
    menu = MenuSystem(db)
    search_options_before = menu.get_available_options_in_category("search")
    print(f"Search options before loading: {len(search_options_before)}")
    
    # Now load the file
    if os.path.exists("tree.ged"):
        filename = "tree.ged"
    elif os.path.exists("moss_tree.ged"):
        filename = "moss_tree.ged"
    else:
        print("No GEDCOM file found")
        return
    
    print(f"Using file: {filename}")
    if not db.load_file(filename):
        print("Failed to load file")
        return
    
    print(f"Database is_loaded after loading: {db.is_loaded}")
    
    # Test specific capability checks AFTER loading
    print(f"Supports 'read': {db.supports('read')}")
    print(f"Supports 'search': {db.supports('search')}")
    
    # Check search options AFTER loading
    search_options_after = menu.get_available_options_in_category("search")
    print(f"Search options after loading: {len(search_options_after)}")
    
    # Check available categories
    available_cats = menu.get_available_categories()
    print(f"\nAvailable categories: {[cat.name for cat in available_cats]}")

if __name__ == "__main__":
    test_capabilities()
