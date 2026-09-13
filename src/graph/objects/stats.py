from pydantic import BaseModel
from typing import Optional

class MapResult(BaseModel):
    map_stats_id: int
    match_id: int
    map_name: str
    team1_id: int
    team2_id: int
    team1_score: int
    team2_score: int
    overtime: bool = False

class PlayerMapStats(BaseModel):
    map_stats_id: int
    match_id: int
    team_id: int
    player_id: int
    player_name: str
    kills: int
    deaths: int
    assists: int
    headshot_kills: Optional[int] = None
    flash_assists: Optional[int] = None
    opening_kills: Optional[int] = None
    opening_deaths: Optional[int] = None
    multi_kills: Optional[int] = None
    clutches_won: Optional[int] = None
    adr: Optional[float] = None
    kast_pct: Optional[float] = None
    rating: Optional[float] = None
    is_captain: Optional[int] = 0
    is_awp: Optional[int] = 0
