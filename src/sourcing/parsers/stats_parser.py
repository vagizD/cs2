import re
from typing import Optional, List, Tuple
from bs4 import BeautifulSoup
from src.graph.objects import MapResult, PlayerMapStats, Player

class StatsParser:
    """Parses raw HLTV map stats HTML pages into MapResult, PlayerMapStats, and Player objects."""

    @staticmethod
    def parse_map_stats_html(html_content: str, map_stats_id: int, fallback_match_id: Optional[int] = None) -> Tuple[Optional[MapResult], List[PlayerMapStats], List[Player]]:
        soup = BeautifulSoup(html_content, "lxml")

        # Match ID extraction
        match_id = fallback_match_id
        match_link = (
            soup.find("a", href=re.compile(r'^/matches/\d+/')) or
            soup.find("a", string=re.compile(r'More info on match page', re.I)) or
            soup.find("a", href=re.compile(r'/matches/\d+'))
        )
        if match_link:
            m = re.search(r'/matches/(\d+)', match_link["href"])
            if m:
                match_id = int(m.group(1))

        if not match_id:
            return None, [], []

        box = soup.find("div", class_="match-info-box")
        if not box:
            return None, [], []

        small_text = box.find("div", class_="small-text")
        map_name = str(small_text.next_sibling).strip() if small_text and small_text.next_sibling else "Unknown"

        t_left = box.find("div", class_="team-left")
        t_right = box.find("div", class_="team-right")

        t1_a = t_left.find("a", href=re.compile(r'/(?:stats/)?teams?/(\d+)')) if t_left else None
        t2_a = t_right.find("a", href=re.compile(r'/(?:stats/)?teams?/(\d+)')) if t_right else None

        team1_id = int(re.search(r'/(?:stats/)?teams?/(\d+)', t1_a["href"]).group(1)) if t1_a else None
        team2_id = int(re.search(r'/(?:stats/)?teams?/(\d+)', t2_a["href"]).group(1)) if t2_a else None

        s1_elem = t_left.find("div", class_=re.compile(r'won|lost')) if t_left else None
        s2_elem = t_right.find("div", class_=re.compile(r'won|lost')) if t_right else None

        team1_score = int(re.search(r'\d+', s1_elem.text).group(0)) if s1_elem and re.search(r'\d+', s1_elem.text) else 0
        team2_score = int(re.search(r'\d+', s2_elem.text).group(0)) if s2_elem and re.search(r'\d+', s2_elem.text) else 0

        overtime = False
        if team1_score + team2_score > 24 or team1_score > 13 or team2_score > 13:
            overtime = True

        # Player stats tables
        stats_tables = soup.find_all("table", class_="stats-table")
        player_stats_list = []
        player_objects = []

        target_tables = []
        if len(stats_tables) >= 4:
            target_tables = [(stats_tables[0], team1_id), (stats_tables[3], team2_id)]
        elif len(stats_tables) >= 2:
            target_tables = [(stats_tables[0], team1_id), (stats_tables[1], team2_id)]

        for table, team_id in target_tables:
            if not team_id:
                th_team = table.find("a", href=re.compile(r'/(?:stats/)?teams?/(\d+)'))
                if th_team:
                    team_id = int(re.search(r'/(?:stats/)?teams?/(\d+)', th_team["href"]).group(1))
            if not team_id:
                continue

            headers = [th.text.strip() for th in table.find_all("th")]

            tbody = table.find("tbody")
            rows = tbody.find_all("tr") if tbody else table.find_all("tr")[1:]

            for r in rows:
                p_a = r.find("a", href=re.compile(r'/(?:player|stats/players)/(\d+)'))
                if not p_a:
                    continue
                p_id = int(re.search(r'/(?:player|stats/players)/(\d+)', p_a["href"]).group(1))
                p_name = p_a.text.strip()

                country_name = None
                flag_img = r.find("img", class_="flag") or r.find("img")
                if flag_img:
                    country_name = (flag_img.get("title") or flag_img.get("alt") or "").strip()

                if p_id:
                    player_objects.append(Player(
                        player_id=p_id,
                        nickname=p_name,
                        country_name=country_name
                    ))

                tds = [td.text.strip() for td in r.find_all("td")]

                kills, deaths, assists = 0, 0, 0
                hs_kills, flash_ast, op_k, op_d, mks, clutches = None, None, None, None, None, None
                adr_val, kast_val, rating_val = None, None, None

                for col_idx, header in enumerate(headers):
                    if col_idx >= len(tds):
                        continue
                    val_str = tds[col_idx]
                    h_upper = header.strip().upper()

                    if h_upper.startswith("EK") or h_upper.startswith("EA") or h_upper.startswith("ED") or h_upper.startswith("OP.EK"):
                        continue

                    if h_upper in ["OP.K-D", "OPENING K-D", "OPENING"]:
                        m = re.search(r'(\d+)\s*:\s*(\d+)', val_str)
                        if m:
                            op_k, op_d = int(m.group(1)), int(m.group(2))
                    elif h_upper == "MKS":
                        if val_str.isdigit():
                            mks = int(val_str)
                    elif h_upper in ["1VSX", "1V1", "CLUTCHES"]:
                        if val_str.isdigit():
                            clutches = int(val_str)
                    elif h_upper in ["K (HS)", "K-D", "K"] or h_upper == "KILLS":
                        m = re.search(r'(\d+)(?:\s*\((\d+)\))?', val_str)
                        if m:
                            kills = int(m.group(1))
                            if m.group(2):
                                hs_kills = int(m.group(2))
                    elif h_upper in ["A (F)", "A"] or h_upper == "ASSISTS":
                        m = re.search(r'(\d+)(?:\s*\((\d+)\))?', val_str)
                        if m:
                            assists = int(m.group(1))
                            if m.group(2):
                                flash_ast = int(m.group(2))
                    elif h_upper in ["D (T)", "D"] or h_upper == "DEATHS":
                        m = re.search(r'(\d+)', val_str)
                        if m:
                            deaths = int(m.group(1))
                    elif h_upper == "ADR":
                        v = val_str.replace(",", ".")
                        if v.replace(".", "", 1).isdigit():
                            adr_val = float(v)
                    elif h_upper == "KAST":
                        v = val_str.replace("%", "").strip()
                        if v.replace(".", "", 1).isdigit():
                            kast_val = float(v)
                    elif "RATING" in h_upper and not h_upper.startswith("E"):
                        v = val_str.replace(",", ".")
                        if v.replace(".", "", 1).isdigit():
                            rating_val = float(v)

                player_stats_list.append(PlayerMapStats(
                    map_stats_id=map_stats_id,
                    match_id=match_id,
                    team_id=team_id,
                    player_id=p_id,
                    player_name=p_name,
                    kills=kills,
                    deaths=deaths,
                    assists=assists,
                    headshot_kills=hs_kills,
                    flash_assists=flash_ast,
                    opening_kills=op_k,
                    opening_deaths=op_d,
                    multi_kills=mks,
                    clutches_won=clutches,
                    adr=adr_val,
                    kast_pct=kast_val,
                    rating=rating_val
                ))

        map_result = None
        if team1_id and team2_id:
            map_result = MapResult(
                map_stats_id=map_stats_id,
                match_id=match_id,
                map_name=map_name,
                team1_id=team1_id,
                team2_id=team2_id,
                team1_score=team1_score,
                team2_score=team2_score,
                overtime=overtime
            )

        return map_result, player_stats_list, player_objects
