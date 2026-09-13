from pydantic import BaseModel
from typing import Optional

class Player(BaseModel):
    player_id: int
    nickname: str
    real_name: Optional[str] = None
    country_name: Optional[str] = None
