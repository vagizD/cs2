from pydantic import BaseModel
from typing import List

class RankingSnapshot(BaseModel):
    snapshot_date: str  # YYYY-MM-DD
    rank: int
    team_id: int
    team_name: str
    points: int
    player_ids: List[int]
