from pydantic import BaseModel
from typing import Optional

class Event(BaseModel):
    event_id: int
    name: str
    date_range_str: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    location: Optional[str] = None
    prize_pool: Optional[str] = None
    prize_pool_usd: Optional[int] = None
    is_lan: Optional[bool] = None
    event_type: Optional[str] = None
    event_tier: Optional[str] = None
