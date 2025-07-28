#!/usr/bin/env python3
"""
Utility script to view the current places configuration.
Usage: python view_places.py [nation] [county]
"""

import sys
from pathlib import Path

# Add the current directory to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent))

def show_usage():
    print("Usage: python view_places.py [nation] [county]")
    print()
    print("Examples:")
    print("  python view_places.py                    # Show all nations and counties")
    print("  python view_places.py Wales              # Show all counties in Wales")
    print("  python view_places.py Wales Flintshire   # Show all places in Flintshire")

def main():
    nation_filter = sys.argv[1] if len(sys.argv) > 1 else None
    county_filter = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        from query_handlers import ReportQueryHandler
        
        # Create a dummy database instance
        class DummyDB:
            pass
        
        db = DummyDB()
        
        # Create the handler which loads the places config
        print("Loading places configuration...")
        handler = ReportQueryHandler(db)
        
        if county_filter and nation_filter:
            # Show specific county details
            if county_filter in handler.county_places:
                places = handler.county_places[county_filter]
                print(f"\n=== {county_filter}, {nation_filter} ===")
                for place, details in places.items():
                    print(f"  {place}")
                    if details.get('local2_places'):
                        print(f"    Local2 places: {details['local2_places']}")
                    if details.get('known_streets'):
                        print(f"    Known streets: {details['known_streets']}")
            else:
                print(f"County '{county_filter}' not found in configuration")
        
        elif nation_filter:
            # Show counties for specific nation
            if nation_filter in handler.nation_counties:
                counties = handler.nation_counties[nation_filter]
                print(f"\n=== {nation_filter} ===")
                if counties:
                    for county in counties:
                        place_count = len(handler.county_places.get(county, {}))
                        print(f"  {county} ({place_count} places)")
                else:
                    print("  No counties configured")
            else:
                print(f"Nation '{nation_filter}' not found in configuration")
        
        else:
            # Show all nations and counties
            print("\n=== ALL NATIONS AND COUNTIES ===")
            for nation, counties in handler.nation_counties.items():
                print(f"\n{nation}:")
                if counties:
                    for county in counties:
                        place_count = len(handler.county_places.get(county, {}))
                        print(f"  {county} ({place_count} places)")
                else:
                    print("  No counties configured")
            
            # Show direct nation places
            if handler.nation_places:
                print(f"\n=== DIRECT NATION PLACES ===")
                for nation, places in handler.nation_places.items():
                    if places:
                        print(f"{nation}: {places}")
            
    except ImportError as e:
        print(f"Import error: {e}")
        print("Make sure all required modules are available")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
