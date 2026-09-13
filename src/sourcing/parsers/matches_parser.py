import re
from datetime import datetime, timezone
from typing import Optional, List, Tuple
from bs4 import BeautifulSoup
from src.graph.objects import Match, Player

class MatchesParser:
    """Parses raw HLTV match HTML pages into Match graph objects and Player objects."""

    @staticmethod
    def parse_match_html(html_content: str, match_id: int) -> Tuple[Optional[Match], List[int], List[Player], dict]:
        soup = BeautifulSoup(html_content, "lxml")

        # Teams Box
        teams_box = soup.find("div", class_="teamsBox")
        if not teams_box:
            return None, [], [], {}

        teams = teams_box.find_all("div", class_="team")
        if len(teams) < 2:
            return None, [], [], {}

        # Team 1
        t1_link = teams[0].find("a", href=re.compile(r'/team/(\d+)'))
        t1_name_elem = teams[0].find("div", class_="teamName")
        team1_name = t1_name_elem.text.strip() if t1_name_elem else "Unknown"
        team1_id = int(re.search(r'/team/(\d+)', t1_link["href"]).group(1)) if t1_link else None

        # Team 2
        t2_link = teams[1].find("a", href=re.compile(r'/team/(\d+)'))
        t2_name_elem = teams[1].find("div", class_="teamName")
        team2_name = t2_name_elem.text.strip() if t2_name_elem else "Unknown"
        team2_id = int(re.search(r'/team/(\d+)', t2_link["href"]).group(1)) if t2_link else None

        if not team1_id or not team2_id:
            return None, [], [], {}

        # Scores (check div.won, div.lost, div.tie, or div.score in team 1 and team 2)
        team1_score, team2_score = None, None
        t1_score_elem = teams[0].find("div", class_=re.compile(r'won|lost|tie|score'))
        if t1_score_elem:
            m1 = re.search(r'\d+', t1_score_elem.text)
            if m1:
                team1_score = int(m1.group(0))

        t2_score_elem = teams[1].find("div", class_=re.compile(r'won|lost|tie|score'))
        if t2_score_elem:
            m2 = re.search(r'\d+', t2_score_elem.text)
            if m2:
                team2_score = int(m2.group(0))

        # Event ID & Name
        event_id = None
        event_div = soup.find("div", class_="event") or soup.find("div", class_="timeAndEvent") or soup.find("div", class_="event-text")
        if event_div:
            event_link = event_div.find("a", href=re.compile(r'/events/(\d+)'))
            if event_link:
                m_ev = re.search(r'/events/(\d+)', event_link["href"])
                if m_ev:
                    event_id = int(m_ev.group(1))

        if not event_id:
            event_link = soup.find("a", href=re.compile(r'/events/(\d+)'))
            if event_link:
                m_ev = re.search(r'/events/(\d+)', event_link["href"])
                if m_ev:
                    event_id = int(m_ev.group(1))

        # Date & Time (UTC)
        datetime_utc = None
        date_div = soup.find("div", class_="date")
        if date_div and date_div.has_attr("data-unix"):
            ts_ms = date_div["data-unix"]
            if ts_ms.isdigit():
                dt = datetime.fromtimestamp(int(ts_ms) / 1000.0, timezone.utc)
                datetime_utc = dt.strftime("%Y-%m-%d %H:%M:%S")

        # Format (bo1, bo3, bo5)
        match_format = None
        format_elem = soup.find("div", class_="formats") or soup.find("div", class_="preformatted-text")
        if format_elem:
            f_text = format_elem.text.lower()
            if "bo1" in f_text or "best of 1" in f_text:
                match_format = "bo1"
            elif "bo3" in f_text or "best of 3" in f_text:
                match_format = "bo3"
            elif "bo5" in f_text or "best of 5" in f_text:
                match_format = "bo5"

        # Standardize BO1 score to maps won (1-0 or 0-1)
        if match_format == "bo1" and team1_score is not None and team2_score is not None:
            if team1_score > team2_score:
                team1_score, team2_score = 1, 0
            elif team2_score > team1_score:
                team1_score, team2_score = 0, 1

        # Maps Played
        maps_played = []
        map_holders = soup.find_all("div", class_="mapholder")
        for m in map_holders:
            m_name_elem = m.find("div", class_="mapname")
            if m_name_elem:
                maps_played.append(m_name_elem.text.strip())

        # Lineups & Players (with real name, country, and roles)
        lineup1_player_ids = []
        lineup2_player_ids = []
        player_objects = []
        player_roles = {}  # pid -> (is_captain, is_awp)

        lineups_div = soup.find("div", class_="lineups")
        if lineups_div:
            lineup_teams = lineups_div.find_all("div", class_="lineup")
            for team_idx, l_team in enumerate(lineup_teams[:2]):
                player_tds = l_team.find_all("td", class_="player") or l_team.find_all("div", class_="player")
                seen_in_team = set()
                for p_td in player_tds:
                    p_link = p_td.find("a", href=re.compile(r'/player/(\d+)'))
                    if not p_link:
                        continue
                    pid = int(re.search(r'/player/(\d+)', p_link["href"]).group(1))
                    if pid in seen_in_team:
                        continue
                    seen_in_team.add(pid)

                    if team_idx == 0:
                        lineup1_player_ids.append(pid)
                    else:
                        lineup2_player_ids.append(pid)

                    # Extract nickname, real_name, country_name
                    nick_elem = p_td.find("div", class_="text-ellipsis") or p_link
                    nick = nick_elem.text.strip() if nick_elem else p_link.text.strip()
                    if not nick:
                        nick = p_link.text.strip()

                    real_name = None
                    country_name = None
                    for img in p_td.find_all("img"):
                        title_or_alt = (img.get("title") or img.get("alt") or "").strip()
                        if not title_or_alt:
                            continue
                        if img.get("class") and "flag" in img.get("class"):
                            country_name = title_or_alt
                        elif "'" in title_or_alt or " " in title_or_alt:
                            clean = re.sub(r"\s*'[^']*'\s*", " ", title_or_alt).strip()
                            if clean:
                                real_name = clean

                    # Roles
                    is_captain = 0
                    is_awp = 0
                    for span in p_td.find_all("span", class_="role-pill"):
                        rtitle = (span.get("title") or span.text).lower()
                        if any(term in rtitle for term in ["leader", "igl", "captain"]):
                            is_captain = 1
                        if "awp" in rtitle:
                            is_awp = 1

                    player_objects.append(Player(
                        player_id=pid,
                        nickname=nick,
                        real_name=real_name,
                        country_name=country_name
                    ))
                    player_roles[pid] = (is_captain, is_awp)

        stats_links = soup.find_all("a", href=re.compile(r'/stats/matches/mapstatsid/(\d+)'))
        map_stats_ids = []
        seen_ms = set()
        for a in stats_links:
            ms_id = int(re.search(r'/stats/matches/mapstatsid/(\d+)', a["href"]).group(1))
            if ms_id not in seen_ms:
                seen_ms.add(ms_id)
                map_stats_ids.append(ms_id)

        match_obj = Match(
            match_id=match_id,
            event_id=event_id,
            datetime_utc=datetime_utc,
            team1_id=team1_id,
            team1_name=team1_name,
            team2_id=team2_id,
            team2_name=team2_name,
            team1_score=team1_score,
            team2_score=team2_score,
            format=match_format,
            maps_played=maps_played,
            lineup1_player_ids=lineup1_player_ids,
            lineup2_player_ids=lineup2_player_ids
        )

        return match_obj, map_stats_ids, player_objects, player_roles
