#!/usr/bin/env python3

import sys
sys.path.append(r'c:\Users\richa\source\python\familytree')
from main import create_database

def quick_debug():
    print("=== Quick Occupation Debug ===")
    
    # Load database
    db = create_database('ged4py')
    if not db:
        print("Failed to create database!")
        return
    
    success = db.load_file('moss_tree.ged')
    if not success:
        print("Failed to load GEDCOM file!")
        return
    
    print("Database loaded successfully")
    
    # Get all individuals
    all_individuals = db.get_all_individuals()
    print(f"Total individuals: {len(all_individuals)}")
    
    # Filter to 1830-1939
    filtered = []
    for individual in all_individuals:
        birth_year = individual.birth_year
        if birth_year and 1830 <= birth_year <= 1939:
            filtered.append(individual)
    
    print(f"Individuals 1830-1939: {len(filtered)}")
    
    # Count occupations
    with_occu = 0
    without_occu = 0
    
    # Test first 10 in detail
    print("\n=== Testing first 10 individuals ===")
    for i, individual in enumerate(filtered[:10]):
        print(f"\n{i+1}. {individual.name} ({individual.birth_year})")
        
        try:
            occupations = individual.get_occupations()
            occ_count = len(occupations)
            print(f"   Occupations found: {occ_count}")
            
            if occ_count > 0:
                with_occu += 1
                for j, occ in enumerate(occupations):
                    print(f"   {j+1}: {occ}")
            else:
                without_occu += 1
                
            # Debug: check if individual has raw_record
            if hasattr(individual, 'raw_record') and individual.raw_record:
                print(f"   Has raw_record: Yes")
                # Check for any OCCU tags
                occu_count = 0
                note_count = 0
                if hasattr(individual.raw_record, 'sub_records'):
                    for sub in individual.raw_record.sub_records:
                        if hasattr(sub, 'tag'):
                            if sub.tag in ['OCCU', 'PROF', '_OCCU']:
                                occu_count += 1
                                print(f"   Found {sub.tag}: {sub.value}")
                            elif sub.tag == 'NOTE':
                                note_count += 1
                                print(f"   Found NOTE: {str(sub.value)[:100]}...")
                print(f"   OCCU tags found: {occu_count}, NOTE tags: {note_count}")
            else:
                print(f"   Has raw_record: No")
                
        except Exception as e:
            print(f"   ERROR: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\nSample results: {with_occu}/{with_occu + without_occu} have occupations")

if __name__ == '__main__':
    quick_debug()
