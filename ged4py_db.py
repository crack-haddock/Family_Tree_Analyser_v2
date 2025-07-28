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
    
    @property
    def records(self):
        """Access to source records for occupation extraction."""
        return self._source_index
    
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
        print("\n=== Dumping all wedding (marriage) records for all families and individuals ===\n")
        family_marriages = []
        individual_marriages = []

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
        for ind in self._individual_index.values():
            name = getattr(ind, "name", None) or ind.xref_id
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
            print(f"\nFamily: {fam['fam_id']}")
            print(f"  Husband: {fam['husband_name']}")
            print(f"  Wife: {fam['wife_name']}")
            print(f"  {fam['record'].tag}: {getattr(fam['record'], 'value', None)}")
            print(f"  Marriage Date: {fam['marriage_date']}")
            # Print all subfields recursively
            def print_subfields(rec, indent="    "):
                for field in getattr(rec, "sub_records", []):
                    tag = getattr(field, "tag", None)
                    value = getattr(field, "value", None)
                    print(f"{indent}{tag}: {value}")
                    if hasattr(field, "sub_records") and field.sub_records:
                        print_subfields(field, indent + "    ")
            print_subfields(fam['record'])

            # Print all info from the wedding source document(s)
            for sub in getattr(fam['record'], "sub_records", []):
                if getattr(sub, "tag", None) == "SOUR" and sub.value:
                    source_id = str(sub.value).strip()
                    source_record = self._source_index.get(source_id)
                    if source_record:
                        print(f"    --- Wedding Source Document ({source_id}) ---")
                        def print_source_fields(record, indent="      "):
                            for field in getattr(record, "sub_records", []):
                                tag = getattr(field, "tag", None)
                                value = getattr(field, "value", None)
                                print(f"{indent}{tag}: {value}")
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
                def print_subfields(rec, indent="    "):
                    for field in getattr(rec, "sub_records", []):
                        tag = getattr(field, "tag", None)
                        value = getattr(field, "value", None)
                        print(f"{indent}{tag}: {value}")
                        if hasattr(field, "sub_records") and field.sub_records:
                            print_subfields(field, indent + "    ")
                print_subfields(ind_mar['record'])
                individual_count += 1

        print(f"\nTotal family marriage records: {family_count}")
        print(f"Total individual marriage records (not matched): {individual_count}")

    def analyse_wedding_ages(self):
        """
        Analyse average ages at marriage for men and women.
        Prints overall, decade, and century stats with min/max/avg for bride and groom.
        Excludes ages >= 120 from stats, but keeps them in the 'over 40s' summary (ordered by age descending).
        Also prints a grand total summary with avg/min/max for both bride and groom.
        Brides under 16 and grooms under 16 are summarised at the end as likely invalid data.
        """
        print("\n=== Wedding Age Analysis ===\n")
        # Use ancestor filter if present
        if hasattr(self, "ancestor_filter_ids") and self.ancestor_filter_ids:
            individuals = [self._individual_index[xref_id] for xref_id in self.ancestor_filter_ids if xref_id in self._individual_index]
        else:
            individuals = list(self._individual_index.values())

        # Build lookup for birth years and names
        birth_years = {ind.xref_id: ind.birth_year for ind in individuals if ind.birth_year}
        names = {ind.xref_id: ind.name for ind in individuals}

        # Collect ages by decade and century
        decade_data = {}
        century_data = {}
        groom_ages = []
        bride_ages = []
        groom_over_40 = []
        bride_over_40 = []
        groom_under_16 = []
        bride_under_16 = []

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
                                marriage_year = int(str(sub2.value).strip()[-4:])
                            except Exception:
                                marriage_year = None
                            break

            if not marriage_year:
                continue

            decade = (marriage_year // 10) * 10
            century = (marriage_year // 100) * 100

            # Groom
            husband_birth = birth_years.get(husband_id)
            if husband_birth and marriage_year >= husband_birth:
                age = marriage_year - husband_birth
                if age > 40:
                    groom_over_40.append({
                        "name": names.get(husband_id, husband_id),
                        "age": age,
                        "marriage_year": marriage_year,
                        "fam_id": fam.xref_id
                    })
                if age < 16:
                    groom_under_16.append({
                        "name": names.get(husband_id, husband_id),
                        "age": age,
                        "marriage_year": marriage_year,
                        "fam_id": fam.xref_id
                    })
                if 16 <= age < 120:
                    groom_ages.append(age)
                    decade_data.setdefault(decade, {"bride": [], "groom": []})["groom"].append(age)
                    century_data.setdefault(century, {"bride": [], "groom": []})["groom"].append(age)
            # Bride
            wife_birth = birth_years.get(wife_id)
            if wife_birth and marriage_year >= wife_birth:
                age = marriage_year - wife_birth
                if age > 40:
                    bride_over_40.append({
                        "name": names.get(wife_id, wife_id),
                        "age": age,
                        "marriage_year": marriage_year,
                        "fam_id": fam.xref_id
                    })
                if age < 16:
                    bride_under_16.append({
                        "name": names.get(wife_id, wife_id),
                        "age": age,
                        "marriage_year": marriage_year,
                        "fam_id": fam.xref_id
                    })
                if 16 <= age < 120:
                    bride_ages.append(age)
                    decade_data.setdefault(decade, {"bride": [], "groom": []})["bride"].append(age)
                    century_data.setdefault(century, {"bride": [], "groom": []})["bride"].append(age)

        def avg(lst):
            return round(sum(lst) / len(lst), 2) if lst else None
        def minmax(lst):
            return (min(lst), max(lst)) if lst else (None, None)

        # Overall
        print(f"Overall average groom age at marriage: {avg(groom_ages)} ({len(groom_ages)} records)")
        print(f"Overall average bride age at marriage: {avg(bride_ages)} ({len(bride_ages)} records)\n")

        # Grand total stats across all data
        bride_min, bride_max = minmax(bride_ages)
        groom_min, groom_max = minmax(groom_ages)
        print("=== Grand Total Marriage Age Stats ===")
        print(f"  Bride Avg: {avg(bride_ages)} (min: {bride_min}, max: {bride_max})")
        print(f"  Groom Avg: {avg(groom_ages)} (min: {groom_min}, max: {groom_max})\n")

        # Per-decade
        print("=== Per-Decade Marriage Age Stats ===")
        grand_total = 0
        for decade in sorted(decade_data):
            bride_list = decade_data[decade]["bride"]
            groom_list = decade_data[decade]["groom"]
            all_ages = bride_list + groom_list
            n_records = max(len(bride_list), len(groom_list))
            grand_total += n_records
            bride_avg, groom_avg = avg(bride_list), avg(groom_list)
            bride_min, bride_max = minmax(bride_list)
            groom_min, groom_max = minmax(groom_list)
            overall_avg = avg(all_ages)
            print(f"{decade}s: {overall_avg} ({n_records} records)")
            print(f"    Bride Avg: {bride_avg} (min: {bride_min}, max: {bride_max})")
            print(f"    Groom Avg: {groom_avg} (min: {groom_min}, max: {groom_max})")
        print(f"\nGrand total marriages: {grand_total}")

        # Per-century
        print("\n=== Per-Century Marriage Age Stats ===")
        for century in sorted(century_data):
            bride_list = century_data[century]["bride"]
            groom_list = century_data[century]["groom"]
            all_ages = bride_list + groom_list
            n_records = max(len(bride_list), len(groom_list))
            bride_avg, groom_avg = avg(bride_list), avg(groom_list)
            bride_min, bride_max = minmax(bride_list)
            groom_min, groom_max = minmax(groom_list)
            overall_avg = avg(all_ages)
            century_label = f"{century//100+1}th century" if century >= 1000 else f"{century}s"
            print(f"{century_label}: {overall_avg} ({n_records} records)")
            print(f"    Bride Avg: {bride_avg} (min: {bride_min}, max: {bride_max})")
            print(f"    Groom Avg: {groom_avg} (min: {groom_min}, max: {groom_max})")

        # Flag individuals over 40 (ordered by age descending)
        if groom_over_40:
            print("\nGrooms over 40 at marriage:")
            for g in sorted(groom_over_40, key=lambda x: -x['age']):
                print(f"  {g['name']} (Family {g['fam_id']}): Age {g['age']} in {g['marriage_year']}")
        if bride_over_40:
            print("\nBrides over 40 at marriage:")
            for b in sorted(bride_over_40, key=lambda x: -x['age']):
                print(f"  {b['name']} (Family {b['fam_id']}): Age {b['age']} in {b['marriage_year']}")

        # Flag individuals under 16 (ordered by age ascending)
        if groom_under_16:
            print("\nGrooms under 16 at marriage (possible invalid data):")
            for g in sorted(groom_under_16, key=lambda x: x['age']):
                print(f"  {g['name']} (Family {g['fam_id']}): Age {g['age']} in {g['marriage_year']}")
        if bride_under_16:
            print("\nBrides under 16 at marriage (possible invalid data):")
            for b in sorted(bride_under_16, key=lambda x: x['age']):
                print(f"  {b['name']} (Family {b['fam_id']}): Age {b['age']} in {b['marriage_year']}")

        # If average is above 40, show all records
        if (avg(groom_ages) and avg(groom_ages) > 40) or (avg(bride_ages) and avg(bride_ages) > 40):
            print("\n*** WARNING: Average age above 40 detected. Listing all marriage ages: ***")
            print("\nAll groom ages:")
            for fam in self._family_index.values():
                husband_id = wife_id = None
                husband_birth = marriage_year = None
                for sub in getattr(fam.raw_record, "sub_records", []):
                    if getattr(sub, "tag", None) == "HUSB" and sub.value:
                        husband_id = str(sub.value)
                for sub in getattr(fam.raw_record, "sub_records", []):
                    if getattr(sub, "tag", None) in ("MARR", "MARRIAGE", "WEDDING"):
                        for sub2 in getattr(sub, "sub_records", []):
                            if getattr(sub2, "tag", None) == "DATE" and sub2.value:
                                try:
                                    marriage_year = int(str(sub2.value).strip()[-4:])
                                except Exception:
                                    marriage_year = None
                                break
                husband_birth = birth_years.get(husband_id)
                if husband_birth and marriage_year and marriage_year >= husband_birth:
                    age = marriage_year - husband_birth
                    print(f"  {names.get(husband_id, husband_id)}: Age {age} in {marriage_year} (Family {fam.xref_id})")
            print("\nAll bride ages:")
            for fam in self._family_index.values():
                wife_id = None
                wife_birth = marriage_year = None
                for sub in getattr(fam.raw_record, "sub_records", []):
                    if getattr(sub, "tag", None) == "WIFE" and sub.value:
                        wife_id = str(sub.value)
                for sub in getattr(fam.raw_record, "sub_records", []):
                    if getattr(sub, "tag", None) in ("MARR", "MARRIAGE", "WEDDING"):
                        for sub2 in getattr(sub, "sub_records", []):
                            if getattr(sub2, "tag", None) == "DATE" and sub2.value:
                                try:
                                    marriage_year = int(str(sub2.value).strip()[-4:])
                                except Exception:
                                    marriage_year = None
                                break
                wife_birth = birth_years.get(wife_id)
                if wife_birth and marriage_year and marriage_year >= wife_birth:
                    age = marriage_year - wife_birth
                    print(f"  {names.get(wife_id, wife_id)}: Age {age} in {marriage_year} (Family {fam.xref_id})")

