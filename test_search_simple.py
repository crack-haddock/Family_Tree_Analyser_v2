#!/usr/bin/env python3
"""Test the enhanced search functionality."""

from ged4py_db import Ged4PyGedcomDB
from query_handlers import SearchQueryHandler
import os

def test_search():
    print("Testing enhanced search functionality...")
    
    # Create database instance
    if os.path.exists("tree.ged"):
        filename = "tree.ged"
    elif os.path.exists("moss_tree.ged"):
        filename = "moss_tree.ged"
    else:
        print("No GEDCOM file found")
        return
    
    print(f"Using file: {filename}")
    db = Ged4PyGedcomDB()
    if not db.load_file(filename):
        print("Failed to load file")
        return
    
    # Test search functionality
    search_handler = SearchQueryHandler(db)
    
    # Perform a simple search
    print("\nSearching for 'John'...")
    results = db.search_individuals_advanced(
        name="John",
        exact_match=False
    )
    
    if results:
        print(f"Found {len(results)} individuals:")
        for i, individual in enumerate(results[:3], 1):  # Show first 3 results
            print(f"{i}. {individual.name} (ID: {individual.xref_id})")
            birth_year = individual.birth_year or "Unknown"
            death_year = individual.death_year or "Living"
            print(f"   Birth: {birth_year} | Death: {death_year}")
        
        # Test detailed view for first result
        if len(results) > 0:
            print("\nTesting detailed view for first result:")
            search_handler._display_individual_details(results[0])
    else:
        print("No individuals found with 'John' in their name")

if __name__ == "__main__":
    test_search()
