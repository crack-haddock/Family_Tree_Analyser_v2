"""
Abstract base class for GEDCOM database implementations.
Provides a library-agnostic interface for family tree analysis.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Set, Any
from datetime import datetime


class Individual:
    """Wrapper class for individual records, normalizing data across different GEDCOM libraries."""
    
    def __init__(self, xref_id: str, raw_record: Any = None):
        self.xref_id = xref_id
        self.raw_record = raw_record  # Store the library-specific record
    
    @property
    def name(self) -> str:
        """Return formatted name."""
        # To be implemented by subclasses based on library
        return ""
    
    @property
    def birth_date(self) -> Optional[datetime]:
        """Return birth date if available."""
        # To be implemented by subclasses
        return None
    
    @property
    def death_date(self) -> Optional[datetime]:
        """Return death date if available."""
        # To be implemented by subclasses
        return None
    
    @property
    def birth_place(self) -> Optional[str]:
        """Return birth place if available."""
        # To be implemented by subclasses
        return None


class Family:
    """Wrapper class for family records."""
    
    def __init__(self, xref_id: str, raw_record: Any = None):
        self.xref_id = xref_id
        self.raw_record = raw_record


class GedcomDB(ABC):
    """Abstract base class for GEDCOM database implementations."""
    
    def __init__(self):
        self.capabilities = set()
        self.file_path = None
        self.is_loaded = False
    
    def supports(self, capability: str) -> bool:
        """Check if this implementation supports a specific capability."""
        return capability in self.capabilities
    
    @abstractmethod
    def load_file(self, file_path: str) -> bool:
        """Load GEDCOM file. Returns True if successful."""
        pass
    
    @abstractmethod
    def get_all_individuals(self) -> List[Individual]:
        """Return all individuals in the database."""
        pass
    
    @abstractmethod
    def get_all_families(self) -> List[Family]:
        """Return all families in the database."""
        pass
    
    @abstractmethod
    def find_individual_by_id(self, xref_id: str) -> Optional[Individual]:
        """Find individual by GEDCOM ID."""
        pass
    
    @abstractmethod
    def find_family_by_id(self, xref_id: str) -> Optional[Family]:
        """Find family by GEDCOM ID."""
        pass
    
    @abstractmethod
    def search_individuals_by_name(self, name: str, birth_year: Optional[int] = None) -> List[Individual]:
        """Search for individuals by name and optionally birth year."""
        pass
    
    # Optional capabilities - implement if supported
    def save_file(self, file_path: str) -> bool:
        """Save changes to GEDCOM file. Returns True if successful, False if not supported."""
        return False
    
    def add_individual(self, individual: Individual) -> bool:
        """Add new individual. Returns True if successful, False if not supported."""
        return False
    
    def update_individual(self, individual: Individual) -> bool:
        """Update existing individual. Returns True if successful, False if not supported."""
        return False
    
    def delete_individual(self, xref_id: str) -> bool:
        """Delete individual. Returns True if successful, False if not supported."""
        return False
