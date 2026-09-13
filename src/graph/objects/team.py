from pydantic import BaseModel
from typing import Optional

class Team(BaseModel):
    team_id: int
    name: str
    logo_url: Optional[str] = None
    country_name: Optional[str] = None
