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
    publication_status: str
    release_day: Optional[str]
    release_schedule_type: str
    release_days: Optional[str]
    release_month_day: Optional[int]
    release_anchor_date: Optional[str]
    last_release_read_date: Optional[str]
    reading_url: Optional[str]
    synopsis: str
    rating: Optional[float]
    favorite: bool
    personal_notes: str
    start_date: Optional[str]
    end_date: Optional[str]
    cover_path: Optional[str]
    created_at: str
    updated_at: str
