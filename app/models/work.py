from dataclasses import dataclass
from typing import Optional


@dataclass
class Work:
    id: str
    name: str
    category: str
    progress_unit: str
    progress_current: int
    progress_total: Optional[int]
    status: str
    release_day: Optional[str]
    synopsis: str
    rating: Optional[int]
    favorite: bool
    personal_notes: str
    created_at: str
    updated_at: str
