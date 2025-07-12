"""
Ged4Py implementation of the GedcomDB interface.
Provides read-only access to GEDCOM files using the ged4py library.
"""

from typing import List, Optional
from datetime import datetime
import re

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
    
    def load_file(self, file_path: str) -> bool:
        """Load GEDCOM file using ged4py."""
        if GedcomReader is None:
            print("Error: ged4py library not available")
            return False
        
        try:
            self.file_path = file_path
            # Test that we can open the file
            with GedcomReader(file_path) as parser:
                # Just test that it opens successfully
                pass
            self.is_loaded = True
            
            # Build indexes on load for fast relationship lookups
            print("Building relationship indexes for fast lookups...")
            self._build_indexes()
            print("Indexes built successfully.")
            
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
        
        with GedcomReader(self.file_path) as parser:
            # First pass: Index all individuals and families
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
        
        individuals = []
        with GedcomReader(self.file_path) as parser:
            for indi in parser.records0('INDI'):
                individuals.append(Ged4PyIndividual(indi.xref_id, indi))
        return individuals
    
    def get_all_families(self) -> List[Family]:
        """Return all families in the database."""
        if not self.is_loaded:
            return []
        
        families = []
        with GedcomReader(self.file_path) as parser:
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
