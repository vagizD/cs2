from pydantic import BaseModel
from typing import Optional, List

class Match(BaseModel):
    match_id: int
    event_id: Optional[int] = None
    datetime_utc: Optional[str] = None
    team1_id: int
    team1_name: str
    team2_id: int
    team2_name: str
    team1_score: Optional[int] = None
    team2_score: Optional[int] = None
    format: Optional[str] = None  # e.g., 'bo1', 'bo3', 'bo5'
    maps_played: List[str] = []
    lineup1_player_ids: List[int] = []
    lineup2_player_ids: List[int] = []
