import re
from pathlib import Path
from typing import List, Optional
from bs4 import BeautifulSoup
from src.graph.objects import RankingSnapshot, Team, Player

class RankingsParser:
    """Parses raw HLTV ranking HTML files into RankingSnapshot objects."""

    @staticmethod
    def parse_ranking_html(html_content: str, snapshot_date: str) -> List[RankingSnapshot]:
        soup = BeautifulSoup(html_content, "lxml")
        snapshots = []

        ranked_team_divs = soup.find_all("div", class_="ranked-team")
        for div in ranked_team_divs:
            # Rank position
            pos_elem = div.find("span", class_="position")
            if not pos_elem:
                continue
            rank_str = pos_elem.text.strip().replace("#", "")
            if not rank_str.isdigit():
                continue
            rank = int(rank_str)

            # Team name and ID
            name_elem = div.find("span", class_="name")
            team_name = name_elem.text.strip() if name_elem else "Unknown"

            # Team ID from details link
            team_id = None
            details_link = div.find("a", class_="details")
            if details_link and "href" in details_link.attrs:
                # e.g., /ranking/teams/2024/january/1/details/9565 or /team/9565/vitality
                match = re.search(r'/(?:details|team)/(\d+)', details_link["href"])
                if match:
                    team_id = int(match.group(1))

            if not team_id:
                # Fallback: relative team link inside ranking
                team_link = div.find("a", href=re.compile(r'/team/(\d+)'))
                if team_link:
                    m = re.search(r'/team/(\d+)', team_link["href"])
                    if m:
                        team_id = int(m.group(1))

            if not team_id:
                continue

            # Points
            points_elem = div.find("span", class_="points")
            points = 0
            if points_elem:
                m_pts = re.search(r'(\d+)', points_elem.text)
                if m_pts:
                    points = int(m_pts.group(1))

            # Listed player IDs
            player_ids = []
            player_links = div.find_all("a", class_="pointer")
            for pl in player_links:
                href = pl.get("href", "")
                m_pl = re.search(r'/player/(\d+)/', href)
                if m_pl:
                    player_ids.append(int(m_pl.group(1)))

            snapshots.append(RankingSnapshot(
                snapshot_date=snapshot_date,
                rank=rank,
                team_id=team_id,
                team_name=team_name,
                points=points,
                player_ids=player_ids
            ))

        return snapshots
