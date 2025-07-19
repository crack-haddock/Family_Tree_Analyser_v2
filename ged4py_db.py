"""
Ged4Py implementation of the GedcomDB interface.
Provides read-only access to GEDCOM files using the ged4py library.
"""

from typing import List, Optional
from datetime import datetime
from pathlib import Path
import re
import json
import pickle
import os
import time

from gedcom_db import GedcomDB, Individual, Family

try:
    from ged4py.parser import GedcomReader
except ImportError:
    print("Warning: ged4py library not found. Install with: pip install ged4py")
    GedcomReader = None


class Ged4PyIndividual(Individual):
    """Individual wrapper for ged4py records."""
    
    def __init__(self, xref_id: str, raw_record):
        super().__init__(xref_id, raw_record)
    
    @property
    def name(self) -> str:
        """Return formatted name."""
        if self.raw_record and self.raw_record.name:
            return self.raw_record.name.format()
        return self.xref_id
    
    @property
    def birth_date(self) -> Optional[datetime]:
        """Return birth date if available."""
        return self._get_date('BIRT')
    
    @property
    def death_date(self) -> Optional[datetime]:
        """Return death date if available."""
        return self._get_date('DEAT')
    
    @property
    def birth_place(self) -> Optional[str]:
        """Return birth place if available."""
        if not self.raw_record:
            return None
        
        for sub in self.raw_record.sub_records:
            if sub.tag == 'BIRT':
                for sub2 in sub.sub_records:
                    if sub2.tag == 'PLAC':
                        return str(sub2.value)
        return None
    
    def calculate_age(self) -> Optional[int]:
        """Calculate age at death, or current age if still alive."""
        birth_date = self.birth_date
        if not birth_date:
            return None
        
        death_date = self.death_date
        if death_date:
            # Age at death
            return (death_date - birth_date).days // 365
        else:
            # Current age (assuming still alive)
            from datetime import datetime
            today = datetime.today()
            return (today - birth_date).days // 365
    
    @property
    def birth_year(self) -> Optional[int]:
        """Return birth year if available."""
        birth_date = self.birth_date
        return birth_date.year if birth_date else None
    
    @property 
    def death_year(self) -> Optional[int]:
        """Return death year if available."""
        death_date = self.death_date
        return death_date.year if death_date else None
    
    def _get_date(self, tag: str) -> Optional[datetime]:
        """Extract date from a specific tag (BIRT, DEAT, etc.)."""
        if not self.raw_record:
            return None
        
        for sub in self.raw_record.sub_records:
            if sub.tag == tag:
                for sub2 in sub.sub_records:
                    if sub2.tag == 'DATE':
                        return self._parse_gedcom_date(sub2.value)
        return None
    
    def _parse_gedcom_date(self, date_val) -> Optional[datetime]:
        """Parse GEDCOM date format into datetime object."""
        if not date_val:
            return None
        
        date_str = str(date_val).strip()
        
        # Try different date formats
        for fmt in ('%d %b %Y', '%b %Y', '%Y'):
            try:
                return datetime.strptime(date_str, fmt)
            except Exception:
                continue
        
        # Try to extract year if all else fails
        match = re.search(r'(\d{4})', date_str)
        if match:
            return datetime(int(match.group(1)), 1, 1)
        
        return None
    
    def get_parents(self) -> List['Ged4PyIndividual']:
        """Get parents of this individual."""
        parents = []
        if not self.raw_record:
            return parents
            
        # Find FAMC (family as child) record
        for sub in self.raw_record.sub_records:
            if sub.tag == 'FAMC':
                family_id = str(sub.value)
                # This would require access to the database to resolve family references
                # For now, return empty list - would need database instance to implement fully
                break
        return parents
    
    def get_spouses(self) -> List['Ged4PyIndividual']:
        """Get spouses of this individual."""
        spouses = []
        if not self.raw_record:
            return spouses
            
        # Find FAMS (family as spouse) records
        for sub in self.raw_record.sub_records:
            if sub.tag == 'FAMS':
                family_id = str(sub.value)
                # This would require access to the database to resolve family references
                # For now, return empty list - would need database instance to implement fully
                break
        return spouses
    
    def get_children(self) -> List['Ged4PyIndividual']:
        """Get children of this individual."""
        children = []
        if not self.raw_record:
            return children
            
        # Find FAMS (family as spouse) records, then get children from those families
        for sub in self.raw_record.sub_records:
            if sub.tag == 'FAMS':
                family_id = str(sub.value)
                # This would require access to the database to resolve family references
                # For now, return empty list - would need database instance to implement fully
                break
        return children

    def get_occupations(self) -> List[dict]:
        """Extract occupation information from various GEDCOM tags and sources."""
        occupations = []
        if not self.raw_record:
            return occupations
        
        # Check direct occupation tags
        for sub in self.raw_record.sub_records:
            try:
                # Standard occupation tags
                if sub.tag in ['OCCU', 'PROF', 'TITL']:
                    if sub.value:
                        occ_info = {
                            'occupation': str(sub.value).strip(),
                            'source': sub.tag,
                            'date': None,
                            'place': None
                        }
                        
                        # Check for date and place in sub-records
                        if hasattr(sub, 'sub_records'):
                            for sub2 in sub.sub_records:
                                if sub2.tag == 'DATE' and sub2.value:
                                    occ_info['date'] = str(sub2.value).strip()
                                elif sub2.tag == 'PLAC' and sub2.value:
                                    occ_info['place'] = str(sub2.value).strip()
                        
                        occupations.append(occ_info)
                
                # Custom occupation tags (like _OCCU)
                elif sub.tag.startswith('_') and 'OCCU' in sub.tag.upper():
                    if sub.value:
                        occ_info = {
                            'occupation': str(sub.value).strip(),
                            'source': f"custom_{sub.tag}",
                            'date': None,
                            'place': None
                        }
                        occupations.append(occ_info)
                
                # Check NOTE fields for occupation information
                elif sub.tag == 'NOTE':
                    if sub.value:
                        note_text = str(sub.value).strip().lower()
                        # Look for occupation keywords in notes
                        if any(keyword in note_text for keyword in 
                               ['occupation:', 'profession:', 'trade:', 'job:', 'work:', 'employed', 'occupation']):
                            occ_info = {
                                'occupation': str(sub.value).strip(),
                                'source': 'NOTE_field',
                                'date': None,
                                'place': None
                            }
                            occupations.append(occ_info)
                
                # Check within events for occupation data
                elif sub.tag in ['CENS', 'RESI', 'EVEN', 'FACT']:
                    event_date = None
                    event_place = None
                    event_occupations = []
                    
                    # Look for occupation within the event
                    if hasattr(sub, 'sub_records'):
                        for sub2 in sub.sub_records:
                            if sub2.tag == 'DATE' and sub2.value:
                                event_date = str(sub2.value).strip()
                            elif sub2.tag == 'PLAC' and sub2.value:
                                event_place = str(sub2.value).strip()
                            elif sub2.tag in ['OCCU', 'PROF'] and sub2.value:
                                event_occupations.append(str(sub2.value).strip())
                            elif sub2.tag == 'NOTE' and sub2.value:
                                note_text = str(sub2.value).strip()
                                # Parse occupation from note text like "Occupation: Coal Miner Hewer; Marital Status: Married; ..."
                                if 'occupation:' in note_text.lower():
                                    # Extract just the occupation part
                                    parts = note_text.split(';')
                                    for part in parts:
                                        part = part.strip()
                                        if part.lower().startswith('occupation:'):
                                            occupation = part[11:].strip()  # Remove "Occupation:" prefix
                                            if occupation:
                                                event_occupations.append(occupation)
                                            break
                                elif any(keyword in note_text.lower() for keyword in 
                                       ['profession:', 'trade:', 'job:', 'work:', 'employed']):
                                    event_occupations.append(note_text)
                    
                    # Also check if the main event value contains occupation info
                    if sub.value:
                        event_text = str(sub.value).strip()
                        # Look for occupation-like keywords in residence or census data
                        if any(keyword in event_text.lower() for keyword in 
                               ['occupation:', 'profession:', 'trade:', 'job:', 'work:', 'employed as']):
                            event_occupations.append(event_text)
                    
                    # Add any found occupations from this event
                    for occ_text in event_occupations:
                        occ_info = {
                            'occupation': occ_text,
                            'source': f"{sub.tag}_event",
                            'date': event_date,
                            'place': event_place
                        }
                        occupations.append(occ_info)
                
                # Check SOURCE records for embedded occupation data
                elif sub.tag == 'SOUR':
                    # We would need to follow the source reference to get the actual source record
                    # For now, check if there are any sub-records under the source reference
                    if hasattr(sub, 'sub_records'):
                        for sub2 in sub.sub_records:
                            if sub2.tag in ['TEXT', 'NOTE', 'DATA'] and sub2.value:
                                text_value = str(sub2.value).strip().lower()
                                if any(keyword in text_value for keyword in 
                                       ['occupation:', 'profession:', 'trade:', 'job:', 'work:', 'employed']):
                                    occ_info = {
                                        'occupation': str(sub2.value).strip(),
                                        'source': f"source_{sub2.tag}",
                                        'date': None,
                                        'place': None
                                    }
                                    occupations.append(occ_info)
                        
            except Exception as e:
                # Continue processing other records if one fails
                continue
        
        return occupations


