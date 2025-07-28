#!/usr/bin/env python3
"""
Utility script to easily add new places to the places configuration.
Usage: python add_place.py <place_name> <county> [nation]
"""

import sys
from pathlib import Path

# Add the current directory to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent))

def show_usage():
    print("Usage: python add_place.py <place_name> <county> [nation]")
    print()
    print("Examples:")
    print("  python add_place.py 'New Town' Flintshire")
    print("  python add_place.py 'Another Place' 'New County' Wales")
    print()
    print("If nation is not specified, it will be determined automatically")
    print("from existing county mappings.")

def main():
    if len(sys.argv) < 3:
        show_usage()
        return
    
    place_name = sys.argv[1]
    county = sys.argv[2]
    nation = sys.argv[3] if len(sys.argv) > 3 else None
    
    try:
        from query_handlers import ReportQueryHandler
        
        # Create a dummy database instance
        class DummyDB:
            pass
        
        db = DummyDB()
        
        # Create the handler which loads the places config
        print("Loading places configuration...")
        handler = ReportQueryHandler(db)
        
        # Add the new place
        print(f"Adding '{place_name}' to {county}" + (f" in {nation}" if nation else ""))
        success = handler.add_place_to_config(place_name, county, nation)
        
        if success:
            print(f"✓ Successfully added '{place_name}' to {county}")
            
            # Show the updated configuration for this county
            if county in handler.county_places:
                places = list(handler.county_places[county].keys())
                print(f"Current places in {county}: {places}")
        else:
            print(f"✗ Failed to add '{place_name}' to {county}")
            
    except ImportError as e:
        print(f"Import error: {e}")
        print("Make sure all required modules are available")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
