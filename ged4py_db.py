"""
Ged4Py implementation of the GedcomDB interface.
Provides read-only access to GEDCOM files using the ged4py library.
"""

from typing import List, Optional
from datetime import datetime
from pathlib import Path
import webbrowser
import os
import re
import json
import pickle
import os
import time
import shutil
import traceback

from gedcom_db import GedcomDB, Individual, Family

try:
    from ged4py.parser import GedcomReader
except ImportError:
    print("Warning: ged4py library not found. Install with: pip install ged4py")
    GedcomReader = None

class Ged4PyIndividual(Individual):
    """Individual wrapper for ged4py records."""
    
    def __init__(self, xref_id: str, raw_record, gedcom_db=None):
        super().__init__(xref_id, raw_record)
        self.gedcom_db = gedcom_db
    
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
        """Extract occupation information recursively from all tags and notes."""
        occupations = []
        if not self.raw_record:
            return occupations
        
        # Recursively extract from all parts of the record
        self._extract_occupations_recursive(self.raw_record, occupations)
        
        return occupations
    
# Replace the method starting at line 179

    def _extract_occupations_recursive(self, record, occupations: List[dict], depth: int = 0):
        """
        Recursively extract occupations from a record and all its sub-records, including source records.
        Uses a robust, case-insensitive exclusion list for skipping irrelevant fields.
        """
        if depth > 20:  # Increased depth limit for deep source record nesting
            return

        indent = "  " * depth

        # Unified, robust exclusion list (case-insensitive, substring match)
        exclusion_list = [
            "archive", "national archives", "relationship", "relation", "marital", "gsu", "folio",
            "ancestry family tree", "general register office", "Marriage Index", "cemeter", "Burial", 
            "death", "Deceased", "Workhouse Admission", "marriages", "cremations", "record office", "parish",
            #"census", "census record",
            "Parish Registers", "Archdeacon", "piece:", "reference", "index", "findagrave", "war grave"
        ]
        exclusion_list = [e.lower() for e in exclusion_list]

        try:
            # Check direct OCCU tags
            if hasattr(record, 'tag') and record.tag in ['OCCU', 'PROF', '_OCCU'] and record.value:
                occupation_text = str(record.value).strip()
                if not self._looks_like_source_title(occupation_text):
                    print(f"{indent}DEBUG: Found top-level occupation: '{occupation_text}'")
                    occupations.append({
                        'occupation': occupation_text,
                        'source': record.tag,
                        'date': None,
                        'place': None
                    })

            # Check data-holding tags that might contain occupations
            if hasattr(record, 'tag') and record.tag in ['NOTE', 'TEXT', 'DATA', 'PAGE', 'CONT'] and record.value:
                text_data = str(record.value).strip()
                if len(text_data) > 5 and any(char.isalpha() for char in text_data):
                    text_data_lower = text_data.lower()
                    #if any(excl in text_data_lower for excl in exclusion_list):
                        #print(f"{indent}DEBUG: Skipping record with tag '{record.tag}' due to exclusion filter: '{text_data[:50]}...'")
                    #    None
                    #else:
                        #print(f"\n--- INTERACTIVE DEBUG: Record Tag '{record.tag}' for Individual {self.name} (Depth: #{depth}) ---")
                        #print(f"Text: {text_data}")
                        #user_input = input("Does this look like it contains occupation data? (y/n): ").strip().lower()

                        ##if user_input == 'y':
                    extracted_occupations = self._extract_occupations_from_text_regex(text_data)
                        #print(f"Extraction result: {extracted_occupations if extracted_occupations else 'None found'}")
                    for occ in extracted_occupations:
                        occupations.append({
                            'occupation': occ,
                            'source': f'{record.tag}_tag',
                            'date': None,
                            'place': None
                        })
                        ##else:
                          ##  print("Skipping extraction for this record.")

            # Handle SOUR (source) references - resolve and check the actual source record
            if hasattr(record, 'tag') and record.tag == 'SOUR' and record.value:
                source_ref = str(record.value).strip()
                if source_ref.startswith('@') and source_ref.endswith('@'):
                    try:
                        if hasattr(self, 'gedcom_db') and self.gedcom_db and hasattr(self.gedcom_db, '_source_index'):
                            source_record = self.gedcom_db._source_index.get(source_ref)
                            if source_record:
                                #print(f"{indent}DEBUG: Resolving SOUR tag '{source_ref}', entering recursive search.")
                                # Recursively search the resolved source record
                                self._extract_occupations_recursive(source_record, occupations, depth + 1)
                            else:
                                print(f"{indent}DEBUG: FAILED to resolve source record {source_ref} from index.")
                        else:
                            print(f"CRITICAL: Cannot resolve source {source_ref} for {self.xref_id}. DB link missing or source index not built.")
                    except Exception as e:
                        print(f"Warning: Error resolving source {source_ref}: {e}")

            # Recursively process all sub-records
            if hasattr(record, 'sub_records') and record.sub_records:
                for sub_record in record.sub_records:
                    self._extract_occupations_recursive(sub_record, occupations, depth + 1)

        except Exception:
            # Continue processing other records if one fails
            pass
    
    def _extract_occupations_from_text_regex(self, text: str) -> List[str]:
        """Extract occupations from text using regex patterns like version 1."""
        if not text:
            return []
        
        occupations = []
        text_lower = text.lower()
        
        import re
        
        # Pattern 1: "Occupation: [job title]"
        occupation_patterns = [
            r'occupation:\s*([^;,\n\r]+)',
            r'profession:\s*([^;,\n\r]+)', 
            r'trade:\s*([^;,\n\r]+)',
            r'employment:\s*([^;,\n\r]+)',
            r'job:\s*([^;,\n\r]+)',
            r'work:\s*([^;,\n\r]+)',
            r'employed\s+as:\s*([^;,\n\r]+)',
            r'working\s+as:\s*([^;,\n\r]+)',
        ]
        
        for pattern in occupation_patterns:
            matches = re.finditer(pattern, text_lower)
            for match in matches:
                occupation = match.group(1).strip()
                if occupation and len(occupation) > 2:  # Avoid single letters
                    # Clean up the occupation
                    occupation = re.sub(r'\s+', ' ', occupation)  # Normalize whitespace
                    occupation = occupation.strip('.,;:-')  # Remove trailing punctuation
                    if occupation:
                        occupations.append(occupation.title())
        
        # Pattern 2: Common occupation words standing alone
        # Look for standalone occupation keywords that might not have explicit labels
        # Always check this, not just when no explicit patterns found
        occupation_keywords = [
            r'\b(farmer|farming)\b',
            r'\b(labou?rer?|labou?ring)\b', 
            r'\b(miner|mining|pitman|collier)\b',
            r'\b(clerk|clerical)\b',
            r'\b(teacher|teaching|schoolmaster|schoolmistress)\b',
            r'\b(carpenter|joiner|woodworker)\b',
            r'\b(blacksmith|smith|metalworker)\b',
            r'\b(merchant|trader|dealer)\b',
            r'\b(miller|milling)\b',
            r'\b(baker|baking)\b',
            r'\b(shoemaker|cobbler|bootmaker)\b',
            r'\b(tailor|tailoring|seamstress|dressmaker)\b',
            r'\b(weaver|weaving|textile)\b',
            r'\b(mason|stonemason|bricklayer)\b',
            r'\b(cooper|barrel\s*maker)\b',
            r'\b(butcher|meat\s*seller)\b',
            r'\b(grocer|shopkeeper|storekeeper)\b',
            r'\b(servant|domestic|housemaid|cook)\b',
            r'\b(nurse|nursing)\b',
            r'\b(doctor|physician|surgeon)\b',
            r'\b(lawyer|solicitor|barrister)\b',
            r'\b(minister|priest|clergyman|vicar|rector)\b',
            r'\b(soldier|military|army)\b',
            r'\b(sailor|seaman|mariner|navy)\b',
            r'\b(engineer|engineering)\b',
            r'\b(machinist|machine\s*operator)\b',
            r'\b(foreman|supervisor|overseer)\b',
            r'\b(manager|management)\b',
            r'\b(proprietor|owner)\b',
            r'\b(salesman|sales|commercial\s*traveller)\b',
            r'\b(driver|carter|coachman)\b',
            r'\b(conductor|railway|railroad)\b',
            r'\b(fireman|stoker)\b',
            r'\b(policeman|constable|police)\b',
            r'\b(postman|postal|mail)\b',
            r'\b(guard|watchman|gatekeeper)\b',
            r'\b(attendant|caretaker)\b',
        ]
        
        # Check keyword patterns regardless of whether we found explicit patterns
        for pattern in occupation_keywords:
            matches = re.finditer(pattern, text_lower)
            for match in matches:
                occupation = match.group(1).strip()
                if occupation:
                    # Convert to a more standard form
                    if 'labou' in occupation:
                        occupation = 'Labourer'
                    elif 'farm' in occupation:
                        occupation = 'Farmer'
                    elif 'min' in occupation or 'pit' in occupation or 'collier' in occupation:
                        occupation = 'Miner'
                    else:
                        occupation = occupation.title()
                    
                    if occupation not in occupations:  # Avoid duplicates
                        occupations.append(occupation)
        
        return occupations

    def _get_source_record(self, source_id: str):
        """Get a source record by its ID."""
        try:
            # Use the database's source index if available
            if hasattr(self, 'gedcom_db') and self.gedcom_db and hasattr(self.gedcom_db, 'records'):
                return self.gedcom_db.records.get(source_id)
        except Exception:
            pass
        return None
    
    def _extract_occupations_from_source_record(self, source_record):
        """Extract occupation data from a source record."""
        occupations = []
        try:
            if hasattr(source_record, 'sub_records'):
                for sub in source_record.sub_records:
                    if sub.tag in ['TEXT', 'NOTE', 'DATA'] and sub.value:
                        occupation_text = self._extract_occupation_from_text(str(sub.value))
                        if occupation_text:
                            occupations.append({
                                'occupation': occupation_text,
                                'date': None,
                                'place': None,
                                'source': f"source_record_{sub.tag}",
                            })
                    # Check sub-sub records for occupation data
                    elif hasattr(sub, 'sub_records'):
                        for sub2 in sub.sub_records:
                            if sub2.tag in ['TEXT', 'NOTE'] and sub2.value:
                                occupation_text = self._extract_occupation_from_text(str(sub2.value))
                                if occupation_text:
                                    occupations.append({
                                        'occupation': occupation_text,
                                        'date': None,
                                        'place': None,
                                        'source': f"source_record_{sub.tag}_{sub2.tag}",
                                    })
        except Exception:
            pass
        return occupations

    def _looks_like_source_title(self, text: str) -> bool:
        """Check if text looks like a source title rather than an occupation."""
        if not text:
            return False
        
        text_lower = text.lower()
        
        # Common source title indicators
        source_indicators = [
            'census', 'england', 'wales', 'scotland', 'birth', 'death', 'marriage',
            'baptism', 'burial', 'church', 'parish', 'register', 'record', 'index',
            'ancestry', 'family tree', 'freebmd', 'lds', 'mormon', 'familysearch',
            'class:', 'piece:', 'folio:', 'page:', 'rg9', 'rg10', 'rg11', 'rg12',
            'ho107', 'probate', 'administration', 'will', 'christening'
        ]
        
        return any(indicator in text_lower for indicator in source_indicators)
    
    def _is_census_source(self, source_record) -> bool:
        """Check if a source record represents a census."""
        try:
            if hasattr(source_record, 'sub_records'):
                for sub in source_record.sub_records:
                    if sub.tag == 'TITL' and sub.value:
                        title = str(sub.value).lower()
                        if 'census' in title:
                            return True
        except Exception:
            pass
        return False
    
    def _extract_census_occupations(self, source_record, occupations: List[dict]):
        """Extract occupation data specifically from census source records."""
        try:
            if hasattr(source_record, 'sub_records'):
                for sub in source_record.sub_records:
                    # Focus on TEXT, NOTE, and DATA fields in census records
                    if sub.tag in ['TEXT', 'NOTE', 'DATA'] and sub.value:
                        text_data = str(sub.value).strip()
                        # Use enhanced regex extraction for census data
                        extracted_occupations = self._extract_occupations_from_census_text(text_data)
                        
                        for occ in extracted_occupations:
                            occupations.append({
                                'occupation': occ,
                                'source': f'CENSUS_{sub.tag}',
                                'date': None,
                                'place': None
                            })
                    
                    # Check sub-sub records for nested occupation data
                    elif hasattr(sub, 'sub_records'):
                        for sub2 in sub.sub_records:
                            if sub2.tag in ['TEXT', 'NOTE', 'DATA'] and sub2.value:
                                text_data = str(sub2.value).strip()
                                extracted_occupations = self._extract_occupations_from_census_text(text_data)
                                
                                for occ in extracted_occupations:
                                    occupations.append({
                                        'occupation': occ,
                                        'source': f'CENSUS_{sub.tag}_{sub2.tag}',
                                        'date': None,
                                        'place': None
                                    })
        except Exception:
            pass
    
    def _extract_occupations_from_census_text(self, text: str) -> List[str]:
        """Enhanced occupation extraction specifically designed for census text data."""
        if not text:
            return []
        
        occupations = []
        text_lower = text.lower()
        
        import re
        
        # Enhanced patterns for census data
        census_occupation_patterns = [
            r'occupation[:\s]*([^;,\n\r\t]+)',
            r'profession[:\s]*([^;,\n\r\t]+)',
            r'trade[:\s]*([^;,\n\r\t]+)',
            r'employment[:\s]*([^;,\n\r\t]+)',
            r'work[:\s]*([^;,\n\r\t]+)',
            r'job[:\s]*([^;,\n\r\t]+)',
            r'employed\s+as[:\s]*([^;,\n\r\t]+)',
            r'working\s+as[:\s]*([^;,\n\r\t]+)',
        ]
        
        for pattern in census_occupation_patterns:
            matches = re.finditer(pattern, text_lower)
            for match in matches:
                occupation = match.group(1).strip()
                if occupation and len(occupation) > 1:
                    # Clean up the occupation
                    occupation = re.sub(r'\s+', ' ', occupation)  # Normalize whitespace
                    occupation = occupation.strip('.,;:-')  # Remove trailing punctuation
                    
                    # Validate it looks like an occupation, not a place or other data
                    if self._validate_occupation_text(occupation):
                        occupations.append(occupation.title())
        
        # If no explicit patterns found, look for standalone occupation keywords
        if not occupations:
            occupation_keywords = [
                r'\b(farmer|farming|agricultural\s*lab[ou]*rer)\b',
                r'\b(lab[ou]*rer?|lab[ou]*ring|general\s*lab[ou]*rer)\b',
                r'\b(miner|mining|pitman|collier|coal\s*miner)\b',
                r'\b(clerk|clerical|office\s*clerk)\b',
                r'\b(teacher|teaching|schoolmaster|schoolmistress|head\s*teacher)\b',
                r'\b(carpenter|joiner|woodworker|cabinet\s*maker)\b',
                r'\b(blacksmith|smith|metalworker|iron\s*worker)\b',
                r'\b(merchant|trader|dealer|shop\s*keeper)\b',
                r'\b(miller|milling|flour\s*miller)\b',
                r'\b(baker|baking|bread\s*maker)\b',
                r'\b(shoemaker|cobbler|bootmaker|cordwainer)\b',
                r'\b(tailor|tailoring|seamstress|dressmaker|needle\s*woman)\b',
                r'\b(weaver|weaving|textile\s*worker|cloth\s*worker)\b',
                r'\b(mason|stonemason|bricklayer|stone\s*cutter)\b',
                r'\b(cooper|barrel\s*maker|cask\s*maker)\b',
                r'\b(butcher|meat\s*seller|slaughterer)\b',
                r'\b(grocer|provision\s*dealer|general\s*dealer)\b',
                r'\b(servant|domestic|housemaid|cook|kitchen\s*maid)\b',
                r'\b(nurse|nursing|hospital\s*nurse)\b',
                r'\b(doctor|physician|surgeon|medical\s*practitioner)\b',
                r'\b(lawyer|solicitor|barrister|legal\s*practitioner)\b',
                r'\b(minister|priest|clergyman|vicar|rector|chaplain)\b',
                r'\b(soldier|military|army|private|corporal|sergeant)\b',
                r'\b(sailor|seaman|mariner|navy|able\s*seaman)\b',
                r'\b(engineer|engineering|mechanical\s*engineer)\b',
                r'\b(machinist|machine\s*operator|factory\s*worker)\b',
                r'\b(foreman|supervisor|overseer|manager)\b',
                r'\b(proprietor|owner|master|employer)\b',
                r'\b(salesman|sales|commercial\s*traveller|agent)\b',
                r'\b(driver|carter|coachman|cab\s*driver)\b',
                r'\b(conductor|railway|railroad|train\s*driver)\b',
                r'\b(fireman|stoker|engine\s*driver)\b',
                r'\b(policeman|constable|police|detective)\b',
                r'\b(postman|postal|mail\s*carrier|letter\s*carrier)\b',
                r'\b(guard|watchman|gatekeeper|caretaker)\b',
            ]
            
            for pattern in occupation_keywords:
                matches = re.finditer(pattern, text_lower)
                for match in matches:
                    occupation = match.group(1).strip()
                    if occupation:
                        # Convert to standard form
                        occupation = self._standardize_occupation(occupation)
                        if occupation and occupation not in occupations:
                            occupations.append(occupation)
        
        return occupations
    
    def _validate_occupation_text(self, text: str) -> bool:
        """Validate that text looks like a legitimate occupation."""
        if not text or len(text) < 2:
            return False
        
        text_lower = text.lower().strip()
        
        # Reject obvious non-occupations
        non_occupation_indicators = [
            'unknown', 'none', 'n/a', 'blank', 'illegible', 'unclear',
            'head', 'wife', 'son', 'daughter', 'child', 'infant',
            'married', 'single', 'widow', 'widower',
            'england', 'wales', 'scotland', 'ireland', 'london',
            'born', 'died', 'age', 'year', 'month', 'day',
            'class:', 'piece:', 'folio:', 'page:', 'district:',
            'enumeration', 'registration', 'sub-district',
        ]
        
        for indicator in non_occupation_indicators:
            if indicator in text_lower:
                return False
        
        # Must contain at least one letter
        if not re.search(r'[a-zA-Z]', text):
            return False
        
        # Reasonable length limits
        if len(text) > 50:  # Too long to be a simple occupation
            return False
        
        return True
    
    def _standardize_occupation(self, occupation: str) -> str:
        """Convert occupation variations to standard forms."""
        occupation = occupation.lower().strip()
        
        # Standardization mappings
        if 'labou' in occupation or 'labor' in occupation:
            if 'farm' in occupation or 'agric' in occupation:
                return 'Agricultural Labourer'
            else:
                return 'Labourer'
        elif 'farm' in occupation:
            return 'Farmer'
        elif 'min' in occupation or 'pit' in occupation or 'collier' in occupation or 'coal' in occupation:
            return 'Miner'
        elif 'teach' in occupation or 'school' in occupation:
            return 'Teacher'
        elif 'serv' in occupation and 'domestic' in occupation:
            return 'Domestic Servant'
        elif 'cloth' in occupation or 'text' in occupation or 'weav' in occupation:
            return 'Textile Worker'
        else:
            return occupation.title()

    def _extract_occupation_from_text(self, text: str):
        """Extract occupation from text using various patterns."""
        if not text:
            return None
        
        text = text.strip()
        text_lower = text.lower()
        
        # Direct occupation patterns
        occupation_patterns = [
            r'occupation:\s*([^;,\n]+)',
            r'profession:\s*([^;,\n]+)',
            r'trade:\s*([^;,\n]+)',
            r'job:\s*([^;,\n]+)',
            r'work:\s*([^;,\n]+)',
            r'employed\s+as:\s*([^;,\n]+)',
            r'worked\s+as:\s*([^;,\n]+)',
        ]
        
        import re
        for pattern in occupation_patterns:
            match = re.search(pattern, text_lower)
            if match:
                occupation = match.group(1).strip()
                # Clean up common suffixes
                occupation = re.sub(r'\s*[;,].*$', '', occupation)
                return occupation.title()
        
        # Check if the entire text looks like an occupation
        # (no colons or semicolons, reasonable length)
        if len(text) < 50 and ':' not in text and ';' not in text:
            # Common occupation keywords
            occupation_keywords = [
                'farmer', 'laborer', 'labourer', 'miner', 'clerk', 'teacher', 'carpenter',
                'blacksmith', 'merchant', 'miller', 'baker', 'shoemaker', 'tailor',
                'weaver', 'mason', 'cooper', 'butcher', 'grocer', 'servant', 'cook',
                'nurse', 'doctor', 'lawyer', 'minister', 'priest', 'soldier', 'sailor',
                'engineer', 'machinist', 'foreman', 'superintendent', 'manager', 'owner',
                'proprietor', 'dealer', 'agent', 'salesman', 'driver', 'conductor',
                'fireman', 'policeman', 'postman', 'guard', 'keeper', 'attendant'
            ]
            
            if any(keyword in text_lower for keyword in occupation_keywords):
                return text.title()
        
        return None

    def debug_occupations_interactive(self, exclusion_list=None):
        """
        Interactive occupation extraction for this individual.
        Shows every candidate field (not excluded) in full, asks user if it contains occupation data.
        After all fields for this person, asks if user wants to continue to next person.
        """
        if exclusion_list is None:
            exclusion_list = [
                "archive", "national archives", "relationship", "relation", "marital", "gsu", "folio",
                "ancestry family tree", "general register office", "census record"
            ]
        exclusion_list = [e.lower() for e in exclusion_list]

        # Gather all candidate text blobs (from self and all linked sources)
        blobs = self._get_all_linked_text(self.raw_record, visited_refs=set())

        found_occupations = []
        for idx, text in enumerate(blobs, 1):
            text_lower = text.lower()
            if any(excl in text_lower for excl in exclusion_list):
                continue  # skip excluded fields

            print(f"\n--- DEBUG: {self.name} [{self.xref_id}] - Field {idx} ---")
            print(f"Text:\n{text}\n")
            user_input = input("Does this field contain occupation data? (y/n/stop): ").strip().lower()
            if user_input == "stop":
                print("Stopping debug session.")
                return found_occupations
            if user_input == "y":
                found_occupations.append(text)

        print(f"\nFinished reviewing all fields for {self.name} [{self.xref_id}].")
        return found_occupations

    def _get_all_linked_text(self, record, visited_refs: set, depth: int = 0) -> list:
        """
        Recursively collect every NOTE/TEXT/DATA/PAGE/CONT/OCCU/PROF tag value
        from record and any SOUR-linked records.
        """
        if depth > 20 or record is None:
            return []
        blobs = []
        xref = getattr(record, 'xref_id', None)
        if xref and xref in visited_refs:
            return []
        if xref:
            visited_refs.add(xref)

        # 1) collect text on this record
        if getattr(record, 'tag', None) in ['NOTE','TEXT','DATA','PAGE','CONT','OCCU','PROF'] and record.value:
            blobs.append(str(record.value).strip())

        # 2) recurse sub_records (excluding SOUR pointers)
        for sub in getattr(record, 'sub_records', []) or []:
            if getattr(sub, 'tag', None) != 'SOUR':
                blobs.extend(self._get_all_linked_text(sub, visited_refs, depth+1))

        # 3) resolve SOUR pointer at this level
        if getattr(record, 'tag', None) == 'SOUR' and record.value:
            sid = str(record.value).strip()
            if sid.startswith('@') and sid.endswith('@'):
                src = getattr(self.gedcom_db, '_source_index', {}).get(sid)
                if src:
                    blobs.extend(self._get_all_linked_text(src, visited_refs, depth+1))

        return blobs

    def is_deceased(self) -> bool:
        """
        Determine if this individual is deceased based on available death information.
        Checks both death_date and death_year properties, plus raw GEDCOM death records.
        Also assumes anyone over 120 years old is deceased.
        """
        # Check parsed death date/year first
        if self.death_date or self.death_year:
            return True
        
        # Check raw GEDCOM record for any DEAT tag (even without date)
        if hasattr(self, 'raw_record') and self.raw_record:
            for sub in self.raw_record.sub_records:
                if sub.tag == 'DEAT':
                    return True  # Death event exists, even if no date
        
        # Check if age is over 120 (assume deceased)
        current_age = self.calculate_age()
        if current_age and current_age > 120:
            return True
        
        return False

    def get_death_info(self) -> dict:
        """
        Get comprehensive death information for debugging.
        """
        info = {
            'has_death_date': self.death_date is not None,
            'has_death_year': self.death_year is not None,
            'death_date_value': self.death_date,
            'death_year_value': self.death_year,
            'has_deat_tag': False,
            'raw_deat_values': []
        }
        
        if hasattr(self, 'raw_record') and self.raw_record:
            for sub in self.raw_record.sub_records:
                if sub.tag == 'DEAT':
                    info['has_deat_tag'] = True
                    for sub2 in getattr(sub, 'sub_records', []):
                        if sub2.tag == 'DATE' and sub2.value:
                            info['raw_deat_values'].append(str(sub2.value))
        
        return info