class Ged4PyFamily(Family):
    """Family wrapper for ged4py records."""
    
    def __init__(self, xref_id: str, raw_record):
        super().__init__(xref_id, raw_record)


class Ged4PyGedcomDB(GedcomDB):
    """GEDCOM database implementation using ged4py library."""
    
    def __init__(self):
        super().__init__()
        self.capabilities = {
            'read', 'search', 'analyze', 'dates', 'places', 'occupations',
            'relationships', 'data_quality'
        }
        self._parser = None
        self._individuals_cache = None
        self._families_cache = None
        
        # Relationship indexes for fast lookups
        self._individual_index = {}  # xref_id -> Individual
        self._family_index = {}      # xref_id -> Family
        self._parent_index = {}      # individual_id -> set of parent_ids
        self._child_index = {}       # individual_id -> set of child_ids
        self._spouse_index = {}      # individual_id -> set of spouse_ids
        self._family_members = {}    # family_id -> {'parents': set, 'children': set}
        self._indexes_built = False
        
        # Cache configuration
        self._base_dir = Path(__file__).parent
        self._cache_dir = self._base_dir / '.cache'
        self._indexes_dir = self._cache_dir / 'indexes'
        self._metadata_file = self._cache_dir / 'metadata.json'
        self._cache_version = "1.0"
    
    def load_file(self, file_path: str) -> bool:
        """Load GEDCOM file using ged4py with intelligent caching."""
        if GedcomReader is None:
            print("Error: ged4py library not available")
            return False
        
        try:
            # Convert to relative path if absolute
            if Path(file_path).is_absolute():
                self.file_path = str(Path(file_path).relative_to(self._base_dir))
            else:
                self.file_path = file_path
            
            # Test that we can open the file
            full_path = self._base_dir / self.file_path
            with GedcomReader(str(full_path)) as parser:
                # Just test that it opens successfully
                pass
            self.is_loaded = True
            
            # Try to use cached indexes first
            if self._should_use_cache():
                start_time = time.time()
                print("Loading cached indexes...")
                if self._load_indexes_from_cache():
                    end_time = time.time()
                    print(f"Cached indexes loaded successfully. ({end_time - start_time:.3f} seconds)")
                    return True
                else:
                    print("Failed to load cached indexes, rebuilding...")
            
            # Build indexes from scratch
            start_time = time.time()
            print("Building relationship indexes for fast lookups...")
            self._build_indexes()
            
            # Cache the indexes for next time
            self._save_indexes_to_cache()
            end_time = time.time()
            print(f"Indexes built and cached successfully. ({end_time - start_time:.3f} seconds)")
            
            return True
        except Exception as e:
            print(f"Error loading GEDCOM file: {e}")
            return False
    
    def _build_indexes(self):
        """Build relationship indexes for fast lookups."""
        if not self.is_loaded:
            return
        
        # Clear existing indexes
        self._individual_index.clear()
        self._family_index.clear()
        self._parent_index.clear()
        self._child_index.clear()
        self._spouse_index.clear()
        self._family_members.clear()
        
        full_path = self._base_dir / self.file_path
        with GedcomReader(str(full_path)) as parser:
            # First pass: Index all individuals and families (streaming, not loading all into memory)
            for indi in parser.records0('INDI'):
                individual = Ged4PyIndividual(indi.xref_id, indi)
                self._individual_index[indi.xref_id] = individual
                self._parent_index[indi.xref_id] = set()
                self._child_index[indi.xref_id] = set()
                self._spouse_index[indi.xref_id] = set()
            
            for fam in parser.records0('FAM'):
                family = Ged4PyFamily(fam.xref_id, fam)
                self._family_index[fam.xref_id] = family
                self._family_members[fam.xref_id] = {'parents': set(), 'children': set()}
            
            # Second pass: Build relationship mappings
            for indi in parser.records0('INDI'):
                individual_id = indi.xref_id
                
                # Process FAMC (Family as Child) - find parents
                for sub in indi.sub_records:
                    if sub.tag == 'FAMC':
                        family_id = str(sub.value)
                        if family_id in self._family_index:
                            # This person is a child in this family
                            self._family_members[family_id]['children'].add(individual_id)
                            
                            # Find parents in this family
                            family_record = self._family_index[family_id].raw_record
                            for fam_sub in family_record.sub_records:
                                if fam_sub.tag in ['HUSB', 'WIFE']:
                                    parent_id = str(fam_sub.value)
                                    if parent_id in self._individual_index:
                                        self._parent_index[individual_id].add(parent_id)
                                        self._child_index[parent_id].add(individual_id)
                    
                    elif sub.tag == 'FAMS':
                        # Family as Spouse - find spouse and children
                        family_id = str(sub.value)
                        if family_id in self._family_index:
                            # This person is a parent in this family
                            self._family_members[family_id]['parents'].add(individual_id)
                            
                            # Find spouse in this family
                            family_record = self._family_index[family_id].raw_record
                            for fam_sub in family_record.sub_records:
                                if fam_sub.tag in ['HUSB', 'WIFE']:
                                    spouse_id = str(fam_sub.value)
                                    if spouse_id != individual_id and spouse_id in self._individual_index:
                                        self._spouse_index[individual_id].add(spouse_id)
        
        self._indexes_built = True
    
    def get_parents_fast(self, individual_id: str) -> List[Individual]:
        """Get parents using indexes for fast lookup."""
        if not self._indexes_built:
            return []
        
        parent_ids = self._parent_index.get(individual_id, set())
        return [self._individual_index[pid] for pid in parent_ids if pid in self._individual_index]
    
    def get_children_fast(self, individual_id: str) -> List[Individual]:
        """Get children using indexes for fast lookup."""
        if not self._indexes_built:
            return []
        
        child_ids = self._child_index.get(individual_id, set())
        return [self._individual_index[cid] for cid in child_ids if cid in self._individual_index]
    
    def get_spouses_fast(self, individual_id: str) -> List[Individual]:
        """Get spouses using indexes for fast lookup."""
        if not self._indexes_built:
            return []
        
        spouse_ids = self._spouse_index.get(individual_id, set())
        return [self._individual_index[sid] for sid in spouse_ids if sid in self._individual_index]
    
    def get_siblings_fast(self, individual_id: str) -> List[Individual]:
        """Get siblings using indexes for fast lookup."""
        if not self._indexes_built:
            return []
        
        siblings = set()
        
        # Find all families where this person is a child
        for family_id, members in self._family_members.items():
            if individual_id in members['children']:
                # Add all other children from this family as siblings
                for sibling_id in members['children']:
                    if sibling_id != individual_id:
                        siblings.add(sibling_id)
        
        return [self._individual_index[sid] for sid in siblings if sid in self._individual_index]
    
    def get_individual_by_id_fast(self, individual_id: str) -> Optional[Individual]:
        """Get individual by ID using index for fast lookup."""
        if not self._indexes_built:
            return self.find_individual_by_id(individual_id)
        
        return self._individual_index.get(individual_id)

    def get_all_individuals(self) -> List[Individual]:
        """Return all individuals in the database."""
        if not self.is_loaded:
            return []
        
        # Use cached index if available for much faster access
        if self._indexes_built:
            return list(self._individual_index.values())
        
        # Fallback to file parsing
        individuals = []
        full_path = self._base_dir / self.file_path
        with GedcomReader(str(full_path)) as parser:
            for indi in parser.records0('INDI'):
                individuals.append(Ged4PyIndividual(indi.xref_id, indi))
        return individuals
    
    def get_all_families(self) -> List[Family]:
        """Return all families in the database."""
        if not self.is_loaded:
            return []
        
        # Use cached index if available
        if self._indexes_built:
            return list(self._family_index.values())
        
        # Fallback to file parsing
        families = []
        full_path = self._base_dir / self.file_path
        with GedcomReader(str(full_path)) as parser:
            for fam in parser.records0('FAM'):
                families.append(Ged4PyFamily(fam.xref_id, fam))
        return families
    
    def find_individual_by_id(self, xref_id: str) -> Optional[Individual]:
        """Find individual by GEDCOM ID."""
        if not self.is_loaded:
            return None
        
        with GedcomReader(self.file_path) as parser:
            for indi in parser.records0('INDI'):
                if indi.xref_id == xref_id:
                    return Ged4PyIndividual(indi.xref_id, indi)
        return None
    
    def find_family_by_id(self, xref_id: str) -> Optional[Family]:
        """Find family by GEDCOM ID."""
        if not self.is_loaded:
            return None
        
        with GedcomReader(self.file_path) as parser:
            for fam in parser.records0('FAM'):
                if fam.xref_id == xref_id:
                    return Ged4PyFamily(fam.xref_id, fam)
        return None
    
    def search_individuals_by_name(self, name: str, birth_year: Optional[int] = None) -> List[Individual]:
        """Search for individuals by name and optionally birth year."""
        if not self.is_loaded:
            return []
        
        matches = []
        name_lower = name.lower()
        
        with GedcomReader(self.file_path) as parser:
            for indi in parser.records0('INDI'):
                indi_wrapper = Ged4PyIndividual(indi.xref_id, indi)
                indi_name = indi_wrapper.name.lower()
                
                # Check name match
                if name_lower in indi_name:
                    # Check birth year if specified
                    if birth_year is not None:
                        birth_date = indi_wrapper.birth_date
                        if birth_date and birth_date.year == birth_year:
                            matches.append(indi_wrapper)
                        elif birth_date is None:
                            continue  # Skip if no birth date and year specified
                    else:
                        matches.append(indi_wrapper)
        
        return matches
    
    def search_individuals_advanced(self, name: str, exact_match: bool = False,
                                  min_birth_year: Optional[int] = None,
                                  max_birth_year: Optional[int] = None,
                                  min_death_year: Optional[int] = None,
                                  max_death_year: Optional[int] = None,
                                  ancestor_filter_ids: Optional[set] = None) -> List[Individual]:
        """Advanced search for individuals with multiple criteria."""
        if not self.is_loaded:
            return []
        
        matches = []
        name_lower = name.lower().strip()
        
        # Use indexes if available, otherwise fall back to file scanning
        if self._indexes_built:
            # Use indexed individuals for much faster search
            individuals_to_search = []
            
            if ancestor_filter_ids:
                # Only search within the ancestor filter
                for individual_id in ancestor_filter_ids:
                    if individual_id in self._individual_index:
                        individuals_to_search.append(self._individual_index[individual_id])
            else:
                # Search all indexed individuals
                individuals_to_search = list(self._individual_index.values())
            
            # Search through the (possibly filtered) list
            for indi_wrapper in individuals_to_search:
                indi_name = indi_wrapper.name.lower()
                
                # Check name match
                name_matches = False
                if exact_match:
                    # Case insensitive exact match
                    name_matches = (indi_name == name_lower)
                else:
                    # Pattern/wildcard match - name appears anywhere in the full name
                    name_matches = (name_lower in indi_name)
                
                if not name_matches:
                    continue
                
                # Check birth year constraints
                birth_date = indi_wrapper.birth_date
                if birth_date:
                    birth_year = birth_date.year
                    if min_birth_year and birth_year < min_birth_year:
                        continue
                    if max_birth_year and birth_year > max_birth_year:
                        continue
                elif min_birth_year or max_birth_year:
                    # Skip if birth constraints specified but no birth date
                    continue
                
                # Check death year constraints
                death_date = indi_wrapper.death_date
                if death_date:
                    death_year = death_date.year
                    if min_death_year and death_year < min_death_year:
                        continue
                    if max_death_year and death_year > max_death_year:
                        continue
                elif min_death_year or max_death_year:
                    # Skip if death constraints specified but no death date
                    continue
                
                matches.append(indi_wrapper)
        
        else:
            # Fallback to slow file scanning method
            with GedcomReader(self.file_path) as parser:
                for indi in parser.records0('INDI'):
                    # Check ancestor filter first
                    if ancestor_filter_ids and indi.xref_id not in ancestor_filter_ids:
                        continue
                    
                    indi_wrapper = Ged4PyIndividual(indi.xref_id, indi)
                    indi_name = indi_wrapper.name.lower()
                    
                    # Check name match
                    name_matches = False
                    if exact_match:
                        # Case insensitive exact match
                        name_matches = (indi_name == name_lower)
                    else:
                        # Pattern/wildcard match - name appears anywhere in the full name
                        name_matches = (name_lower in indi_name)
                    
                    if not name_matches:
                        continue
                    
                    # Check birth year constraints
                    birth_date = indi_wrapper.birth_date
                    if birth_date:
                        birth_year = birth_date.year
                        if min_birth_year and birth_year < min_birth_year:
                            continue
                        if max_birth_year and birth_year > max_birth_year:
                            continue
                    elif min_birth_year or max_birth_year:
                        # Skip if birth constraints specified but no birth date
                        continue
                    
                    # Check death year constraints
                    death_date = indi_wrapper.death_date
                    if death_date:
                        death_year = death_date.year
                        if min_death_year and death_year < min_death_year:
                            continue
                        if max_death_year and death_year > max_death_year:
                            continue
                    elif min_death_year or max_death_year:
                        # Skip if death constraints specified but no death date
                        continue
                    
                    matches.append(indi_wrapper)
        
        return matches

    # ============ CACHING METHODS ============
    
    def _should_use_cache(self) -> bool:
        """Determine if we can use cached indexes."""
        try:
            if not self._metadata_file.exists():
                return False
                
            metadata = self._load_metadata()
            if not metadata:
                return False
            
            # Check GEDCOM file hasn't changed
            current_stats = self._get_gedcom_stats()
            if not current_stats:
                return False
            
            cached_stats = {
                'gedcom_file': metadata.get('gedcom_file'),
                'gedcom_size': metadata.get('gedcom_size'),
                'gedcom_modified': metadata.get('gedcom_modified')
            }
            
            if current_stats != cached_stats:
                return False
                
            # Check cache version compatibility
            if metadata.get('cache_version') != self._cache_version:
                return False
                
            # Check all index files exist
            return self._validate_index_files(metadata)
        except Exception:
            return False
    
    def _get_gedcom_stats(self) -> Optional[dict]:
        """Get current GEDCOM file stats using relative path."""
        try:
            gedcom_path = self._base_dir / self.file_path
            if not gedcom_path.exists():
                return None
                
            stat = gedcom_path.stat()
            return {
                'gedcom_file': self.file_path,  # Store relative path
                'gedcom_size': stat.st_size,
                'gedcom_modified': stat.st_mtime
            }
        except Exception:
            return None
    
    def _load_metadata(self) -> Optional[dict]:
        """Load cache metadata from file."""
        try:
            with open(self._metadata_file, 'r') as f:
                return json.load(f)
        except Exception:
            return None
    
    def _validate_index_files(self, metadata: dict) -> bool:
        """Check that all expected index files exist."""
        try:
            expected_indexes = metadata.get('available_indexes', [])
            for index_name in expected_indexes:
                index_file = self._indexes_dir / f"{index_name}.pkl"
                if not index_file.exists():
                    return False
            return True
        except Exception:
            return False
    
    def _load_indexes_from_cache(self) -> bool:
        """Load relationship indexes from cache files."""
        try:
            # Load relationship indexes only
            with open(self._indexes_dir / 'parent_index.pkl', 'rb') as f:
                self._parent_index = pickle.load(f)
            
            with open(self._indexes_dir / 'child_index.pkl', 'rb') as f:
                self._child_index = pickle.load(f)
            
            with open(self._indexes_dir / 'spouse_index.pkl', 'rb') as f:
                self._spouse_index = pickle.load(f)
            
            with open(self._indexes_dir / 'family_members.pkl', 'rb') as f:
                self._family_members = pickle.load(f)
            
            # Rebuild individual and family indexes from GEDCOM file
            full_path = self._base_dir / self.file_path
            with GedcomReader(str(full_path)) as parser:
                for indi in parser.records0('INDI'):
                    individual = Ged4PyIndividual(indi.xref_id, indi)
                    self._individual_index[indi.xref_id] = individual
                
                for fam in parser.records0('FAM'):
                    family = Ged4PyFamily(fam.xref_id, fam)
                    self._family_index[fam.xref_id] = family
            
            self._indexes_built = True
            return True
        except Exception as e:
            print(f"Error loading cached indexes: {e}")
            return False
    
    def _save_indexes_to_cache(self):
        """Save relationship indexes to cache files - only the ID mappings, not full objects."""
        try:
            # Create cache directories
            self._cache_dir.mkdir(exist_ok=True)
            self._indexes_dir.mkdir(exist_ok=True)
            
            # Save only the relationship mappings (sets of IDs), not the full objects
            with open(self._indexes_dir / 'parent_index.pkl', 'wb') as f:
                pickle.dump(self._parent_index, f)
            
            with open(self._indexes_dir / 'child_index.pkl', 'wb') as f:
                pickle.dump(self._child_index, f)
            
            with open(self._indexes_dir / 'spouse_index.pkl', 'wb') as f:
                pickle.dump(self._spouse_index, f)
            
            with open(self._indexes_dir / 'family_members.pkl', 'wb') as f:
                pickle.dump(self._family_members, f)
            
            # Save metadata
            current_stats = self._get_gedcom_stats()
            if current_stats:
                metadata = {
                    **current_stats,
                    'indexes_created': datetime.now().timestamp(),
                    'cache_version': self._cache_version,
                    'available_indexes': [
                        'parent_index',
                        'child_index',
                        'spouse_index',
                        'family_members'
                    ]
                }
                
                with open(self._metadata_file, 'w') as f:
                    json.dump(metadata, f, indent=2)
                    
        except Exception as e:
            print(f"Warning: Could not save indexes to cache: {e}")
            import traceback
            traceback.print_exc()
    
    def clear_cache(self):
        """Manually clear the relationship index cache."""
        try:
            import shutil
            if self._cache_dir.exists():
                shutil.rmtree(self._cache_dir)
                print("Index cache cleared successfully.")
            else:
                print("No cache to clear.")
        except Exception as e:
            print(f"Error clearing cache: {e}")
    
    def get_cache_info(self) -> dict:
        """Get information about the current cache state."""
        info = {
            'cache_exists': self._metadata_file.exists(),
            'cache_valid': False,
            'cache_size': 0,
            'last_updated': None
        }
        
        if info['cache_exists']:
            try:
                metadata = self._load_metadata()
                if metadata:
                    info['cache_valid'] = self._should_use_cache()
                    info['last_updated'] = metadata.get('indexes_created')
                    
                    # Calculate cache size
                    if self._indexes_dir.exists():
                        total_size = sum(f.stat().st_size for f in self._indexes_dir.iterdir() if f.is_file())
                        info['cache_size'] = total_size
            except Exception:
                pass
        
        return info
