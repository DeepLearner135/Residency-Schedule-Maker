from dataclasses import dataclass, field
from typing import List, Optional, Dict
from datetime import date

@dataclass
class Resident:
    name: str
    pgy: str = "" # PGY-2, PGY-3, etc.
    total_call_weeks: int = 0
    total_inpatient_days: int = 0
    # Constraints
    vacation_dates: List[date] = field(default_factory=list)
    impossible_call_dates: List[date] = field(default_factory=list)

@dataclass
class Attending:
    name: str
    clinic_days: List[str] = field(default_factory=list) # "Monday", "Tuesday", etc.
    is_satellite: bool = False

@dataclass
class Block:
    name: str # "Block 1", "Block 2"
    start_date: date
    end_date: date

@dataclass
class BlockAssignment:
    block_name: str
    resident_name: str
    attending_name: str