class Ged4PyFamily(Family):
    """Family wrapper for ged4py records."""
    
    def __init__(self, xref_id: str, raw_record):
        super().__init__(xref_id, raw_record)
    
    def get_husband(self) -> Optional['Individual']:
        """Get the husband/father in this family."""
        if not self.raw_record:
            return None
        
        husband_ref = self.raw_record.husband
        if husband_ref:
            return Ged4PyIndividual(husband_ref.xref_id, husband_ref)
        return None
    
    def get_wife(self) -> Optional['Individual']:
        """Get the wife/mother in this family.""" 
        if not self.raw_record:
            return None
            
        wife_ref = self.raw_record.wife
        if wife_ref:
            return Ged4PyIndividual(wife_ref.xref_id, wife_ref)
        return None
    
    def get_children(self) -> List['Individual']:
        """Get all children in this family."""
        if not self.raw_record:
            return []
            
        children = []
        for child_ref in self.raw_record.children:
            children.append(Ged4PyIndividual(child_ref.xref_id, child_ref))
        return children

class Ged4PyGedcomDB(GedcomDB):
    """GEDCOM database implementation using ged4py library."""
    
    def __init__(self):
        super().__init__()
        self.capabilities = {
            'read', 'search', 'analyze', 'dates', 'places', 'occupations',
            'relationships', 'data_quality', "marriage"
        }
        self._parser = None
        self._individuals_cache = None
        self._families_cache = None
        
        # Relationship indexes for fast lookups
        self._individual_index = {}  # xref_id -> Individual
        self._family_index = {}      # xref_id -> Family
        self._source_index = {}      # xref_id -> Source record
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

        self._geocoding_cache = {}
        self._geocoding_cache_file = self._cache_dir / 'geocoding_cache.json'

        self._places_config = None
        self._places_config_file = self._base_dir / 'places_config.json'
    
    @property
    def records(self):
        """Access to source records for occupation extraction."""
        return self._source_index

    def _load_places_config(self):
        """Load places_config.json into memory once."""
        try:
            if self._places_config_file.exists():
                with open(self._places_config_file, 'r', encoding='utf-8') as f:
                    self._places_config = json.load(f)
                print(f"Loaded places configuration from {self._places_config_file}")
            else:
                self._places_config = {}
                print("No places_config.json found, using empty configuration.")
        except Exception as e:
            print(f"Error loading places configuration: {e}")
            self._places_config = {}

    def _select_gedcom_file(self) -> Optional[str]:
        """Present a menu of .ged files in the 'ged' subfolder for user selection."""
        ged_folder = self._base_dir / 'ged'
        
        if not ged_folder.exists():
            print(f"Error: 'ged' folder not found at {ged_folder}")
            return None
        
        # Find all .ged files
        ged_files = list(ged_folder.glob('*.ged'))
        
        if not ged_files:
            print(f"No .ged files found in {ged_folder}")
            return None
        
        # Sort by modification time (most recent first)
        ged_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        
        print("\n=== Available GEDCOM Files ===")
        print("(Ordered by date, most recent first)\n")
        
        for i, ged_file in enumerate(ged_files, 1):
            # Get file stats
            stat = ged_file.stat()
            size_mb = stat.st_size / (1024 * 1024)
            modified_time = datetime.fromtimestamp(stat.st_mtime)
            
            # Mark the most recent file as default
            default_marker = " (DEFAULT)" if i == 1 else ""
            
            print(f"{i:2}. {ged_file.name}{default_marker}")
            print(f"    Modified: {modified_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"    Size: {size_mb:.1f} MB")
            print()
        
        # Get user selection
        while True:
            try:
                choice = input(f"Select file (1-{len(ged_files)}, or Enter for default): ").strip()
                
                if not choice:
                    # Default to most recent (first in list)
                    selected_file = ged_files[0]
                    break
                
                index = int(choice) - 1
                if 0 <= index < len(ged_files):
                    selected_file = ged_files[index]
                    break
                else:
                    print(f"Please enter a number between 1 and {len(ged_files)}.")
            except ValueError:
                print("Please enter a valid number or press Enter for default.")
        
        # Return relative path from base directory
        relative_path = selected_file.relative_to(self._base_dir)
        print(f"\nSelected: {selected_file.name}")
        return str(relative_path)

    def _build_indexes(self):
        """Build relationship indexes for fast lookups."""
        if not self.is_loaded:
            return
        
        # Clear existing indexes
        self._individual_index.clear()
        self._family_index.clear()
        self._source_index.clear()
        self._parent_index.clear()
        self._child_index.clear()
        self._spouse_index.clear()
        self._family_members.clear()
        
        full_path = self._base_dir / self.file_path
        with GedcomReader(str(full_path)) as parser:
            # First pass: Index all individuals, families, and sources (streaming, not loading all into memory)
            for indi in parser.records0('INDI'):
                # Pass a reference to this database instance (self) to the individual
                individual = Ged4PyIndividual(indi.xref_id, indi, self)
                self._individual_index[indi.xref_id] = individual
                self._parent_index[indi.xref_id] = set()
                self._child_index[indi.xref_id] = set()
                self._spouse_index[indi.xref_id] = set()
            
            for fam in parser.records0('FAM'):
                family = Ged4PyFamily(fam.xref_id, fam)
                self._family_index[fam.xref_id] = family
                self._family_members[fam.xref_id] = {'parents': set(), 'children': set()}
            
            # Index source records for occupation extraction
            for sour in parser.records0('SOUR'):
                self._source_index[sour.xref_id] = sour
            
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
                individuals.append(Ged4PyIndividual(indi.xref_id, indi, self))
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
                    return Ged4PyIndividual(indi.xref_id, indi, self)
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
                indi_wrapper = Ged4PyIndividual(indi.xref_id, indi, self)
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
                    
                    indi_wrapper = Ged4PyIndividual(indi.xref_id, indi, self)
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

    def find_individual_by_name_with_details(self):
        """Find and show detailed information for an individual by name."""
        name = input("Enter name to search for: ").strip()
        if not name:
            return
        
        # Use the existing search method
        matches = self.search_individuals_by_name(name)
        
        if not matches:
            print(f"No individuals found matching '{name}'")
            input("\nPress Enter to continue...")
            return
        
        if len(matches) > 1:
            print(f"Found {len(matches)} matches:")
            for i, person in enumerate(matches, 1):
                birth_year = person.birth_year or "Unknown"
                
                if person.is_deceased():
                    death_year = person.death_year or "Unknown"
                    death_display = f", died {death_year}"
                elif person.calculate_age() and person.calculate_age() > 120:
                    # Assume deceased if over 120
                    death_display = ", died Unknown"
                else:
                    death_display = ""  # Don't show death info if living
                
                print(f"{i}. {person.name} (born {birth_year}{death_display})")

            try:
                choice = int(input("Select person (number): "))
                if 1 <= choice <= len(matches):
                    person = matches[choice - 1]
                else:
                    print("Invalid selection")
                    input("\nPress Enter to continue...")
                    return
            except ValueError:
                print("Invalid selection")
                input("\nPress Enter to continue...")
                return
        else:
            person = matches[0]
        
        # Ask if user wants debug data
        debug_choice = input("Show debug/raw GEDCOM data including birth location fields? (y/N): ").strip().lower()
        show_debug = debug_choice == 'y'
        
        print(f"\n" + "="*80)
        print(f"INDIVIDUAL DETAILS: {person.name}")
        print("="*80)
        
        # Basic information
        print(f"GEDCOM ID: {person.xref_id}")
        print(f"Name: {person.name}")
        
        # Birth information
        print(f"\nBIRTH INFORMATION:")
        print(f"  Birth Date: {person.birth_date.strftime('%d %b %Y') if person.birth_date else 'Unknown'}")
        print(f"  Birth Year: {person.birth_year or 'Unknown'}")
        print(f"  Birth Place: {person.birth_place or 'Unknown'}")
        
        # Death information
        print(f"\nDEATH INFORMATION:")
        current_age = person.calculate_age()
        
        # Enhanced deceased logic
        if person.is_deceased():
            print(f"  Is Deceased: Yes")
            print(f"  Death Date: {person.death_date.strftime('%d %b %Y') if person.death_date else 'Unknown'}")
            print(f"  Death Year: {person.death_year or 'Unknown'}")
        elif current_age and current_age > 120:
            print(f"  Is Deceased: Yes (assumed - age over 120)")
            print(f"  Death Date: Unknown")
            print(f"  Death Year: Unknown")
        else:
            print(f"  Is Deceased: No")
            # Don't show death date/year for living people
        
        # Age information
        print(f"  Age: {current_age or 'Unknown'}")
        if current_age and current_age > 120:
            print(f"  Note: Age over 120 suggests data error or person assumed deceased")
        
        # Family relationships
        parents = self.get_parents_fast(person.xref_id)
        spouses = self.get_spouses_fast(person.xref_id)
        children = self.get_children_fast(person.xref_id)
        siblings = self.get_siblings_fast(person.xref_id)
        
        print(f"\nFAMILY RELATIONSHIPS:")
        print(f"  Parents: {len(parents)}")
        for parent in parents:
            print(f"    - {parent.name} (born {parent.birth_year or 'Unknown'})")
        
        print(f"  Spouses: {len(spouses)}")
        for spouse in spouses:
            print(f"    - {spouse.name} (born {spouse.birth_year or 'Unknown'})")
        
        print(f"  Children: {len(children)}")
        for child in children:
            print(f"    - {child.name} (born {child.birth_year or 'Unknown'})")
        
        print(f"  Siblings: {len(siblings)}")
        for sibling in siblings:
            print(f"    - {sibling.name} (born {sibling.birth_year or 'Unknown'})")
        
        # Occupations
        occupations = person.get_occupations()
        print(f"\nOCCUPATIONS:")
        if occupations:
            for i, occ in enumerate(occupations, 1):
                print(f"  {i}. {occ['occupation']} (source: {occ['source']})")
        else:
            print("  None found")
        
        # Debug section for birth location fields
        if show_debug:
            print(f"\n" + "="*80)
            print("DEBUG: BIRTH LOCATION ANALYSIS")
            print("="*80)
            
            print(f"\nCURRENT birth_place PROPERTY:")
            print(f"  Value: '{person.birth_place or 'None'}'")
            print(f"  Source: BIRT > PLAC tag only")
            
            # Check for all possible birth location fields
            birth_location_fields = []
            
            def extract_birth_locations(record, path="", depth=0):
                if depth > 10:  # Prevent infinite recursion
                    return
                
                if hasattr(record, 'sub_records'):
                    for sub in record.sub_records:
                        current_path = f"{path}/{sub.tag}" if path else sub.tag
                        
                        # Check if this is a birth event
                        if sub.tag == 'BIRT':
                            print(f"\n  Found BIRT event at {current_path}:")
                            # Look for all sub-records under BIRT
                            for birth_sub in getattr(sub, 'sub_records', []):
                                birth_path = f"{current_path}/{birth_sub.tag}"
                                value = getattr(birth_sub, 'value', None)
                                print(f"    {birth_sub.tag}: {value}")
                                
                                if birth_sub.tag in ['PLAC', 'ADDR', 'NOTE'] and value:
                                    birth_location_fields.append({
                                        'path': birth_path,
                                        'tag': birth_sub.tag,
                                        'value': str(value)
                                    })
                                
                                # Check for nested records (like source data)
                                if hasattr(birth_sub, 'sub_records'):
                                    for nested in birth_sub.sub_records:
                                        nested_path = f"{birth_path}/{nested.tag}"
                                        nested_value = getattr(nested, 'value', None)
                                        if nested_value:
                                            print(f"      {nested.tag}: {nested_value}")
                                            if nested.tag in ['TEXT', 'DATA', 'NOTE'] and 'birth' in str(nested_value).lower():
                                                birth_location_fields.append({
                                                    'path': nested_path,
                                                    'tag': nested.tag,
                                                    'value': str(nested_value),
                                                    'note': 'Contains birth keyword'
                                                })
                        
                        # Check for SOUR records that might contain birth info
                        elif sub.tag == 'SOUR' and sub.value:
                            source_id = str(sub.value).strip()
                            if source_id.startswith('@') and source_id.endswith('@'):
                                source_record = self._source_index.get(source_id)
                                if source_record:
                                    print(f"\n  Checking source reference: {source_id}")
                                    self._extract_source_birth_info(source_record, source_id, birth_location_fields)
                        
                        # Recursively check other records (but limit depth)
                        if depth < 3:
                            extract_birth_locations(sub, current_path, depth + 1)
            
            extract_birth_locations(person.raw_record)
            
            print(f"\n" + "="*50)
            print("SUMMARY OF ALL BIRTH LOCATION FIELDS FOUND:")
            print("="*50)
            
            if birth_location_fields:
                for i, field in enumerate(birth_location_fields, 1):
                    print(f"\n{i}. {field['tag']} field ({field['path']}):")
                    print(f"   Value: {field['value']}")
                    if 'note' in field:
                        print(f"   Note: {field['note']}")
            else:
                print("\nNo additional birth location fields found beyond main PLAC field.")
            
            print(f"\n" + "="*50)
            print("RECOMMENDATIONS:")
            print("="*50)
            
            if len(birth_location_fields) > 1:
                print("Multiple birth location fields found!")
                print("Consider modifying the birth_place property to check these additional fields:")
                for field in birth_location_fields[1:]:  # Skip first (current PLAC)
                    print(f"  - {field['tag']} fields under BIRT events")
                    print(f"  - Source document {field['tag']} fields")
            else:
                print("Only the standard BIRT > PLAC field contains birth location data.")
                print("This is the expected/normal case for most GEDCOM files.")
            
            # Show complete raw record structure if requested
            show_full_raw = input("\nShow complete raw GEDCOM structure? (y/N): ").strip().lower()
            if show_full_raw == 'y':
                print(f"\n" + "="*80)
                print("COMPLETE RAW GEDCOM STRUCTURE:")
                print("="*80)
                
                def show_record_structure(record, indent="  ", max_depth=8, current_depth=0):
                    if current_depth >= max_depth:
                        print(f"{indent}... (max depth reached)")
                        return
                    
                    if hasattr(record, 'sub_records'):
                        for sub in record.sub_records:
                            tag = getattr(sub, 'tag', 'NO_TAG')
                            value = getattr(sub, 'value', '')
                            
                            # Truncate very long values
                            if isinstance(value, str) and len(value) > 100:
                                display_value = value[:100] + "..."
                            else:
                                display_value = value
                            
                            print(f"{indent}{tag}: {display_value}")
                            
                            # Special handling for source references
                            if tag == 'SOUR' and str(value).startswith('@'):
                                source_id = str(value).strip()
                                source_record = self._source_index.get(source_id)
                                if source_record:
                                    print(f"{indent}  [Resolved source {source_id}:]")
                                    show_record_structure(source_record, indent + "    ", max_depth, current_depth + 1)
                            else:
                                show_record_structure(sub, indent + "  ", max_depth, current_depth + 1)
                
                show_record_structure(person.raw_record)
        
        print("="*80)
        input("\nPress Enter to continue...")

    def _extract_source_birth_info(self, source_record, source_id: str, birth_location_fields: list):
        """Extract birth location information from a source record."""
        def check_source_fields(record, path_prefix=""):
            if hasattr(record, 'sub_records'):
                for sub in record.sub_records:
                    tag = getattr(sub, 'tag', 'NO_TAG')
                    value = getattr(sub, 'value', '')
                    current_path = f"{path_prefix}/{tag}" if path_prefix else tag
                    
                    # Check if this field might contain birth location info
                    if tag in ['TEXT', 'DATA', 'NOTE', 'TITL', 'PAGE'] and value:
                        value_str = str(value).lower()
                        # Look for birth-related keywords and location indicators
                        birth_keywords = ['birth', 'born', 'birthplace', 'birth place', 'place of birth']
                        location_keywords = ['county', 'parish', 'district', 'town', 'city', 'village']
                        
                        has_birth_keyword = any(keyword in value_str for keyword in birth_keywords)
                        has_location_keyword = any(keyword in value_str for keyword in location_keywords)
                        
                        if has_birth_keyword or (has_location_keyword and len(str(value)) < 200):
                            birth_location_fields.append({
                                'path': f"SOURCE_{source_id}/{current_path}",
                                'tag': tag,
                                'value': str(value),
                                'note': f"Source field with {'birth' if has_birth_keyword else 'location'} keywords"
                            })
                            print(f"    {tag}: {str(value)[:100]}{'...' if len(str(value)) > 100 else ''}")
                    
                    # Recursively check sub-fields
                    check_source_fields(sub, current_path)
        
        check_source_fields(source_record)

    # ============ CACHING METHODS ============
    
    def _get_cache_file_base(self) -> str:
        """Get a unique cache file base name for the current GEDCOM file."""
        import hashlib
        # Create a hash of the relative file path for unique cache names
        path_hash = hashlib.md5(self.file_path.encode()).hexdigest()[:8]
        # Also include the filename (without extension) for readability
        file_stem = Path(self.file_path).stem

        return f"{file_stem}_{path_hash}"

    def _should_use_cache(self) -> bool:
        """Determine if we can use cached indexes."""
        try:
            cache_base = self._get_cache_file_base()
            metadata_file = self._cache_dir / f'{cache_base}_metadata.json'
            
            if not metadata_file.exists():
                return False
                
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
                
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
        except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
            # Expected exceptions when cache is invalid
            return False
        except Exception as e:
            # Unexpected exceptions should be logged, not hidden
            print(f"Unexpected error in cache validation: {e}")
            return False
    
    def _get_gedcom_stats(self) -> Optional[dict]:
        """Get current GEDCOM file stats using relative path."""
        try:
            gedcom_path = self._base_dir / self.file_path
            if not gedcom_path.exists():
                print(f"Warning: GEDCOM file not found at {gedcom_path}")
                return None
                
            stat = gedcom_path.stat()
            return {
                'gedcom_file': self.file_path,  # Store relative path
                'gedcom_size': stat.st_size,
                'gedcom_modified': stat.st_mtime
            }
        except Exception as e:
            print(f"Error getting GEDCOM stats: {e}")
            return None

    def show_gedcom_summary(self):
        """Display a summary of the loaded GEDCOM file."""
        if not self.is_loaded:
            print("No GEDCOM file loaded.")
            return
        
        print("\n" + "="*60)
        print("GEDCOM FILE SUMMARY")
        print("="*60)
        
        # Basic file info
        file_path = self._base_dir / self.file_path
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        file_name = file_path.name
        
        print(f"File: {file_name}")
        print(f"Size: {file_size_mb:.1f} MB")
        print(f"Path: {self.file_path}")
        
        # Record counts
        if self._indexes_built:
            # Use cached counts for speed
            individual_count = len(self._individual_index)
            family_count = len(self._family_index) 
            source_count = len(self._source_index)
        else:
            # Count from file
            individual_count = family_count = source_count = 0
            full_path = self._base_dir / self.file_path
            with GedcomReader(str(full_path)) as parser:
                for _ in parser.records0('INDI'):
                    individual_count += 1
                for _ in parser.records0('FAM'):
                    family_count += 1
                for _ in parser.records0('SOUR'):
                    source_count += 1
        
        print(f"\nRecord Counts:")
        print(f"  Individuals: {individual_count:,}")
        print(f"  Families: {family_count:,}")
        print(f"  Sources: {source_count:,}")
        
        # Date range analysis
        birth_years = []
        death_years = []
        
        if self._indexes_built:
            # Use indexed data
            for individual in self._individual_index.values():
                if individual.birth_year:
                    birth_years.append(individual.birth_year)
                if individual.death_year:
                    death_years.append(individual.death_year)
        else:
            # Scan file
            full_path = self._base_dir / self.file_path
            with GedcomReader(str(full_path)) as parser:
                for indi in parser.records0('INDI'):
                    indi_wrapper = Ged4PyIndividual(indi.xref_id, indi, self)
                    if indi_wrapper.birth_year:
                        birth_years.append(indi_wrapper.birth_year)
                    if indi_wrapper.death_year:
                        death_years.append(indi_wrapper.death_year)
        
        if birth_years or death_years:
            print(f"\nDate Ranges:")
            if birth_years:
                print(f"  Birth years: {min(birth_years)} - {max(birth_years)} ({len(birth_years)} records)")
            if death_years:
                print(f"  Death years: {min(death_years)} - {max(death_years)} ({len(death_years)} records)")
        
        # Ancestor filter status
        if hasattr(self, 'ancestor_filter_ids') and self.ancestor_filter_ids:
            filter_count = len(self.ancestor_filter_ids)
            root_name = getattr(self, 'root_ancestor_name', 'Unknown')
            print(f"\nTree Scope: Limited to {filter_count:,} individuals")
            print(f"Root Ancestor: {root_name}")
        else:
            print(f"\nTree Scope: Full database (no ancestor filter)")
        
        print("="*60)

    def _geocode_places_config(self):
        """Geocode any missing places from places_config.json on startup."""
        if not self._places_config:  # Use cached config
            return
        
        places_to_geocode = []
        
        # Define structural keys that should be skipped (not geocoded)
        structural_keys = {
            '_comment', 'nation_counties', 'county_places', 'nation_places',
            'local2_places', 'known_streets'
        }
        
        # Extract places from all levels of the hierarchy
        def extract_places_recursive(data, path=""):
            if isinstance(data, dict):
                for key, value in data.items():
                    if key in structural_keys:
                        # Skip the structural key itself, but process its contents
                        extract_places_recursive(value, f"{path}/{key}" if path else key)
                    else:
                        # This is a place name - check if we need to geocode it
                        if not self._is_place_cached(key):
                            places_to_geocode.append(key)
                        
                        # Recursively process the value
                        extract_places_recursive(value, f"{path}/{key}" if path else key)
                    
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, str) and not self._is_place_cached(item):
                        places_to_geocode.append(item)
                    else:
                        extract_places_recursive(item, path)
        
        # Process the entire config structure
        extract_places_recursive(self._places_config)
        
        if places_to_geocode:
            print(f"Geocoding {len(places_to_geocode)} new places from places_config.json...")
            for place_name in places_to_geocode:
                self._get_geocoded_location(place_name)
            
            # Save updated cache
            self._save_geocoding_cache()
        else:
            print("All places from places_config.json already geocoded.")

    def _is_place_cached(self, place_name: str) -> bool:
        """Check if a place is already cached, including substring matches and failed lookups."""
        if not place_name or not place_name.strip():
            return True  # Skip empty places
        
        place_name = place_name.strip()
        
        # Handle slash-separated places (e.g., "Shropshire/Salop", "Devon/Dorset")
        if '/' in place_name:
            # This is a slash-separated place from config - geocode both parts
            slash_parts = [p.strip() for p in place_name.split('/') if p.strip()]
            print(f"Processing slash-separated place: '{place_name}' → {slash_parts}")
            
            all_parts_cached = True
            for part in slash_parts:
                if part not in self._geocoding_cache:
                    all_parts_cached = False
                    break
            
            if all_parts_cached:
                print(f"All parts of '{place_name}' already cached")
                return True  # All parts already cached
            
            # Need to geocode the missing parts
            try:
                from geopy.geocoders import Nominatim
                import time
                
                geolocator = Nominatim(user_agent="family_tree_mapper_v1.0")
                
                for part in slash_parts:
                    if part not in self._geocoding_cache:
                        print(f"  Geocoding slash part: '{part}'")
                        
                        try:
                            location = geolocator.geocode(part, timeout=10)
                            
                            if location:
                                # Cache this individual part
                                cache_entry = {
                                    'lat': location.latitude,
                                    'lng': location.longitude,
                                    'cached_date': datetime.now().isoformat(),
                                    'source': 'nominatim_slash_part',
                                    'geocoded_address': location.address,
                                    'original_slash_group': place_name
                                }
                                self._geocoding_cache[part] = cache_entry
                                print(f"    ✓ '{part}' geocoded and cached")
                                
                                time.sleep(1)  # Rate limiting
                            else:
                                # Cache the failure
                                self._geocoding_cache[part] = {
                                    'lat': None,
                                    'lng': None,
                                    'cached_date': datetime.now().isoformat(),
                                    'source': 'failed_slash_part',
                                    'original_slash_group': place_name
                                }
                                print(f"    ✗ '{part}' not found")
                        
                        except Exception as e:
                            print(f"    ✗ Error geocoding '{part}': {e}")
                            # Cache the error
                            self._geocoding_cache[part] = {
                                'lat': None,
                                'lng': None,
                                'cached_date': datetime.now().isoformat(),
                                'source': 'error_slash_part',
                                'original_slash_group': place_name,
                                'error': str(e)
                            }
                
                return True  # We've processed this slash-separated place
                
            except Exception as e:
                print(f"Error processing slash-separated place '{place_name}': {e}")
                return False
        
        # Regular single place processing
        # Direct match - return True for ANY cached entry (successful OR failed)
        if place_name in self._geocoding_cache:
            return True  # Already cached, don't try again
        
        # Check if this place appears as part of a longer cached address
        place_lower = place_name.lower()
        for cached_key in self._geocoding_cache.keys():
            if place_lower in cached_key.lower():
                cached_data = self._geocoding_cache[cached_key]
                if cached_data.get('lat') is not None and cached_data.get('lng') is not None:
                    # Copy the coordinates to the shorter place name for future lookups
                    self._geocoding_cache[place_name] = {
                        'lat': cached_data['lat'],
                        'lng': cached_data['lng'],
                        'cached_date': datetime.now().isoformat(),
                        'source': 'derived_from_longer_address',
                        'derived_from': cached_key
                    }
                else:
                    # Copy the failed lookup to the shorter place name
                    self._geocoding_cache[place_name] = {
                        'lat': None,
                        'lng': None,
                        'cached_date': datetime.now().isoformat(),
                        'source': 'derived_failed_lookup',
                        'derived_from': cached_key
                    }
                return True  # Found in cache (successful or failed)
        
        return False  # Not cached at all

    def load_file(self, file_path: str = None) -> bool:
        print("""Load GEDCOM file using ged4py with intelligent caching and file selection.""")
        if GedcomReader is None:
            print("Error: ged4py library not available")
            return False
        
        try:
            # If no file path provided, show file selection menu
            if file_path is None:
                file_path = self._select_gedcom_file()
                if not file_path:
                    print("No file selected.")
                    return False
            else:
                # If a file path was provided, check if it's just a filename and look in ged folder
                file_path_obj = Path(file_path)
                if not file_path_obj.is_absolute() and not file_path_obj.exists():
                    # Try looking in the ged subfolder
                    ged_path = self._base_dir / 'ged' / file_path
                    if ged_path.exists():
                        file_path = str(ged_path.relative_to(self._base_dir))
            
            # Store the relative path from base directory
            if Path(file_path).is_absolute():
                self.file_path = str(Path(file_path).relative_to(self._base_dir))
            else:
                self.file_path = file_path
            
            # Clear all existing indexes and state when loading new file - DO THIS AFTER SETTING file_path
            self._individual_index = {}
            self._family_index = {}
            self._source_index = {}
            self._parent_index = {}
            self._child_index = {}
            self._spouse_index = {}
            self._family_members = {}
            self._indexes_built = False
            
            # Reset ancestor filter when loading new file
            if hasattr(self, 'ancestor_filter_ids'):
                self.ancestor_filter_ids = None
            if hasattr(self, 'root_ancestor_name'):
                self.root_ancestor_name = None
            
            # Test that we can open the file
            full_path = self._base_dir / self.file_path
            if not full_path.exists():
                print(f"Error: File not found: {full_path}")
                print("Available files in ged folder:")
                ged_folder = self._base_dir / 'ged'
                if ged_folder.exists():
                    for ged_file in ged_folder.glob('*.ged'):
                        print(f"  {ged_file.name}")
                return False
            
            # Test that we can parse the file
            try:
                with GedcomReader(str(full_path)) as parser:
                    # Test parsing by reading first record
                    for record in parser.records0('INDI'):
                        break  # Just test we can read at least one record
            except Exception as parse_error:
                print(f"\nError: GEDCOM file has parsing errors:")
                print(f"  {parse_error}")
                print(f"\nThis file appears to be corrupted or contains invalid GEDCOM syntax.")
                print(f"File: {full_path}")
                
                # Offer options to user
                while True:
                    print("\nOptions:")
                    print("1. Try a different file")
                    print("2. Exit program")
                    choice = input("Choose option (1-2): ").strip()
                    
                    if choice == '1':
                        # Try to select a different file
                        new_file_path = self._select_gedcom_file()
                        if new_file_path:
                            return self.load_file(new_file_path)  # Recursive call with new file
                        else:
                            return False
                    elif choice == '2':
                        return False
                    else:
                        print("Please enter 1 or 2.")
            
            self.is_loaded = True
            
            # Try to use cached indexes first
            if self._should_use_cache():
                start_time = time.time()
                print("Loading cached indexes...")
                if self._load_indexes_from_cache():
                    end_time = time.time()
                    print(f"Cached indexes loaded successfully. ({end_time - start_time:.3f} seconds)")
                    # Load geocoding cache after indexes
                    self._load_geocoding_cache()
                    # Geocode any missing places from places_config
                    self._geocode_places_config()
                    self.show_gedcom_summary()
                    return True
                else:
                    print("Failed to load cached indexes, rebuilding...")
            
            # Build indexes from scratch
            start_time = time.time()
            print("Building relationship indexes for fast lookups...")
            
            try:
                self._build_indexes()
            except Exception as index_error:
                print(f"\nError building indexes: {index_error}")
                print("This usually indicates corrupted GEDCOM data.")
                
                while True:
                    print("\nOptions:")
                    print("1. Try a different file")
                    print("2. Exit program")
                    choice = input("Choose option (1-2): ").strip()
                    
                    if choice == '1':
                        new_file_path = self._select_gedcom_file()
                        if new_file_path:
                            return self.load_file(new_file_path)
                        else:
                            return False
                    elif choice == '2':
                        return False
                    else:
                        print("Please enter 1 or 2.")
            
            # Cache the indexes for next time
            self._save_indexes_to_cache()
            end_time = time.time()
            print(f"Indexes built and cached successfully. ({end_time - start_time:.3f} seconds)")
            
            # Load geocoding cache and geocode places_config
            print("Geocoding places from places_config.json...")
            self._load_places_config()
            print("Loading geocoding cache...")
            self._load_geocoding_cache()
            print("Geocoding any missing places...")
            self._ensure_places_config_geocoded()
            
            # Show summary after successful load
            self.show_gedcom_summary()
            
            return True
        except Exception as e:
            print(f"Unexpected error loading GEDCOM file: {e}")
            print("This may indicate a serious file corruption or system issue.")
            return False

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
            cache_base = self._get_cache_file_base()
            
            # Load relationship indexes only
            with open(self._indexes_dir / f'{cache_base}_parent_index.pkl', 'rb') as f:
                self._parent_index = pickle.load(f)
            
            with open(self._indexes_dir / f'{cache_base}_child_index.pkl', 'rb') as f:
                self._child_index = pickle.load(f)
            
            with open(self._indexes_dir / f'{cache_base}_spouse_index.pkl', 'rb') as f:
                self._spouse_index = pickle.load(f)
            
            with open(self._indexes_dir / f'{cache_base}_family_members.pkl', 'rb') as f:
                self._family_members = pickle.load(f)
            
            # Rebuild individual, family, and source indexes from GEDCOM file
            full_path = self._base_dir / self.file_path
            with GedcomReader(str(full_path)) as parser:
                for indi in parser.records0('INDI'):
                    # Pass a reference to this database instance (self) to the individual
                    individual = Ged4PyIndividual(indi.xref_id, indi, self)
                    self._individual_index[indi.xref_id] = individual
                
                for fam in parser.records0('FAM'):
                    family = Ged4PyFamily(fam.xref_id, fam)
                    self._family_index[fam.xref_id] = family
                
                # Index source records for occupation extraction
                for sour in parser.records0('SOUR'):
                    self._source_index[sour.xref_id] = sour
            
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
            
            cache_base = self._get_cache_file_base()
            
            # Save only the relationship mappings (sets of IDs), not the full objects
            with open(self._indexes_dir / f'{cache_base}_parent_index.pkl', 'wb') as f:
                pickle.dump(self._parent_index, f)
            
            with open(self._indexes_dir / f'{cache_base}_child_index.pkl', 'wb') as f:
                pickle.dump(self._child_index, f)
            
            with open(self._indexes_dir / f'{cache_base}_spouse_index.pkl', 'wb') as f:
                pickle.dump(self._spouse_index, f)
            
            with open(self._indexes_dir / f'{cache_base}_family_members.pkl', 'wb') as f:
                pickle.dump(self._family_members, f)
            
            # Save metadata with updated index names
            current_stats = self._get_gedcom_stats()
            if current_stats:
                metadata = {
                    **current_stats,
                    'indexes_created': datetime.now().timestamp(),
                    'cache_version': self._cache_version,
                    'cache_base': cache_base,
                    'available_indexes': [
                        f'{cache_base}_parent_index',
                        f'{cache_base}_child_index', 
                        f'{cache_base}_spouse_index',
                        f'{cache_base}_family_members'
                    ]
                }
                
                # Use file-specific metadata filename
                metadata_file = self._cache_dir / f'{cache_base}_metadata.json'
                with open(metadata_file, 'w') as f:
                    json.dump(metadata, f, indent=2)
                    
        except Exception as e:
            print(f"Error saving indexes to cache: {e}")
            # Don't fail the entire load operation if caching fails
            pass
    
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

    def scan_census_sources_for_occupations(self, occupations_config_path="occupations_config.json"):
        """
        Scan all census source records for fields matching occupation keywords/patterns.
        Prints record type, field name, full text, and matching occupation(s).
        """

        # Load occupation keywords/patterns
        with open(occupations_config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        keywords = set()
        for group in config.get("occupation_groups", {}).values():
            keywords.update([k.lower() for k in group])
        for pat in config.get("occupation_patterns", {}).values():
            keywords.add(pat.lower())

        #print(f"Loaded occupation keywords: {keywords}")

        #print(f"DEBUG: ancestor_filter_ids = {getattr(self, 'ancestor_filter_ids', None)}")

        # Determine which individuals to process
        if hasattr(self, "ancestor_filter_ids") and self.ancestor_filter_ids:
            individuals = [self._individual_index[xref_id] for xref_id in self.ancestor_filter_ids if xref_id in self._individual_index]
        else:
            individuals = list(self._individual_index.values())

        count = 0
        for ind in individuals:
            name = getattr(ind, "name", None) or ind.xref_id
            # Only process John Samuel Moss
            if name != "John Samuel Moss":
                continue
            birth_year = getattr(ind, "birth_year", None)
            death_year = getattr(ind, "death_year", None)
            print(f"\nPerson: {name}, Birth Year: {birth_year}, Death Year: {death_year}")

            # Recursively print all census records and any linked records
            def print_all_fields(record, indent="    ", visited=None):
                if visited is None:
                    visited = set()
                xref = getattr(record, "xref_id", None)
                if xref and xref in visited:
                    return
                if xref:
                    visited.add(xref)
                for field in getattr(record, "sub_records", []):
                    tag = getattr(field, "tag", None)
                    value = getattr(field, "value", None)
                    print(f"{indent}{tag}: {value}")
                    # If this is a SOUR pointer, recursively print the linked source record
                    if tag == "SOUR" and value:
                        source_id = str(value).strip()
                        source_record = self._source_index.get(source_id)
                        if source_record:
                            print(f"{indent}-- Recursing into linked source record {source_id} --")
                            print_all_fields(source_record, indent + "    ", visited)
                    # Recursively print sub-sub-records
                    if hasattr(field, "sub_records") and field.sub_records:
                        print_all_fields(field, indent + "    ", visited)

            # Find all census sources attached to this individual and print everything recursively
            for sub in getattr(ind.raw_record, "sub_records", []):
                if getattr(sub, "tag", None) == "SOUR" and sub.value:
                    source_id = str(sub.value).strip()
                    source_record = self._source_index.get(source_id)
                    if source_record:
                        # Check if source is a census
                        for src_sub in getattr(source_record, "sub_records", []):
                            if getattr(src_sub, "tag", None) in ("TITL", "TITLE") and src_sub.value:
                                title = str(src_sub.value).lower()
                                if "census" in title:
                                    print(f"\n  Census record for source {source_id}:")
                                    print_all_fields(source_record, indent="    ")

            count += 1

            #cont = input("Continue to next person? (y/n): ").strip().lower()
            #if cont not in ("y", "yes", ""):
            #    print("Exiting census scan.")
            #    break

        print(f"\nTotal individuals processed: {count}")
    
    def dump_wedding_records(self):
        """
        Dump all data under wedding (marriage) records for each family and for individuals.
        Merge individual marriage records with family ones if the individual's marriage date matches the family's marriage date.
        """

        def print_subfields(rec, indent="    "):
            for field in getattr(rec, "sub_records", []):
                tag = getattr(field, "tag", None)
                value = getattr(field, "value", None)
                print(f"{indent}{tag}: {value}")
                if hasattr(field, "sub_records") and field.sub_records:
                    print_subfields(field, indent + "    ")

        print("\n=== Dumping all wedding (marriage) records for all families and individuals ===\n")
        family_marriages = []
        individual_marriages = []

        # Determine which individuals to process
        if hasattr(self, "ancestor_filter_ids") and self.ancestor_filter_ids:
            individuals = [self._individual_index[xref_id] for xref_id in self.ancestor_filter_ids if xref_id in self._individual_index]
        else:
            individuals = list(self._individual_index.values())

        # 1. Collect family marriage records
        for fam in self._family_index.values():
            fam_id = fam.xref_id
            husband_name = "Unknown"
            wife_name = "Unknown"
            husband_id = None
            wife_id = None
            for sub in getattr(fam.raw_record, "sub_records", []):
                if getattr(sub, "tag", None) == "HUSB" and sub.value:
                    husband_id = str(sub.value)
                    husb = self._individual_index.get(husband_id)
                    if husb:
                        husband_name = husb.name
                if getattr(sub, "tag", None) == "WIFE" and sub.value:
                    wife_id = str(sub.value)
                    wife = self._individual_index.get(wife_id)
                    if wife:
                        wife_name = wife.name
            for sub in getattr(fam.raw_record, "sub_records", []):
                if getattr(sub, "tag", None) in ("MARR", "MARRIAGE", "WEDDING"):
                    # Try to get marriage date
                    marriage_date = None
                    for sub2 in getattr(sub, "sub_records", []):
                        if getattr(sub2, "tag", None) == "DATE" and sub2.value:
                            marriage_date = str(sub2.value).strip()
                            break
                    family_marriages.append({
                        "fam_id": fam_id,
                        "husband_name": husband_name,
                        "wife_name": wife_name,
                        "husband_id": husband_id,
                        "wife_id": wife_id,
                        "record": sub,
                        "marriage_date": marriage_date
                    })

        # 2. Collect individual marriage records
        for ind in individuals:
            name = getattr(ind, "name", None) or ind.xref_id
            print(f"name = {name}")
            for sub in getattr(ind.raw_record, "sub_records", []):
                if getattr(sub, "tag", None) in ("MARR", "MARRIAGE", "WEDDING"):
                    # Try to get marriage date
                    marriage_date = None
                    for sub2 in getattr(sub, "sub_records", []):
                        if getattr(sub2, "tag", None) == "DATE" and sub2.value:
                            marriage_date = str(sub2.value).strip()
                            break
                    individual_marriages.append({
                        "name": name,
                        "xref_id": ind.xref_id,
                        "record": sub,
                        "marriage_date": marriage_date
                    })

        # 3. Print family marriage records and merge with matching individual records by marriage date
        matched_individuals = set()
        print("=== Family Marriage Records ===")
        family_count = 0
        for fam in family_marriages:
            husband_in_filter = False
            if hasattr(self, "ancestor_filter_ids") and self.ancestor_filter_ids:
                husband_in_filter = fam['husband_id'] in self.ancestor_filter_ids
            else:
                husband_in_filter = True  # No filter, include all

            if not husband_in_filter:
                continue  # Skip families not in filter

            print(f"\nFamily: {fam['fam_id']}")
            print(f"  Husband: {fam['husband_name']}")
            print(f"  Wife: {fam['wife_name']}")
            print(f"  {fam['record'].tag}: {getattr(fam['record'], 'value', None)}")
            print(f"  Marriage Date: {fam['marriage_date']}")

            # Print all info from the wedding source document(s)
            for sub in getattr(fam['record'], "sub_records", []):
                if getattr(sub, "tag", None) == "SOUR" and sub.value:
                    source_id = str(sub.value).strip()
                    source_record = self._source_index.get(source_id)
                    if source_record:
                        #print(f"    --- Wedding Source Document ({source_id}) ---")
                        def print_source_fields(record, indent="      "):
                            for field in getattr(record, "sub_records", []):
                                tag = getattr(field, "tag", None)
                                value = getattr(field, "value", None)
                                #print(f"{indent}{tag}: {value}")
                                if hasattr(field, "sub_records") and field.sub_records:
                                    print_source_fields(field, indent + "    ")
                        print_source_fields(source_record)

            # Check for matching individual marriage records by marriage date
            for ind_mar in individual_marriages:
                if ind_mar["marriage_date"] and fam["marriage_date"] and ind_mar["marriage_date"] == fam["marriage_date"]:
                    print(f"  [MATCHED INDIVIDUAL RECORD: {ind_mar['name']} ({ind_mar['xref_id']})]")
                    print(f"    {ind_mar['record'].tag}: {getattr(ind_mar['record'], 'value', None)}")
                    print(f"    Marriage Date: {ind_mar['marriage_date']}")
                    print_subfields(ind_mar['record'], indent="      ")
                    matched_individuals.add(ind_mar["xref_id"])
            family_count += 1

        # 4. Print unmatched individual marriage records
        print("\n=== Individual Marriage Records (not matched to any family) ===")
        individual_count = 0
        for ind_mar in individual_marriages:
            if ind_mar["xref_id"] not in matched_individuals:
                print(f"\nIndividual: {ind_mar['name']} [{ind_mar['xref_id']}]")
                print(f"  {ind_mar['record'].tag}: {getattr(ind_mar['record'], 'value', None)}")
                print(f"  Marriage Date: {ind_mar['marriage_date']}")
                print_subfields(ind_mar['record'])
                individual_count += 1

        print(f"\nTotal family marriage records: {family_count}")
        print(f"Total individual marriage records (not matched): {individual_count}")

    def get_wedding_ages_data(self) -> dict:
        """Get wedding age analysis data - refactored from analyse_wedding_ages."""
        # Use ancestor filter if present
        if hasattr(self, "ancestor_filter_ids") and self.ancestor_filter_ids:
            individuals = [self._individual_index[xref_id] for xref_id in self.ancestor_filter_ids if xref_id in self._individual_index]
        else:
            individuals = list(self._individual_index.values())

        # Build lookup for birth years and names
        birth_years = {ind.xref_id: ind.birth_year for ind in individuals if ind.birth_year}
        names = {ind.xref_id: ind.name for ind in individuals}

        # Collect data
        wedding_data = {
            'decade_data': {},
            'century_data': {},
            'groom_ages': [],
            'bride_ages': [],
            'groom_over_40': [],
            'bride_over_40': [],
            'groom_under_16': [],
            'bride_under_16': []
        }

        for fam in self._family_index.values():
            husband_id = wife_id = None
            husband_birth = wife_birth = marriage_year = None

            # Get husband and wife IDs
            for sub in getattr(fam.raw_record, "sub_records", []):
                if getattr(sub, "tag", None) == "HUSB" and sub.value:
                    husband_id = str(sub.value)
                if getattr(sub, "tag", None) == "WIFE" and sub.value:
                    wife_id = str(sub.value)
            
            # Get marriage year
            for sub in getattr(fam.raw_record, "sub_records", []):
                if getattr(sub, "tag", None) in ("MARR", "MARRIAGE", "WEDDING"):
                    for sub2 in getattr(sub, "sub_records", []):
                        if getattr(sub2, "tag", None) == "DATE" and sub2.value:
                            try:
                                import re
                                date_str = str(sub2.value).strip()
                                match = re.search(r'(\d{4})', date_str)
                                marriage_year = int(match.group(1)) if match else None
                            except Exception:
                                marriage_year = None
                            break

            if not marriage_year:
                continue

            decade = (marriage_year // 10) * 10
            century = (marriage_year // 100) * 100

            # Process groom
            husband_birth = birth_years.get(husband_id)
            if husband_birth and marriage_year >= husband_birth:
                age = marriage_year - husband_birth
                person_data = {
                    "name": names.get(husband_id, husband_id),
                    "age": age,
                    "marriage_year": marriage_year,
                    "fam_id": fam.xref_id
                }
                
                if age > 40:
                    wedding_data['groom_over_40'].append(person_data)
                if age < 16:
                    wedding_data['groom_under_16'].append(person_data)
                if 16 <= age < 120:
                    wedding_data['groom_ages'].append(age)
                    wedding_data['decade_data'].setdefault(decade, {"bride": [], "groom": []})["groom"].append(age)
                    wedding_data['century_data'].setdefault(century, {"bride": [], "groom": []})["groom"].append(age)

            # Process bride (similar logic)
            wife_birth = birth_years.get(wife_id)
            if wife_birth and marriage_year >= wife_birth:
                age = marriage_year - wife_birth
                person_data = {
                    "name": names.get(wife_id, wife_id),
                    "age": age,
                    "marriage_year": marriage_year,
                    "fam_id": fam.xref_id
                }
                
                if age > 40:
                    wedding_data['bride_over_40'].append(person_data)
                if age < 16:
                    wedding_data['bride_under_16'].append(person_data)
                if 16 <= age < 120:
                    wedding_data['bride_ages'].append(age)
                    wedding_data['decade_data'].setdefault(decade, {"bride": [], "groom": []})["bride"].append(age)
                    wedding_data['century_data'].setdefault(century, {"bride": [], "groom": []})["bride"].append(age)

        return wedding_data

    def analyse_wedding_ages(self):
        """Print wedding age analysis - now uses the data function."""
        wedding_data = self.get_wedding_ages_data()
        
        def avg(lst):
            return round(sum(lst) / len(lst), 2) if lst else None
        def minmax(lst):
            return (min(lst), max(lst)) if lst else (None, None)

        print("\n=== Wedding Age Analysis ===\n")
        
        # Print all the same output as before, but using the returned data
        groom_ages = wedding_data['groom_ages']
        bride_ages = wedding_data['bride_ages']
        
        print(f"Overall average groom age at marriage: {avg(groom_ages)} ({len(groom_ages)} records)")
        print(f"Overall average bride age at marriage: {avg(bride_ages)} ({len(bride_ages)} records)\n")
        
        # ... rest of your existing printing logic, but using wedding_data
        
        # The key benefit: this data is now reusable for mapping or GUI!
        return wedding_data

    def _load_geocoding_cache(self):
        """Load geocoding cache from file into memory."""
        try:
            cache_was_empty = False
            if self._geocoding_cache_file.exists():
                with open(self._geocoding_cache_file, 'r', encoding='utf-8') as f:
                    self._geocoding_cache = json.load(f)
                print(f"Loaded {len(self._geocoding_cache)} geocoded locations from cache.")
            else:
                self._geocoding_cache = {}
                print("No geocoding cache found, starting fresh.")
                cache_was_empty = True
            
            # If cache is empty, check and load places_config if needed
            if cache_was_empty or len(self._geocoding_cache) == 0:
                # Ensure places_config is loaded first
                if not hasattr(self, '_places_config') or self._places_config is None:
                    self._load_places_config()
                    
                # Now we can safely check and use places_config
                if self._places_config:
                    print("Cache is empty - populating with places from places_config.json...")
                    self._ensure_places_config_geocoded()
                
        except Exception as e:
            print(f"Error loading geocoding cache: {e}")
            self._geocoding_cache = {}

    def _save_geocoding_cache(self):
        """Save geocoding cache from memory to file."""
        try:
            self._cache_dir.mkdir(exist_ok=True)
            with open(self._geocoding_cache_file, 'w', encoding='utf-8') as f:
                json.dump(self._geocoding_cache, f, indent=2, ensure_ascii=False)
            print(f"Saved {len(self._geocoding_cache)} locations to geocoding cache.")
        except Exception as e:
            print(f"Error saving geocoding cache: {e}")

    def _get_geocoded_location(self, place_name: str, person_info: dict = None, debug: bool = False):
        """Get geocoded location using enhanced UK-preference algorithm with progressive left-trimming."""
        if not place_name or not place_name.strip():
            return None
        
        place_key = place_name.strip().lower() 
        
        if debug:
            print(f"\n--- GEOCODING DEBUG ---")
            print(f"Original input: '{place_name}'")
            print(f"Cache key: '{place_key}'")

        # Direct cache match first - silent
        if place_key in self._geocoding_cache:
            cached_data = self._geocoding_cache[place_key]
            
            if debug:
                print(f"✓ CACHE HIT: Found in geocoding cache")
                print(f"  Source: {cached_data.get('source', 'Unknown')}")
                if cached_data.get('geocoded_address'):
                    print(f"  Geocoded address: {cached_data.get('geocoded_address')}")
                if cached_data.get('lat') is not None:
                    print(f"  Coordinates: {cached_data.get('lat')}, {cached_data.get('lng')}")
                else:
                    print(f"  [Cached failed lookup]")

            if cached_data.get('lat') is not None and cached_data.get('lng') is not None:
                return {
                    'latitude': cached_data['lat'],
                    'longitude': cached_data['lng'],
                    'source': 'cache'
                }
            else:
                return None
        
        # Determine if this looks like a UK address (to guide preference logic)
        uk_address_indicators = ['uk', 'england', 'wales', 'scotland', 'northern ireland', 'great britain', 'britain']
        looks_like_uk_address = any(indicator in place_name.lower() for indicator in uk_address_indicators)
        
        # Try geocoding with enhanced algorithm
        try:
            from geopy.geocoders import Nominatim
            import time
            
            geolocator = Nominatim(user_agent="family_tree_mapper_v1.0")
            uk_result_indicators = ['united kingdom', 'uk', 'great britain', 'gb', 'england', 'wales', 'scotland', 'northern ireland']
            
            if debug:
                print(f"\nChecking if address looks like UK: {looks_like_uk_address}")
                print(f"Checking for UK enhancement via places_config...")

            # Check places_config for UK enhancement
            enhanced_address = self._check_places_config_for_uk_enhancement(place_name, debug=True)
            if enhanced_address and enhanced_address != place_name:
                if person_info and debug:
                    print(f"Trying UK-enhanced address: {enhanced_address}")
                # Try geocoding with enhanced address (adds UK context)
                enhanced_location = geolocator.geocode(enhanced_address, timeout=15)
                if enhanced_location:
                    # Check if it's a UK result
                    enhanced_address_lower = enhanced_location.address.lower()
                    is_uk_result = any(indicator in enhanced_address_lower for indicator in uk_result_indicators)
                    if is_uk_result:
                        # Use the enhanced UK result
                        chosen_location = enhanced_location
                        cache_entry = {
                            'lat': chosen_location.latitude,
                            'lng': chosen_location.longitude,
                            'cached_date': datetime.now().isoformat(),
                            'source': 'nominatim_places_config_enhanced',
                            'geocoded_address': chosen_location.address
                        }
                        self._geocoding_cache[place_key] = cache_entry
                        
                        time.sleep(1)  # Rate limiting
                        
                        return {
                            'latitude': chosen_location.latitude,
                            'longitude': chosen_location.longitude,
                            'source': 'geocoded_uk_enhanced'
                        }
            
            chosen_location = None
            
            # If it's not a comma-separated address, just try it once
            if ',' not in place_name:
                location = geolocator.geocode(place_name, timeout=15)
                if location:
                    chosen_location = location
            else:
                # Progressive left-trimming for comma-separated addresses
                place_parts = [p.strip() for p in place_name.split(',') if p.strip()]
                
                for attempt in range(len(place_parts)):
                    # Create query by joining remaining parts (from attempt index onwards)
                    remaining_parts = place_parts[attempt:]
                    query = ', '.join(remaining_parts)
                    
                    try:
                        # Try single result first
                        location = geolocator.geocode(query, timeout=15)
                        
                        if location:
                            # Check if single result is UK
                            address_lower = location.address.lower()
                            is_uk_result = any(indicator in address_lower for indicator in uk_result_indicators)
                            
                            # Accept single result if:
                            # 1. It's UK and we expect UK, OR
                            # 2. We don't expect UK (so any result is fine)
                            if (is_uk_result and looks_like_uk_address) or not looks_like_uk_address:
                                chosen_location = location
                                break
                            else:
                                # Single result is not UK but we expect UK, check multiple results
                                pass
                        
                        # Try multiple results if single wasn't suitable or didn't exist
                        if not chosen_location:
                            locations = geolocator.geocode(query, exactly_one=False, timeout=15)
                            
                            if locations:
                                uk_locations = []
                                non_uk_locations = []
                                
                                for loc in locations:
                                    # Check if this looks like UK
                                    address_lower = loc.address.lower()
                                    is_uk_result = any(indicator in address_lower for indicator in uk_result_indicators)
                                    
                                    if is_uk_result:
                                        uk_locations.append(loc)
                                    else:
                                        non_uk_locations.append(loc)
                                
                                # Choose based on whether we expect a UK address
                                if looks_like_uk_address:
                                    # We expect UK - prefer UK results if available
                                    if uk_locations:
                                        chosen_location = uk_locations[0]
                                        break
                                    elif non_uk_locations:
                                        # No UK results but we have others - continue trying shorter address parts
                                        continue
                                    else:
                                        # No results at all - continue
                                        continue
                                else:
                                    # We don't expect UK - any result is fine, prefer first available
                                    if locations:
                                        chosen_location = locations[0]
                                        break
                            else:
                                # No multiple results either - continue to next attempt
                                continue
                        
                        time.sleep(1)  # Rate limiting between attempts
                        
                    except Exception as e:
                        print(f"Error geocoding '{query}': {e}")
                        continue
            
            # Cache and return the chosen location
            if chosen_location:
                cache_entry = {
                    'lat': chosen_location.latitude,
                    'lng': chosen_location.longitude,
                    'cached_date': datetime.now().isoformat(),
                    'source': 'nominatim_enhanced_progressive',
                    'geocoded_address': chosen_location.address
                }
                self._geocoding_cache[place_key] = cache_entry
                
                time.sleep(1)  # Rate limiting
                
                return {
                    'latitude': chosen_location.latitude,
                    'longitude': chosen_location.longitude,
                    'source': 'geocoded'
                }
            
            # If everything failed, cache the failure
            self._geocoding_cache[place_key] = {
                'lat': None,
                'lng': None,
                'cached_date': datetime.now().isoformat(),
                'source': 'failed_enhanced_progressive'
            }
            
            if person_info:
                print(f"  ✗ Could not geocode '{place_name}' for {person_info.get('name', 'Unknown')} (born {person_info.get('birth_year', 'Unknown')})")
            
            return None
            
        except Exception as e:
            print(f"Error in enhanced geocoding for '{place_name}': {e}")
            if person_info:
                print(f"   → Person: {person_info.get('name', 'Unknown')} (born {person_info.get('birth_year', 'Unknown')})")
            return None




    def _check_places_config_for_uk_enhancement(self, address: str, debug=False) -> str:
        """Check if the last part of an address is a UK place in places_config and enhance it."""
        if debug:
            print(f"Checking places_config for UK enhancement of address: '{address}'")
            
        if not self._places_config:
            if debug:
                print(f"No places_config available for enhancement. Returning original address.")
            return address
        
        # Extract parts from comma-separated address
        parts = [p.strip() for p in address.split(',') if p.strip()]
        if debug:
            print(f"Address parts: {parts}")
        
        if len(parts) < 2:
            return address
        
        # Check for historical county mapping
        place = parts[0]  # e.g. "Bangor"
        county = parts[1]  # e.g. "Caernarvonshire"
        
        # Check if this is a historical county reference
        county_places = self._places_config.get('county_places', {})
        for current_county, places in county_places.items():
            # Check if place exists in this county
            if place.lower() in map(str.lower, places.keys()):
                # Find the actual case-sensitive place key
                for place_key in places.keys():
                    if place.lower() == place_key.lower():
                        place_data = places[place_key]
                        
                        # First check array-based historical_counties (new format)
                        if "historical_counties" in place_data:
                            for hist_county in place_data["historical_counties"]:
                                # Handle comma-separated variants within each array entry
                                variants = [v.strip() for v in hist_county.split(',')]
                                for variant in variants:
                                    if county.lower() == variant.lower():
                                        if debug:
                                            print(f"✓ Historical county match: '{county}' → '{current_county}'")
                                        
                                        # Replace county with current county
                                        updated_parts = parts.copy()
                                        updated_parts[1] = current_county
                                        return ', '.join(updated_parts)
                        
                        # Fall back to legacy single historical_county format
                        elif "historical_county" in place_data and county.lower() == place_data["historical_county"].lower():
                            if debug:
                                print(f"✓ Historical county match (legacy): '{county}' → '{current_county}'")
                            
                            # Replace county with current county
                            updated_parts = parts.copy()
                            updated_parts[1] = current_county
                            return ', '.join(updated_parts)
        
        # Special case for places like "Chester, Cheshire"
        # Check if the last part is directly a UK county in our config
        last_part = parts[-1].lower()
        nation_counties = self._places_config.get('nation_counties', {})
        for nation, counties in nation_counties.items():
            if isinstance(counties, list):
                for county in counties:
                    county_lower = county.lower()
                    if '/' in county_lower:  # Handle variants like "Shropshire/Salop"
                        county_variants = [c.strip() for c in county_lower.split('/')]
                        if last_part in county_variants:
                            return f"{address}, {nation}"
                    elif county_lower == last_part:
                        return f"{address}, {nation}"

        # Check if last part is a country first
        nation_places = self._places_config.get('nation_places', {})
        for country, places in nation_places.items():
            if country.lower() == last_part:
                # It's already a country, don't enhance
                if debug:
                    print(f"Address '{address}' is already a country: {country}")
                return address
        
        # Check if last part is a UK county/place and find which nation it belongs to
        nation_counties = self._places_config.get('nation_counties', {})
        
        # Check if it's a county in England/Wales/Scotland
        for nation, counties in nation_counties.items():
            if isinstance(counties, list):
                for county in counties:
                    # Handle slash-separated counties
                    if '/' in county:
                        county_variants = [c.strip().lower() for c in county.split('/')]
                        if last_part in county_variants:
                            # Found it! Enhance with the correct nation
                            enhanced_address = f"{address}, {nation}"
                            return enhanced_address
                    else:
                        if county.lower() == last_part:
                            # Found it! Enhance with the correct nation
                            if debug:
                                print(f"Found county match (enhancing with its nation): {county} in {nation}")
                            enhanced_address = f"{address}, {nation}"
                            return enhanced_address
        
        # Check county_places for sub-locations
        county_places = self._places_config.get('county_places', {})
        for county, places in county_places.items():
            if isinstance(places, dict):  # This is the correct structure
                for place in places.keys():
                    # Handle slash-separated places
                    if '/' in place:
                        place_variants = [p.strip().lower() for p in place.split('/')]
                        if last_part in place_variants:
                            # Found in a county - need to find which nation this county is in
                            county_lower = county.lower()
                            for nation, counties in nation_counties.items():
                                if isinstance(counties, list):
                                    for nation_county in counties:
                                        if '/' in nation_county:
                                            nation_county_variants = [c.strip().lower() for c in nation_county.split('/')]
                                            if county_lower in nation_county_variants:
                                                enhanced_address = f"{address}, {county}, {nation}"
                                                return enhanced_address
                                        else:
                                            if nation_county.lower() == county_lower:
                                                enhanced_address = f"{address}, {county}, {nation}"
                                                return enhanced_address
                    else:
                        if place.lower() == last_part:
                            # Found in a county - need to find which nation this county is in
                            county_lower = county.lower()
                            for nation, counties in nation_counties.items():
                                if isinstance(counties, list):
                                    for nation_county in counties:
                                        if '/' in nation_county:
                                            nation_county_variants = [c.strip().lower() for c in nation_county.split('/')]
                                            if county_lower in nation_county_variants:
                                                enhanced_address = f"{address}, {county}, {nation}"
                                                return enhanced_address
                                        else:
                                            if nation_county.lower() == county_lower:
                                                enhanced_address = f"{address}, {county}, {nation}"
                                                return enhanced_address
        
        # If we get here, the last part wasn't found in UK places config
        return address




    def _fallback_smart_part_matching(self, place_name: str, person_info: dict, geolocator, uk_indicators):
        """Fallback to smart part matching when full address methods fail."""
        if ',' not in place_name:
            # Single place name - cache failure and exit
            self._geocoding_cache[place_name] = {
                'lat': None,
                'lng': None,
                'cached_date': datetime.now().isoformat(),
                'source': 'failed_single_name_enhanced'
            }
            
            print(f"  ✗ Single place name '{place_name}' not found")
            if person_info:
                print(f"      → FULL ADDRESS: '{place_name}'")
                print(f"      → Person: {person_info.get('name', 'Unknown')} (born {person_info.get('birth_year', 'Unknown')})")
                print(f"      → You may want to check/modify this address in the source data")
            
            return None
        
        print(f"  → FULL ADDRESS: '{place_name}' - Enhanced methods failed, trying smart part matching...")
        
        # Split into parts and try each
        place_parts = [p.strip() for p in place_name.split(',') if p.strip()]
        
        for i, part in enumerate(place_parts):
            if len(part) <= 3:  # Skip very short parts
                continue
            
            try:
                print(f"  → Geocoding part '{part}'...")
                locations = geolocator.geocode(part, exactly_one=False, timeout=10)
                
                if not locations:
                    print(f"    ✗ No results for '{part}'")
                    continue
                
                if len(locations) == 1:
                    # Only one result - use it
                    location = locations[0]
                    
                    cache_entry = {
                        'lat': location.latitude,
                        'lng': location.longitude,
                        'cached_date': datetime.now().isoformat(),
                        'source': 'nominatim_fallback_single_part',
                        'geocoded_address': location.address,
                        'derived_from': part
                    }
                    self._geocoding_cache[place_name] = cache_entry
                    
                    time.sleep(1)
                    return {
                        'latitude': location.latitude,
                        'longitude': location.longitude,
                        'source': 'geocoded'
                    }
                
                else:
                    # Multiple results - favor UK locations
                    print(f"    ⚠️  Multiple results for '{part}' ({len(locations)} found)")
                    if person_info:
                        print(f"        → FULL ADDRESS: '{place_name}'")
                        print(f"        → Person: {person_info.get('name', 'Unknown')} (born {person_info.get('birth_year', 'Unknown')})")
                    
                    # Look for UK locations
                    uk_location = None
                    for location in locations:
                        address_lower = location.address.lower()
                        if any(indicator in address_lower for indicator in uk_indicators):
                            uk_location = location
                            break
                    
                    if uk_location:
                        print(f"    ✓ Found UK location in results: {uk_location.address}")
                        
                        cache_entry = {
                            'lat': uk_location.latitude,
                            'lng': uk_location.longitude,
                            'cached_date': datetime.now().isoformat(),
                            'source': 'nominatim_fallback_uk_preferred',
                            'geocoded_address': uk_location.address,
                            'derived_from': part,
                            'total_alternatives': len(locations)
                        }
                        self._geocoding_cache[place_name] = cache_entry
                        
                        time.sleep(1)
                        return {
                            'latitude': uk_location.latitude,
                            'longitude': uk_location.longitude,
                            'source': 'geocoded'
                        }
                    
                    # No UK location - try combining with next part
                    if i + 1 < len(place_parts):
                        combined_query = f"{place_parts[i]}, {place_parts[i+1]}"
                        print(f"    → Trying combined query: '{combined_query}'")
                        
                        combined_location = geolocator.geocode(combined_query, timeout=10)
                        
                        if combined_location:
                            # Check if this combined result matches one of the multiple results
                            for multi_loc in locations:
                                lat_diff = abs(combined_location.latitude - multi_loc.latitude)
                                lng_diff = abs(combined_location.longitude - multi_loc.longitude)
                                
                                if lat_diff < 0.01 and lng_diff < 0.01:  # ~1km tolerance
                                    cache_entry = {
                                        'lat': combined_location.latitude,
                                        'lng': combined_location.longitude,
                                        'cached_date': datetime.now().isoformat(),
                                        'source': 'nominatim_fallback_combined_parts',
                                        'geocoded_address': combined_location.address,
                                        'derived_from': combined_query
                                    }
                                    self._geocoding_cache[place_name] = cache_entry
                                    
                                    time.sleep(1)
                                    return {
                                        'latitude': combined_location.latitude,
                                        'longitude': combined_location.longitude,
                                        'source': 'geocoded'
                                    }
                            
                            print(f"    ✗ Combined query result doesn't match any of the multiple results")
                        else:
                            print(f"    ✗ Combined query '{combined_query}' failed")
                    
                    print(f"    ✗ Cannot resolve ambiguous location '{part}' (no UK match found)")
                    continue
                    
            except Exception as e:
                print(f"    ✗ Error geocoding part '{part}': {e}")
                continue
        
        # All methods failed - cache the failure
        self._geocoding_cache[place_name] = {
            'lat': None,
            'lng': None,
            'cached_date': datetime.now().isoformat(),
            'source': 'failed_all_enhanced_methods'
        }
        
        print(f"  ✗ GEOCODING FAILED: Could not geocode any part of: {place_name}")
        
        if person_info:
            print(f"      → FULL ADDRESS: '{place_name}'")
            print(f"      → Person: {person_info.get('name', 'Unknown')} (born {person_info.get('birth_year', 'Unknown')})")
            print(f"      → You may want to check/modify this address in the source data")
        
        return None

    def _find_uk_location_in_results(self, locations) -> object:
        """Find UK location among multiple geocoding results."""
        uk_indicators = [
            'united kingdom', 'uk', 'great britain', 'gb',
            'england', 'wales', 'scotland', 'northern ireland',
            'royaume-uni',  # French name sometimes appears
        ]
        
        for location in locations:
            address_lower = location.address.lower()
            if any(indicator in address_lower for indicator in uk_indicators):
                return location
        
        return None

    def _ensure_places_config_geocoded(self):
        print("Ensuring all places from places_config.json are geocoded...")
        """Ensure all places from places_config.json are in the geocoding cache."""
        if not self._places_config:
            if not hasattr(self, '_places_config_file') or not self._places_config_file.exists():
                print("No places_config.json file found.")
                return
            
            # Load places_config if not already loaded
            self._load_places_config()
        
        # Count places in config before geocoding
        place_count = 0
        
        def count_places_recursive(data):
            nonlocal place_count
            if isinstance(data, dict):
                for key, value in data.items():
                    if key not in {'_comment', 'nation_counties', 'county_places', 'nation_places', 
                                'local2_places', 'known_streets'}:
                        place_count += 1
                    count_places_recursive(value)
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, str):
                        place_count += 1
                    else:
                        count_places_recursive(item)
        
        count_places_recursive(self._places_config)
        print(f"Found {place_count} places in places_config.json.")
        # Only show message if there are places to potentially geocode
        if place_count > 0:
            cache_count = len(self._geocoding_cache)
            print(f"Checking {place_count} places from places_config.json against {cache_count} cached locations...")
            
            # Geocode any missing places from the config
            self._geocode_places_config()

    def clear_geocoding_cache(self):
        """Clear the geocoding cache (for debugging or cache corruption)."""
        self._geocoding_cache = {}
        if self._geocoding_cache_file.exists():
            self._geocoding_cache_file.unlink()
        print("Geocoding cache cleared.")
        
        # Ask if user wants to repopulate with places_config
        repopulate = input("\nDo you want to repopulate the cache with places from places_config.json? (Y/n): ").strip().lower()
        if repopulate != 'n':  # Default is yes
            print("\nRepopulating cache with places_config.json entries...")
            self._ensure_places_config_geocoded()
            print("\nCache repopulated with places_config.json entries.")
        else:
            print("\nCache left empty.")
        
        input("\nPress Enter to continue...")

    def clear_cache(self):
        """Manually clear the relationship index cache."""
        try:
            import shutil
            if self._cache_dir.exists():
                shutil.rmtree(self._cache_dir)
                print("All caches cleared successfully (indexes and geocoding).")
            else:
                print("No cache to clear.")
        except Exception as e:
            print(f"Error clearing cache: {e}")

    def analyse_years_lived(self):
        """
        Analyze ages at death for men and women.
        Prints overall, decade, and century stats with average/max for male and female.
        Excludes ages >= 100, negative ages, and those with no death recorded.
        Optionally excludes deaths under age 5.
        """
        print("\n=== Death Age Analysis ===\n")
        
        # Ask about excluding deaths under age 5
        exclude_under_5 = input("Exclude people who died under age 5? (Y/n): ").strip().lower()
        exclude_under_5 = exclude_under_5 != 'n'  # Default is yes
        
        # Use ancestor filter if present
        if hasattr(self, "ancestor_filter_ids") and self.ancestor_filter_ids:
            individuals = [self._individual_index[xref_id] for xref_id in self.ancestor_filter_ids if xref_id in self._individual_index]
            tree_context = f"current ancestry tree ({len(self.ancestor_filter_ids)} individuals)"
        else:
            individuals = list(self._individual_index.values())
            tree_context = f"entire database ({len(individuals)} individuals)"

        # Build lookup for birth years, death years, and names
        birth_years = {ind.xref_id: ind.birth_year for ind in individuals if ind.birth_year}
        death_years = {ind.xref_id: ind.death_year for ind in individuals if ind.death_year}
        names = {ind.xref_id: ind.name for ind in individuals}

        # Collect ages by decade and century
        decade_data = {}
        century_data = {}
        male_ages = []
        female_ages = []

        print(f"Analyzing {tree_context}...")

        for ind in individuals:
            # Skip if no birth or death year
            birth_year = birth_years.get(ind.xref_id)
            death_year = death_years.get(ind.xref_id)
            
            if not birth_year or not ind.is_deceased() or not death_year:
                continue
                
            # Calculate age at death
            age = death_year - birth_year
            
            # Skip negative ages
            if age < 0:
                continue
                
            # Skip ages over 100
            if age >= 100:
                continue
                
            # Skip deaths under age 5 if requested
            if exclude_under_5 and age < 5:
                continue

            # Get gender from raw record
            gender = None
            if hasattr(ind, 'raw_record') and ind.raw_record and hasattr(ind.raw_record, 'sub_records'):
                for sub in ind.raw_record.sub_records:
                    if getattr(sub, 'tag', None) == 'SEX':
                        gender = (sub.value or '').strip().upper()
                        break

            # Skip if no gender specified
            if not gender or gender not in ['M', 'F']:
                continue

            decade = (death_year // 10) * 10
            century = (death_year // 100) * 100

            # Add to appropriate gender list
            if gender == 'M':
                male_ages.append(age)
                decade_data.setdefault(decade, {"male": [], "female": []})["male"].append(age)
                century_data.setdefault(century, {"male": [], "female": []})["male"].append(age)
            else:  # gender == 'F'
                female_ages.append(age)
                decade_data.setdefault(decade, {"male": [], "female": []})["female"].append(age)
                century_data.setdefault(century, {"male": [], "female": []})["female"].append(age)

        def avg(lst):
            return round(sum(lst) / len(lst), 2) if lst else None
        def maximum(lst):
            return max(lst) if lst else None

        # Overall stats
        print(f"Overall average male age at death: {avg(male_ages)} ({len(male_ages)} records)")
        print(f"Overall average female age at death: {avg(female_ages)} ({len(female_ages)} records)")
        print(f"Overall max male age at death: {maximum(male_ages)}")
        print(f"Overall max female age at death: {maximum(female_ages)}")
        
        exclusions = []
        if exclude_under_5:
            exclusions.append("deaths under age 5")
        exclusions.append("ages >= 115")
        exclusions.append("negative ages")
        exclusions.append("missing birth/death years")
        exclusions.append("missing gender")
        
        print(f"(Excluding: {', '.join(exclusions)})\n")

        # Grand total stats across all data
        male_max = maximum(male_ages)
        female_max = maximum(female_ages)
        print("=== Grand Total Death Age Stats ===")
        print(f"  Male Avg: {avg(male_ages)} (max: {male_max})")
        print(f"  Female Avg: {avg(female_ages)} (max: {female_max})\n")

        # Per-decade
        print("=== Per-Decade Death Age Stats ===")
        grand_total = 0
        for decade in sorted(decade_data):
            male_list = decade_data[decade]["male"]
            female_list = decade_data[decade]["female"]
            all_ages = male_list + female_list
            n_records = len(all_ages)
            grand_total += n_records
            
            male_avg = avg(male_list)
            female_avg = avg(female_list)
            male_max = maximum(male_list)
            female_max = maximum(female_list)
            overall_avg = avg(all_ages)
            
            print(f"{decade}s: {overall_avg} avg ({n_records} records)")
            print(f"    Male Avg: {male_avg} (max: {male_max}) [{len(male_list)} records]")
            print(f"    Female Avg: {female_avg} (max: {female_max}) [{len(female_list)} records]")
        print(f"\nGrand total deaths: {grand_total}")

        # Per-century
        print("\n=== Per-Century Death Age Stats ===")
        for century in sorted(century_data):
            male_list = century_data[century]["male"]
            female_list = century_data[century]["female"]
            all_ages = male_list + female_list
            n_records = len(all_ages)
            
            male_avg = avg(male_list)
            female_avg = avg(female_list)
            male_max = maximum(male_list)
            female_max = maximum(female_list)
            overall_avg = avg(all_ages)
            
            century_label = f"{century//100+1}th century" if century >= 1000 else f"{century}s"
            print(f"{century_label}: {overall_avg} avg ({n_records} records)")
            print(f"    Male Avg: {male_avg} (max: {male_max}) [{len(male_list)} records]")
            print(f"    Female Avg: {female_avg} (max: {female_max}) [{len(female_list)} records]")

    def get_birth_places_data(self) -> dict:
        """Get birth places data that can be used for mapping or other purposes."""
        if hasattr(self, "ancestor_filter_ids") and self.ancestor_filter_ids:
            individuals = [self._individual_index[xref_id] for xref_id in self.ancestor_filter_ids if xref_id in self._individual_index]
        else:
            individuals = list(self._individual_index.values())
        
        places_data = {}
        
        for ind in individuals:
            if ind.birth_place:
                place = ind.birth_place.strip()
                if place not in places_data:
                    places_data[place] = {
                        'people': [],
                        'count': 0,
                        'birth_years': []
                    }
                
                places_data[place]['people'].append({
                    'name': ind.name,
                    'xref_id': ind.xref_id,
                    'birth_year': ind.birth_year
                })
                places_data[place]['count'] += 1
                
                if ind.birth_year:
                    places_data[place]['birth_years'].append(ind.birth_year)
        
        return places_data

    def export_places_to_kml(self, places_data: dict):
        """KML export not implemented."""
        print("KML export functionality not implemented.")
        print("Use option 1 (Google Maps URL) instead.")
        input("\nPress Enter to continue...")

    def create_interactive_map(self, places_data: dict):
        """Interactive mapping not implemented."""
        print("Interactive HTML mapping requires additional packages and setup.")
        print("Use option 1 (Google Maps URL) instead.")
        input("\nPress Enter to continue...")

    def create_google_maps_url(self, places_data: dict):
        """Generate a Google Maps URL with birth place markers."""
        if not places_data:
            print("No birth places found.")
            return
        
        # For individual pins, we can either:
        # 1. Open the first location and let user search for others
        # 2. Create a My Maps URL (requires manual import)
        
        places_list = list(places_data.keys())
        
        if len(places_list) == 1:
            # Single location - direct map link
            place = places_list[0]
            clean_place = place.replace(' ', '+').replace(',', '%2C')
            maps_url = f"https://www.google.com/maps/search/{clean_place}"
        else:
            # Multiple locations - show first one and print instructions
            first_place = places_list[0]
            clean_place = first_place.replace(' ', '+').replace(',', '%2C')
            maps_url = f"https://www.google.com/maps/search/{clean_place}"
            
            print(f"Found {len(places_data)} unique birth places:")
            print(f"Opening map for: {first_place}")
            print(f"\nTo see all locations as pins, search for these in Google Maps:")
            
            for i, place in enumerate(places_list, 1):
                data = places_data[place]
                year_range = ""
                if data['birth_years']:
                    min_year = min(data['birth_years'])
                    max_year = max(data['birth_years'])
                    year_range = f" ({min_year}-{max_year})" if min_year != max_year else f" ({min_year})"
                
                print(f"  {i}. {place}: {data['count']} people{year_range}")
        
        print(f"\nOpening Google Maps...")
        
        # Open in default browser
        webbrowser.open(maps_url)
        
        return maps_url

    def _cluster_places_by_coordinates(self, places_data: dict) -> dict:
        """Group places by their coordinates to avoid duplicate pins."""
        coordinate_clusters = {}
        
        for place, data in places_data.items():
            # Create person info for the first person at this location (for error reporting)
            person_info = None
            if data.get('people') and len(data['people']) > 0:
                first_person = data['people'][0]
                person_info = {
                    'name': first_person.get('name', 'Unknown'),
                    'birth_year': first_person.get('birth_year', 'Unknown')
                }
            
            location_data = self._get_geocoded_location(place, person_info)
            
            if location_data:
                # Round coordinates to avoid tiny differences
                lat = round(location_data['latitude'], 4)  # ~11m precision
                lng = round(location_data['longitude'], 4)
                coord_key = f"{lat},{lng}"
                
                if coord_key not in coordinate_clusters:
                    coordinate_clusters[coord_key] = {
                        'latitude': location_data['latitude'],
                        'longitude': location_data['longitude'],
                        'places': [],
                        'total_people': 0,
                        'all_people': [],
                        'all_birth_years': []
                    }
                
                # Add this place's data to the cluster
                coordinate_clusters[coord_key]['places'].append({
                    'name': place,
                    'count': data['count'],
                    'people': data['people']
                })
                coordinate_clusters[coord_key]['total_people'] += data['count']
                coordinate_clusters[coord_key]['all_people'].extend(data['people'])
                coordinate_clusters[coord_key]['all_birth_years'].extend(data.get('birth_years', []))
        
        return coordinate_clusters

    def create_folium_map(self, places_data: dict):
        """Create interactive map using Folium with coordinate-based clustering to avoid duplicate pins."""
        try:
            import folium
            from folium import DivIcon
        except ImportError:
            print("This option requires additional packages:")
            print("pip install folium geopy")
            return
        
        if not places_data:
            print("No birth places found.")
            return
        
        # Create map centered on UK
        m = folium.Map(location=[54.5, -2.0], zoom_start=6)
        
        geocoded_count = 0
        cached_count = 0
        failed_count = 0
        
        # Cluster places by coordinates first
        coordinate_clusters = self._cluster_places_by_coordinates(places_data)
        
        print(f"Processing {len(places_data)} places into {len(coordinate_clusters)} map locations...")
        
        for coord_key, cluster in coordinate_clusters.items():
            if cluster['total_people'] == 0:
                continue
                
            # Track geocoding stats
            # (Note: geocoding already happened in _cluster_places_by_coordinates)
            cached_count += 1  # All are from cache now since clustering already geocoded them
            
            # Create popup showing all places at this location
            place_summaries = []
            for place_info in cluster['places']:
                place_summaries.append(f"• {place_info['name']}: {place_info['count']} people")
            
            year_range = ""
            if cluster['all_birth_years']:
                min_year = min(cluster['all_birth_years'])
                max_year = max(cluster['all_birth_years'])
                year_range = f" ({min_year}-{max_year})" if min_year != max_year else f" ({min_year})"
            
            # Determine the primary place name for the tooltip
            primary_place = cluster['places'][0]['name']
            if len(cluster['places']) > 1:
                tooltip_text = f"{primary_place} + {len(cluster['places'])-1} more locations ({cluster['total_people']} people)"
            else:
                tooltip_text = f"{primary_place} ({cluster['total_people']} people)"
            
            popup_html = f"""
            <b>Location Cluster</b>{year_range}<br/>
            <i>{cluster['total_people']} people born here:</i><br/>
            {"<br/>".join(place_summaries)}<br/>
            <br/><b>People:</b><br/>
            {', '.join([p['name'] for p in cluster['all_people'][:15]])}
            {"<br/>...and more" if len(cluster['all_people']) > 15 else ""}
            """
            
            count = cluster['total_people']
            
            # Choose marker style based on count
            if count == 1:
                # Single person - use standard marker
                folium.Marker(
                    [cluster['latitude'], cluster['longitude']],
                    popup=folium.Popup(popup_html, max_width=300),
                    tooltip=tooltip_text,
                    icon=folium.Icon(color='blue', icon='user', prefix='fa')
                ).add_to(m)
            else:
                # Multiple people - use numbered marker
                # Choose color based on count
                if count <= 5:
                    color = '#4285f4'  # Blue
                    text_color = 'white'
                elif count <= 10:
                    color = '#ea4335'  # Red
                    text_color = 'white'
                elif count <= 20:
                    color = '#fbbc05'  # Yellow
                    text_color = 'black'
                else:
                    color = '#34a853'  # Green
                    text_color = 'white'
                
                # Create custom numbered marker
                html = f"""
                <div style="
                    background-color: {color};
                    border: 2px solid white;
                    border-radius: 50%;
                    width: 30px;
                    height: 30px;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    font-weight: bold;
                    font-size: 14px;
                    color: {text_color};
                    box-shadow: 0 2px 4px rgba(0,0,0,0.3);
                ">{count}</div>
                """
                
                folium.Marker(
                    [cluster['latitude'], cluster['longitude']],
                    popup=folium.Popup(popup_html, max_width=300),
                    tooltip=tooltip_text,
                    icon=DivIcon(
                        html=html,
                        icon_size=(30, 30),
                        icon_anchor=(15, 15)
                    )
                ).add_to(m)
        
        # Calculate failed count
        failed_count = len(places_data) - sum(len(cluster['places']) for cluster in coordinate_clusters.values())
        
        # Add a legend
        legend_html = """
        <div style="position: fixed; 
                    bottom: 50px; left: 50px; width: 220px; height: 140px; 
                    background-color: white; border:2px solid grey; z-index:9999; 
                    font-size:14px; padding: 10px; border-radius: 5px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.3);
                    ">
        <h4>Birth Places Legend</h4>
        <p><i class="fa fa-user" style="color:blue"></i> 1 person</p>
        <p><span style="color:#4285f4">●</span> 2-5 people</p>
        <p><span style="color:#ea4335">●</span> 6-10 people</p>
        <p><span style="color:#fbbc05">●</span> 11-20 people</p>
        <p><span style="color:#34a853">●</span> 20+ people</p>
        <p><small>Clustered by coordinates</small></p>
        </div>
        """
        m.get_root().html.add_child(folium.Element(legend_html))
        
        # Save updated cache
        self._save_geocoding_cache()
        
        filename = "birth_places_folium.html"
        m.save(filename)
        
        print(f"Results: {len(coordinate_clusters)} pin locations, {failed_count} places failed geocoding")
        print(f"Interactive map saved: {filename}")
        
        webbrowser.open('file://' + os.path.abspath(filename))
        return filename

    def create_openstreetmap_interactive(self, places_data: dict):
        """Create interactive OpenStreetMap with markers using Leaflet."""
        if not places_data:
            print("No birth places found.")
            return
        
        # Create HTML with Leaflet.js
        html_content = '''<!DOCTYPE html>
    <html>
    <head>
        <title>Family Tree Birth Places</title>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <style>
            #map { height: 600px; width: 100%; }
            body { margin: 0; font-family: Arial, sans-serif; }
            .info { padding: 10px; background: #f8f9fa; margin: 10px; border-radius: 5px; }
        </style>
    </head>
    <body>
        <div class="info">
            <h2>Family Tree Birth Places</h2>
            <p>Click on markers to see details. Places listed below need manual geocoding.</p>
        </div>
        <div id="map"></div>
        
        <script>
            // Initialize map centered on UK
            var map = L.map('map').setView([54.5, -2.0], 6);
            
            // Add OpenStreetMap tiles
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap contributors'
            }).addTo(map);
            
            // Add markers (you'll need to manually add coordinates)
            var places = ['''

        # Add place data (Note: you'd need geocoding for coordinates)
        places_js = []
        for place, data in places_data.items():
            people_names = [p['name'] for p in data['people'][:5]]
            more_text = f" and {data['count']-5} more" if data['count'] > 5 else ""
            
            year_range = ""
            if data['birth_years']:
                min_year = min(data['birth_years'])
                max_year = max(data['birth_years'])
                year_range = f" ({min_year}-{max_year})" if min_year != max_year else f" ({min_year})"
            
            # You'd need to geocode these - for now, just list them
            places_js.append(f'            // {place}: {data["count"]} people{year_range}')
            places_js.append(f'            // People: {", ".join(people_names)}{more_text}')
        
        html_content += '\n'.join(places_js)
        
        html_content += '''
            ];
            
            // Note: Coordinates needed for actual pins
            // For now, just center on UK and show place list below
        </script>
        
        <div class="info">
            <h3>Birth Places Found:</h3>
            <ul>'''
        
        for place, data in places_data.items():
            year_range = ""
            if data['birth_years']:
                min_year = min(data['birth_years'])
                max_year = max(data['birth_years'])
                year_range = f" ({min_year}-{max_year})" if min_year != max_year else f" ({min_year})"
            
            html_content += f'<li><strong>{place}</strong>: {data["count"]} people{year_range}</li>'
        
        html_content += '''
            </ul>
            <p><em>To add pins to the map, you would need to geocode these place names to coordinates.</em></p>
        </div>
    </body>
    </html>'''
        
        filename = "birth_places_openstreetmap.html"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"OpenStreetMap created: {filename}")
        webbrowser.open('file://' + os.path.abspath(filename))
        return filename

    def plot_birth_places_menu(self):
        """Menu for birth place mapping options."""
        print("\n=== Birth Place Mapping ===")
        print("1. Google Maps URL (limited to one location)")
        print("2. OpenStreetMap HTML (manual geocoding needed)")
        print("3. Interactive Folium map (auto-geocoding)")
        print("4. CSV export for manual mapping")
        
        choice = input("Choose option (1-4): ").strip()
        
        places_data = self.get_birth_places_data()
        
        if choice == '1':
            self.create_google_maps_url(places_data)
        elif choice == '2':
            self.create_openstreetmap_interactive(places_data)
        elif choice == '3':
            self.create_folium_map(places_data)
        elif choice == '4':
            self.export_places_csv(places_data)
        else:
            print("Invalid choice.")
        
        input("\nPress Enter to continue...")

        """Show geocoding cache statistics."""
        print(f"\nGeocoding Cache Statistics:")
        print(f"Cache file: {self._geocoding_cache_file}")
        print(f"Total entries: {len(self._geocoding_cache)}")
        
        if self._geocoding_cache:
            sources = {}
            for entry in self._geocoding_cache.values():
                source = entry.get('source', 'unknown')
                sources[source] = sources.get(source, 0) + 1
            
            print(f"Entries by source:")
            for source, count in sources.items():
                print(f"  {source}: {count}")
                
            # Count successful vs failed
            successful = sum(1 for entry in self._geocoding_cache.values() 
                           if entry.get('lat') is not None and entry.get('lng') is not None)
            failed = len(self._geocoding_cache) - successful
            print(f"Successful geocodes: {successful}")
            print(f"Failed geocodes: {failed}")
        
        input("\nPress Enter to continue...")

    def admin_menu(self):
        """Admin functions menu."""
        while True:
            print("\n" + "="*50)
            print("ADMIN MENU")
            print("="*50)
            print("1. Clear geocoding cache")
            print("2. Show cache statistics")
            print("0. Back to main menu")
            
            choice = input("\nEnter your choice: ").strip()
            
            if choice == '0':
                break
            elif choice == '1':
                confirm = input("Are you sure you want to clear the geocoding cache? This will require re-geocoding all places. (y/N): ").strip().lower()
                if confirm == 'y':
                    self.clear_geocoding_cache()
                else:
                    print("Cache clear cancelled.")
                    input("\nPress Enter to continue...")
            elif choice == '2':
                self.show_cache_stats()
            else:
                print("Invalid choice. Please try again.")
                input("\nPress Enter to continue...")

    def check_parents_died_before_children_born(self):
        """Check for parents who died before their children were born."""
        print("\n=== Parents Who Died Before Children Were Born ===\n")
        
        # Use ancestor filter if present
        if hasattr(self, "ancestor_filter_ids") and self.ancestor_filter_ids:
            individuals = [self._individual_index[xref_id] for xref_id in self.ancestor_filter_ids if xref_id in self._individual_index]
            tree_context = f"current ancestry tree ({len(self.ancestor_filter_ids)} individuals)"
        else:
            individuals = list(self._individual_index.values())
            tree_context = f"entire database ({len(individuals)} individuals)"
        
        print(f"Checking {tree_context}...")
        
        # Ask user what to check
        print("\nWhat would you like to check?")
        print("1. Mothers only")
        print("2. Fathers only")
        print("3. Both mothers and fathers")
        
        while True:
            choice = input("Enter choice (1-3): ").strip()
            if choice in ['1', '2', '3']:
                break
            print("Please enter 1, 2, or 3.")
        
        check_mothers = choice in ['1', '3']
        check_fathers = choice in ['2', '3']
        
        def format_date_precisely(individual):
            """Format date showing only what we actually know."""
            if individual.birth_date:
                # We have a full date - show it properly formatted
                return individual.birth_date.strftime('%d %b %Y')
            elif individual.birth_year:
                # Only have year
                return str(individual.birth_year)
            else:
                return "Unknown"
        
        # Build parent-child relationships with dates
        parent_issues = {'mothers': {}, 'fathers': {}}
        
        for individual in individuals:
            # Skip if no birth date
            if not individual.birth_date:
                continue
                
            # Get parents using fast lookup
            parents = self.get_parents_fast(individual.xref_id)
            
            for parent in parents:
                # Skip if parent has no death date
                if not parent.death_date:
                    continue
                
                # Determine parent gender
                parent_gender = None
                if hasattr(parent, 'raw_record') and parent.raw_record:
                    for sub in parent.raw_record.sub_records:
                        if getattr(sub, 'tag', None) == 'SEX':
                            parent_gender = (sub.value or '').strip().upper()
                            break
                
                # Skip if we can't determine gender or not checking this gender
                if parent_gender == 'F' and not check_mothers:
                    continue
                if parent_gender == 'M' and not check_fathers:
                    continue
                if parent_gender not in ['M', 'F']:
                    continue
                
                # Check timing based on gender
                is_problematic = False
                
                if parent_gender == 'F':
                    # For mothers: any death before birth is problematic
                    if parent.death_date < individual.birth_date:
                        is_problematic = True
                else:  # parent_gender == 'M'
                    # For fathers: death must be more than 9 months before birth
                    days_gap = (individual.birth_date - parent.death_date).days
                    if days_gap > 270:  # ~9 months
                        is_problematic = True
                
                if is_problematic:
                    # Calculate gap details
                    days_gap = (individual.birth_date - parent.death_date).days
                    years_gap = days_gap / 365.25
                    months_gap = days_gap / 30.44  # Average month length
                    
                    # Determine category
                    category = 'mothers' if parent_gender == 'F' else 'fathers'
                    
                    # Initialize parent entry if not exists
                    if parent.xref_id not in parent_issues[category]:
                        parent_issues[category][parent.xref_id] = {
                            'parent': parent,
                            'children_after_death': [],
                            'total_children': 0
                        }
                    
                    # Add this problematic child
                    parent_issues[category][parent.xref_id]['children_after_death'].append({
                        'child': individual,
                        'days_gap': days_gap,
                        'years_gap': years_gap,
                        'months_gap': months_gap
                    })
        
        # Count total children for each problematic parent
        for category in ['mothers', 'fathers']:
            for parent_id in parent_issues[category].keys():
                all_children = self.get_children_fast(parent_id)
                parent_issues[category][parent_id]['total_children'] = len(all_children)
        
        # Check if any issues found
        total_issues = len(parent_issues['mothers']) + len(parent_issues['fathers'])
        if total_issues == 0:
            print("✓ No problematic parent-child timing issues found.")
            input("\nPress Enter to continue...")
            return
        
        # Display results
        for category in ['mothers', 'fathers']:
            if not parent_issues[category] or (category == 'mothers' and not check_mothers) or (category == 'fathers' and not check_fathers):
                continue
            
            print(f"\n{'='*20} {category.upper()} {'='*20}")
            
            # Sort by number of problematic children (most issues first)
            sorted_parents = sorted(parent_issues[category].items(), 
                                key=lambda x: len(x[1]['children_after_death']), 
                                reverse=True)
            
            print(f"Found {len(sorted_parents)} {category} with children born after their death:\n")
            
            for parent_id, data in sorted_parents:
                parent = data['parent']
                problematic_children = data['children_after_death']
                total_children = data['total_children']
                
                # Format parent info with precise dates
                parent_birth = format_date_precisely(parent)
                parent_death = format_date_precisely(parent) if hasattr(parent, 'death_date') and parent.death_date else (str(parent.death_year) if hasattr(parent, 'death_year') and parent.death_year else "Unknown")
                
                # Fix: use death_date for parent_death formatting
                if parent.death_date:
                    parent_death = parent.death_date.strftime('%d %b %Y')
                elif hasattr(parent, 'death_year') and parent.death_year:
                    parent_death = str(parent.death_year)
                else:
                    parent_death = "Unknown"
                
                print(f"👤 {parent.name}")
                print(f"   Born: {parent_birth}")
                print(f"   Died: {parent_death}")
                print(f"   Problematic children: {len(problematic_children)} of {total_children} total children")
                
                # Sort children by birth date
                problematic_children.sort(key=lambda x: x['child'].birth_date)
                
                for i, child_data in enumerate(problematic_children, 1):
                    child = child_data['child']
                    days_gap = child_data['days_gap']
                    months_gap = child_data['months_gap']
                    years_gap = child_data['years_gap']
                    
                    child_birth = format_date_precisely(child)
                    
                    # Format gap description
                    if days_gap < 365:
                        gap_desc = f"{months_gap:.1f} months"
                    else:
                        gap_desc = f"{years_gap:.1f} years"
                    
                    print(f"   {i}. {child.name}")
                    print(f"      Born: {child_birth}")
                    print(f"      Gap: {gap_desc} after parent's death")
                
                print()  # Blank line between parents
        
        # Summary statistics
        total_mothers = len(parent_issues['mothers'])
        total_fathers = len(parent_issues['fathers'])
        total_problematic_children = sum(len(data['children_after_death']) 
                                    for category in parent_issues.values() 
                                    for data in category.values())
        
        print(f"\nSummary:")
        if check_mothers:
            print(f"  Problematic mothers: {total_mothers}")
        if check_fathers:
            print(f"  Problematic fathers: {total_fathers}")
        print(f"  Total problematic parent-child relationships: {total_problematic_children}")
        
        input("\nPress Enter to continue...")

    def test_single_address_mapping(self):
        """Test geocoding and mapping of a single address - temporary feature for debugging."""
        print("\n" + "="*50)
        print("SINGLE ADDRESS GEOCODING TEST")
        print("="*50)

        # Ensure places_config is loaded
        if not hasattr(self, '_places_config') or not self._places_config:
            print("Places config not loaded. Loading now...")
            self._load_places_config()

        # Get address from user
        address = input("Enter full address to test: ").strip()
        
        if not address:
            print("No address entered.")
            return
        
        # Ask if user wants detailed debugging
        debug_choice = input("Show detailed debugging output? (Y/n): ").strip().lower()
        show_debug = debug_choice != 'n'  # Default is yes
        
        print(f"\nTesting address: '{address}'")
        print("-" * 60)
        
        # Use the SAME enhanced geocoding function as the main system
        person_info = {
            'name': 'Test Person',
            'birth_year': 'Test'
        }
        
        if show_debug:
            print("Using main geocoding function with debug output enabled...")
        
        # Call the main geocoding function
        location_data = self._get_geocoded_location(address, person_info, debug=True)
        
        # Display result
        if location_data:
            print(f"\n" + "="*60)
            print("FINAL CHOSEN LOCATION:")
            print(f"Coordinates: {location_data['latitude']:.6f}, {location_data['longitude']:.6f}")
            print(f"Source: {location_data['source']}")
            print("="*60)
            
            # Create a simple map
            try:
                import folium
                
                # Create Folium map
                m = folium.Map(location=[location_data['latitude'], location_data['longitude']], zoom_start=12)
                
                # Add marker
                popup_html = f"""
                <b>Test Address</b><br/>
                <i>{address}</i><br/>
                <br/>Coordinates: {location_data['latitude']:.6f}, {location_data['longitude']:.6f}<br/>
                Source: {location_data['source']}
                """
                
                folium.Marker(
                    [location_data['latitude'], location_data['longitude']],
                    popup=folium.Popup(popup_html, max_width=300),
                    tooltip=f"Test: {address}",
                    icon=folium.Icon(color='green', icon='info-sign')
                ).add_to(m)
                
                # Save and open map
                filename = "test_single_address.html"
                m.save(filename)
                
                print(f"   ✅ Map created: {filename}")
                
                import webbrowser
                import os
                webbrowser.open('file://' + os.path.abspath(filename))
                
            except ImportError:
                print("   Folium not available for mapping")
        else:
            print(f"\n✗ FAILED: No location could be determined for '{address}'")
        
        input("\nPress Enter to continue...")

    def _find_places_config_match(self, original_address: str, uk_locations: list) -> object:
        """Check if any UK locations match places from our places config."""
        if not self._places_config:
            return None
        
        # Extract all place names from config
        config_places = set()
        
        def extract_places_recursive(data):
            if isinstance(data, dict):
                for key, value in data.items():
                    if key not in {'_comment', 'nation_counties', 'county_places', 'nation_places', 'local2_places', 'known_streets'}:
                        # Handle slash-separated places
                        if '/' in key:
                            config_places.update([p.strip().lower() for p in key.split('/') if p.strip()])
                        else:
                            config_places.add(key.lower())
                        extract_places_recursive(value)
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, str):
                        # Handle slash-separated places
                        if '/' in item:
                            config_places.update([p.strip().lower() for p in item.split('/') if p.strip()])
                        else:
                            config_places.add(item.lower())
                    else:
                        extract_places_recursive(item)
        
        extract_places_recursive(self._places_config)
        
        # Check original address parts against config
        original_parts = [p.strip().lower() for p in original_address.split(',') if p.strip()]
        config_matches_in_original = [part for part in original_parts if part in config_places]
        
        if not config_matches_in_original:
            print(f"   → No parts of '{original_address}' found in places config")
            return None
        
        print(f"   → Found config places in original address: {config_matches_in_original}")
        
        # Now check which UK locations contain these config places
        best_match = None
        best_match_count = 0
        
        for location in uk_locations:
            location_lower = location.address.lower()
            match_count = sum(1 for config_place in config_matches_in_original if config_place in location_lower)
            
            print(f"   → Checking: {location.address}")
            print(f"     Config matches: {match_count}")
            
            if match_count > best_match_count:
                best_match = location
                best_match_count = match_count
        
        if best_match and best_match_count > 0:
            print(f"   → Best config match ({best_match_count} matches): {best_match.address}")
            return best_match
        
        return None

    def export_places_csv(self, places_data: dict):
        """Export places as CSV for import into mapping tools."""
        if not places_data:
            print("No birth places found.")
            return
        
        csv_content = "Place,Count,People,Years\n"
        
        for place, data in places_data.items():
            people_names = '; '.join([p['name'] for p in data['people']])
            year_range = ""
            if data['birth_years']:
                min_year = min(data['birth_years'])
                max_year = max(data['birth_years'])
                year_range = f"{min_year}-{max_year}" if min_year != max_year else str(min_year)
            
            csv_content += f'"{place}",{data["count"]},"{people_names}","{year_range}"\n'
        
        filename = "birth_places.csv"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(csv_content)
        
        print(f"CSV exported: {filename}")
        print("You can import this into Google My Maps, QGIS, or other mapping tools.")
        return filename

    def find_potential_duplicates(self):
        """Find potential duplicate individuals based on name similarity and date proximity."""
        print("\n=== Potential Duplicate Detection ===\n")
        
        # Use ancestor filter if present
        if hasattr(self, "ancestor_filter_ids") and self.ancestor_filter_ids:
            individuals = [self._individual_index[xref_id] for xref_id in self.ancestor_filter_ids if xref_id in self._individual_index]
            tree_context = f"current ancestry tree ({len(self.ancestor_filter_ids)} individuals)"
        else:
            individuals = list(self._individual_index.values())
            tree_context = f"entire database ({len(individuals)} individuals)"
        
        print(f"Analyzing {tree_context} for potential duplicates...")
        
        # Configuration options (removed loose)
        print("\nDuplicate detection settings:")
        print("1. Strict matching (very similar names, close dates)")
        print("2. Standard matching (similar names, reasonable date proximity)")
        
        while True:
            choice = input("\nSelect detection level (1-2): ").strip()
            if choice in ['1', '2']:
                break
            print("Please enter 1 or 2.")
        
        # Set thresholds based on choice
        if choice == '1':
            name_threshold = 0.9  # Very similar names
            date_threshold = 2    # Within 2 years
            description = "Strict"
        else:  # choice == '2'
            name_threshold = 0.8  # Similar names
            date_threshold = 5    # Within 5 years
            description = "Standard"
        
        print(f"\nUsing {description} matching:")
        print(f"  - Name similarity threshold: {name_threshold}")
        print(f"  - Date proximity threshold: ±{date_threshold} years")
        print(f"  - Analyzing {len(individuals)} individuals...\n")
        
        # Pre-filter individuals to only those with names and reasonable birth years
        candidates = []
        for ind in individuals:
            if (ind.name and 
                len(ind.name.strip()) > 3 and  # Skip very short names
                (not ind.birth_year or 1400 <= ind.birth_year <= 2100)):  # Reasonable birth years only
                candidates.append(ind)
        
        print(f"  - Filtered to {len(candidates)} candidates (removed short names, unreasonable dates)")
        
        # Pre-calculate family relationships for fast lookup
        print("  - Building family relationship cache...")
        parent_cache = {}
        sibling_cache = {}
        
        for person in candidates:
            parents = self.get_parents_fast(person.xref_id)
            parent_cache[person.xref_id] = {p.xref_id for p in parents}
            
            # Get siblings through shared parents
            siblings = set()
            for parent in parents:
                for child in self.get_children_fast(parent.xref_id):
                    if child.xref_id != person.xref_id:
                        siblings.add(child.xref_id)
            sibling_cache[person.xref_id] = siblings
        
        # Find duplicates with optimized comparison
        duplicates = []
        total_comparisons = len(candidates) * (len(candidates) - 1) // 2
        comparisons_done = 0
        
        print(f"  - Starting {total_comparisons:,} comparisons...")
        
        for i, person1 in enumerate(candidates):
            # Progress update every 1000 comparisons or 10% intervals
            if comparisons_done % 1000 == 0 or comparisons_done % (total_comparisons // 10) == 0:
                progress = (comparisons_done / total_comparisons) * 100
                print(f"    Progress: {progress:.1f}% ({comparisons_done:,}/{total_comparisons:,})")
            
            for person2 in candidates[i+1:]:
                comparisons_done += 1
                
                # Quick name similarity check first (fastest filter)
                name_similarity = self._calculate_name_similarity(person1.name, person2.name)
                if name_similarity < name_threshold:
                    continue  # Skip if names not similar enough
                
                # Family relationship checks
                person1_parents = parent_cache[person1.xref_id]
                person2_parents = parent_cache[person2.xref_id]
                
                # Skip if they have same parents but ages don't overlap (child mortality reuse)
                if person1_parents and person2_parents and person1_parents == person2_parents:
                    # Same parents - check if ages overlap (accounting for uncertainty)
                    if not self._ages_overlap(person1, person2, tolerance=5):
                        continue  # Skip - likely name reuse after child death
                
                # Skip if they are cousins (one's parent is sibling of other's parent)
                if self._are_cousins(person1_parents, person2_parents, sibling_cache):
                    continue
                
                # Date proximity check (more expensive)
                date_proximity_score, date_details = self._calculate_date_proximity(person1, person2, date_threshold)
                
                if date_proximity_score > 0:  # Any date match within threshold
                    duplicate_entry = {
                        'person1': person1,
                        'person2': person2,
                        'name_similarity': name_similarity,
                        'date_proximity': date_proximity_score,
                        'date_details': date_details,
                        'confidence': self._calculate_confidence_score(name_similarity, date_proximity_score)
                    }
                    duplicates.append(duplicate_entry)
        
        print(f"Analysis complete.\n")
        
        if not duplicates:
            print(f"✅ No potential duplicates found with {description.lower()} matching criteria.")
            input("\nPress Enter to continue...")
            return
        
        # Sort by confidence score (highest first)
        duplicates.sort(key=lambda x: x['confidence'], reverse=True)
        
        print(f"❌ Found {len(duplicates)} potential duplicate pair(s):\n")
        print("=" * 80)
        
        # Display results (same as before)
        for i, dup in enumerate(duplicates, 1):
            person1 = dup['person1']
            person2 = dup['person2']
            confidence = dup['confidence']
            name_sim = dup['name_similarity']
            date_details = dup['date_details']
            
            # Format dates for display
            def format_person_dates(person):
                birth = "Unknown"
                death = "Unknown"
                
                if person.birth_date:
                    birth = person.birth_date.strftime('%d %b %Y')
                elif person.birth_year:
                    birth = str(person.birth_year)
                
                if person.death_date:
                    death = person.death_date.strftime('%d %b %Y')
                elif person.death_year:
                    death = str(person.death_year)
                elif not person.is_deceased():
                    death = "Living"
                
                return birth, death
            
            birth1, death1 = format_person_dates(person1)
            birth2, death2 = format_person_dates(person2)
            
            # Confidence level description
            if confidence >= 0.9:
                conf_desc = "Very High"
            elif confidence >= 0.8:
                conf_desc = "High"
            elif confidence >= 0.7:
                conf_desc = "Medium"
            else:
                conf_desc = "Low"
            
            print(f"Potential Duplicate #{i} - Confidence: {conf_desc} ({confidence:.2f})")
            print(f"  Name Similarity: {name_sim:.2f}")
            print()
            print(f"  Person A: {person1.name} [{person1.xref_id}]")
            print(f"    Born: {birth1} | Died: {death1}")
            print(f"    Birth Place: {person1.birth_place or 'Unknown'}")
            print()
            print(f"  Person B: {person2.name} [{person2.xref_id}]")
            print(f"    Born: {birth2} | Died: {death2}")
            print(f"    Birth Place: {person2.birth_place or 'Unknown'}")
            print()
            print(f"  Date Analysis: {date_details}")
            print()
            
            # Show family connections to help distinguish
            parents1 = self.get_parents_fast(person1.xref_id)
            parents2 = self.get_parents_fast(person2.xref_id)
            
            if parents1 or parents2:
                print(f"  Family Context:")
                if parents1:
                    parent_names = [p.name for p in parents1]
                    print(f"    Person A parents: {', '.join(parent_names)}")
                else:
                    print(f"    Person A parents: Unknown")
                
                if parents2:
                    parent_names = [p.name for p in parents2]
                    print(f"    Person B parents: {', '.join(parent_names)}")
                else:
                    print(f"    Person B parents: Unknown")
                print()
            
            print("=" * 80)
            print()
        
        # Summary statistics
        high_confidence = sum(1 for dup in duplicates if dup['confidence'] >= 0.8)
        medium_confidence = sum(1 for dup in duplicates if 0.7 <= dup['confidence'] < 0.8)
        low_confidence = sum(1 for dup in duplicates if dup['confidence'] < 0.7)
        
        print(f"Summary:")
        print(f"  High confidence (≥0.8): {high_confidence}")
        print(f"  Medium confidence (0.7-0.8): {medium_confidence}")
        print(f"  Low confidence (<0.7): {low_confidence}")
        print(f"  Total potential duplicates: {len(duplicates)}")
        print(f"\nNote: Excluded same-parent non-overlapping ages and cousin relationships.")
        
        input("\nPress Enter to continue...")

    def _ages_overlap(self, person1, person2, tolerance: int = 5) -> bool:
        """Check if two people's ages could have overlapped (accounting for uncertainty)."""
        # Get birth and death years for both people
        def get_life_span(person):
            birth_year = person.birth_year
            death_year = person.death_year if person.is_deceased() else None
            return birth_year, death_year
        
        birth1, death1 = get_life_span(person1)
        birth2, death2 = get_life_span(person2)
        
        # If we don't have birth years for both, assume they could overlap
        if not birth1 or not birth2:
            return True
        
        # Calculate the earliest possible death and latest possible birth for each
        # Add tolerance for date uncertainty
        
        # Person 1's life span (with tolerance)
        p1_earliest_death = death1 - tolerance if death1 else (birth1 + 100)  # Assume max 100 years if no death
        p1_latest_birth = birth1 + tolerance
        
        # Person 2's life span (with tolerance)
        p2_earliest_death = death2 - tolerance if death2 else (birth2 + 100)
        p2_latest_birth = birth2 + tolerance
        
        # They overlap if person1's life could have extended to person2's birth time or vice versa
        overlap = not (p1_earliest_death < p2_latest_birth or p2_earliest_death < p1_latest_birth)
        
        return overlap

    def _are_cousins(self, person1_parents: set, person2_parents: set, sibling_cache: dict) -> bool:
        """Check if two people are cousins (share grandparents but not parents)."""
        if not person1_parents or not person2_parents:
            return False
        
        # If they have the same parents, they're siblings, not cousins
        if person1_parents == person2_parents:
            return False
        
        # Check if any parent of person1 is a sibling of any parent of person2
        for parent1_id in person1_parents:
            parent1_siblings = sibling_cache.get(parent1_id, set())
            if person2_parents.intersection(parent1_siblings):
                return True  # Found cousin relationship
        
        return False

    def _calculate_name_similarity(self, name1: str, name2: str) -> float:
        """Calculate similarity between two names using multiple algorithms."""
        if not name1 or not name2:
            return 0.0
        
        # Normalize names
        def normalize_name(name):
            # Remove common prefixes/suffixes and extra whitespace
            name = name.lower().strip()
            # Remove common titles
            prefixes = ['mr', 'mrs', 'miss', 'dr', 'rev', 'sir', 'lady']
            suffixes = ['jr', 'sr', 'ii', 'iii', 'iv']
            
            words = name.split()
            words = [w for w in words if w not in prefixes and w not in suffixes]
            return ' '.join(words)
        
        norm1 = normalize_name(name1)
        norm2 = normalize_name(name2)
        
        # Exact match after normalization
        if norm1 == norm2:
            return 1.0
        
        # Use multiple similarity measures and take the highest
        similarities = []
        
        # 1. Levenshtein distance (edit distance)
        similarities.append(self._levenshtein_similarity(norm1, norm2))
        
        # 2. Jaccard similarity (word-based)
        similarities.append(self._jaccard_similarity(norm1, norm2))
        
        # 3. Common substring ratio
        similarities.append(self._common_substring_similarity(norm1, norm2))
        
        # Return the highest similarity score
        return max(similarities)

    def _levenshtein_similarity(self, s1: str, s2: str) -> float:
        """Calculate Levenshtein similarity (1 - normalized edit distance)."""
        if len(s1) < len(s2):
            s1, s2 = s2, s1
        
        if len(s2) == 0:
            return 0.0
        
        previous_row = list(range(len(s2) + 1))
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        edit_distance = previous_row[-1]
        max_len = max(len(s1), len(s2))
        return 1 - (edit_distance / max_len)

    def _jaccard_similarity(self, s1: str, s2: str) -> float:
        """Calculate Jaccard similarity based on word sets."""
        words1 = set(s1.split())
        words2 = set(s2.split())
        
        if not words1 and not words2:
            return 1.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union) if union else 0.0

    def _common_substring_similarity(self, s1: str, s2: str) -> float:
        """Calculate similarity based on longest common substring."""
        def longest_common_substring(str1, str2):
            m, n = len(str1), len(str2)
            dp = [[0] * (n + 1) for _ in range(m + 1)]
            length = 0
            
            for i in range(1, m + 1):
                for j in range(1, n + 1):
                    if str1[i-1] == str2[j-1]:
                        dp[i][j] = dp[i-1][j-1] + 1
                        length = max(length, dp[i][j])
                    else:
                        dp[i][j] = 0
            
            return length
        
        lcs_length = longest_common_substring(s1, s2)
        max_length = max(len(s1), len(s2))
        
        return lcs_length / max_length if max_length > 0 else 0.0

    def _calculate_date_proximity(self, person1, person2, threshold_years: int) -> tuple:
        """Calculate date proximity score and return details."""
        scores = []
        details = []
        
        # Compare birth dates
        birth_score = self._compare_dates(person1.birth_date, person1.birth_year,
                                        person2.birth_date, person2.birth_year,
                                        threshold_years, "birth")
        if birth_score > 0:
            scores.append(birth_score)
            birth_diff = self._get_date_difference(person1.birth_date, person1.birth_year,
                                                person2.birth_date, person2.birth_year)
            details.append(f"Birth dates within {abs(birth_diff)} years")
        
        # Compare death dates
        death_score = self._compare_dates(person1.death_date, person1.death_year,
                                        person2.death_date, person2.death_year,
                                        threshold_years, "death")
        if death_score > 0:
            scores.append(death_score)
            death_diff = self._get_date_difference(person1.death_date, person1.death_year,
                                                person2.death_date, person2.death_year)
            details.append(f"Death dates within {abs(death_diff)} years")
        
        # Overall score is the average of matching date types
        overall_score = sum(scores) / len(scores) if scores else 0
        detail_text = "; ".join(details) if details else "No matching dates within threshold"
        
        return overall_score, detail_text

    def _compare_dates(self, date1, year1, date2, year2, threshold: int, date_type: str) -> float:
        """Compare two dates and return proximity score."""
        diff = self._get_date_difference(date1, year1, date2, year2)
        
        if diff is None:
            return 0  # Can't compare if one or both dates are missing
        
        if abs(diff) <= threshold:
            # Score decreases as difference increases
            return 1 - (abs(diff) / threshold)
        
        return 0

    def _get_date_difference(self, date1, year1, date2, year2) -> int:
        """Get the difference in years between two dates."""
        # Get the best available year for each date
        def get_year(date_obj, year_int):
            if date_obj:
                return date_obj.year
            elif year_int:
                return year_int
            return None
        
        y1 = get_year(date1, year1)
        y2 = get_year(date2, year2)
        
        if y1 is None or y2 is None:
            return None
        
        return y1 - y2

    def _calculate_confidence_score(self, name_similarity: float, date_proximity: float) -> float:
        """Calculate overall confidence score for duplicate detection."""
        # Weight name similarity more heavily than date proximity
        # Names are more reliable identifiers than dates in genealogical data
        name_weight = 0.7
        date_weight = 0.3
        
        return (name_similarity * name_weight) + (date_proximity * date_weight)

