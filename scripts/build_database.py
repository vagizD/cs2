import os
import glob
import re
import json
import time
from multiprocessing import Pool, cpu_count

from src.db.storage import Storage
from src.sourcing.parsers.rankings_parser import RankingsParser
from src.sourcing.parsers.events_parser import EventsParser
from src.sourcing.parsers.matches_parser import MatchesParser
from src.sourcing.parsers.stats_parser import StatsParser

def parse_ranking_file(fpath):
    m = re.search(r'(\d{4}-\d{2}-\d{2})\.html$', fpath)
    if not m:
        return None
    date_str = m.group(1)
    with open(fpath, "r", encoding="utf-8") as f:
        html = f.read()
    snapshots = RankingsParser.parse_ranking_html(html, date_str)
    rows = []
    teams = {}
    if snapshots:
        for s in snapshots:
            p_ids = s.player_ids + [None] * (5 - len(s.player_ids))
            rows.append((
                s.snapshot_date, s.rank, s.team_id, s.team_name, s.points,
                p_ids[0], p_ids[1], p_ids[2], p_ids[3], p_ids[4]
            ))
            teams[s.team_id] = (s.team_id, s.team_name, None, None)
    return rows, teams

def parse_event_file(fpath):
    m = re.search(r'(\d+)\.html$', fpath)
    if not m:
        return None
    event_id = int(m.group(1))
    with open(fpath, "r", encoding="utf-8") as f:
        html = f.read()
    e = EventsParser.parse_event_html(html, event_id)
    if e:
        return (
            e.event_id, e.name, e.start_date, e.end_date, e.date_range_str,
            e.location, e.prize_pool, e.prize_pool_usd,
            1 if e.is_lan else (0 if e.is_lan is False else None),
            e.event_type, e.event_tier
        )
    return None

def parse_match_file(fpath):
    m = re.search(r'(\d+)\.html$', fpath)
    if not m:
        return None
    match_id = int(m.group(1))
    with open(fpath, "r", encoding="utf-8") as f:
        html = f.read()
    res = MatchesParser.parse_match_html(html, match_id)
    if res and res[0]:
        match_obj, map_stats_ids, player_objs, player_roles = res
        match_tuple = (
            match_obj.match_id, match_obj.event_id, match_obj.datetime_utc,
            match_obj.team1_id, match_obj.team1_name, match_obj.team2_id, match_obj.team2_name,
            match_obj.team1_score, match_obj.team2_score, match_obj.format,
            json.dumps(match_obj.maps_played),
            json.dumps(match_obj.lineup1_player_ids),
            json.dumps(match_obj.lineup2_player_ids)
        )
        teams = {
            match_obj.team1_id: (match_obj.team1_id, match_obj.team1_name, None, None),
            match_obj.team2_id: (match_obj.team2_id, match_obj.team2_name, None, None)
        }
        players = {}
        for p in player_objs:
            players[p.player_id] = (p.player_id, p.nickname, p.real_name, p.country_name)

        role_tuples = []
        for pid, (is_cap, is_awp) in player_roles.items():
            role_tuples.append((match_id, pid, is_cap, is_awp))

        return match_tuple, teams, players, role_tuples
    return None

def parse_stats_file(fpath):
    m = re.search(r'(\d+)\.html$', fpath)
    if not m:
        return None
    map_stats_id = int(m.group(1))
    with open(fpath, "r", encoding="utf-8") as f:
        html = f.read()
    map_res, p_stats, p_objs = StatsParser.parse_map_stats_html(html, map_stats_id)
    
    map_tuple = None
    if map_res:
        map_tuple = (
            map_res.map_stats_id, map_res.match_id, map_res.map_name,
            map_res.team1_id, map_res.team2_id, map_res.team1_score, map_res.team2_score,
            1 if map_res.overtime else 0
        )
    
    player_stat_tuples = []
    players = {}
    if p_objs:
        for p in p_objs:
            players[p.player_id] = (p.player_id, p.nickname, p.real_name, p.country_name)

    if p_stats:
        for s in p_stats:
            player_stat_tuples.append((
                s.map_stats_id, s.match_id, s.team_id, s.player_id, s.player_name,
                s.kills, s.deaths, s.assists, s.headshot_kills, s.flash_assists,
                s.opening_kills, s.opening_deaths, s.multi_kills, s.clutches_won,
                s.adr, s.kast_pct, s.rating
            ))
            if s.player_id not in players:
                players[s.player_id] = (s.player_id, s.player_name, None, None)
            
    return map_tuple, player_stat_tuples, players

def main():
    start_time = time.time()
    db_path = "data/processed/hltv_database.db"
    num_workers = max(1, cpu_count() - 1)

    print("==================================================")
    print("      REBUILDING HLTV DATABASE FROM RAW HTML     ")
    print(f"      (Parallel execution with {num_workers} CPU workers)")
    print("==================================================")

    if os.path.exists(db_path):
        print(f"Removing existing database: {db_path}")
        os.remove(db_path)

    storage = Storage(db_path)
    conn = storage._get_connection()
    cursor = conn.cursor()

    print("Database schema initialized successfully.")

    with Pool(num_workers) as pool:
        # --------------------------------------------------
        # Step 1: Rankings Snapshots
        # --------------------------------------------------
        ranking_files = glob.glob("data/raw/rankings/*.html")
        print(f"\n[1/4] Parsing {len(ranking_files):,} ranking snapshot HTML files...")
        snapshot_tuples = []
        team_tuples = {}

        results = pool.map(parse_ranking_file, ranking_files, chunksize=10)
        for res in results:
            if res:
                rows, teams = res
                snapshot_tuples.extend(rows)
                team_tuples.update(teams)

        cursor.executemany("""
            INSERT INTO ranking_snapshot (snapshot_date, rank, team_id, team_name, points, player_id1, player_id2, player_id3, player_id4, player_id5)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, snapshot_tuples)
        print(f"  -> Inserted {len(snapshot_tuples):,} ranking snapshot rows.")

        # --------------------------------------------------
        # Step 2: Events Metadata
        # --------------------------------------------------
        event_files = glob.glob("data/raw/events/*.html")
        print(f"\n[2/4] Parsing {len(event_files):,} event HTML files...")
        event_tuples = []

        results = pool.map(parse_event_file, event_files, chunksize=50)
        for res in results:
            if res:
                event_tuples.append(res)

        cursor.executemany("""
            INSERT INTO event (event_id, name, start_date, end_date, date_range_str, location, prize_pool, prize_pool_usd, is_lan, event_type, event_tier)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, event_tuples)
        print(f"  -> Inserted {len(event_tuples):,} event rows.")

        # --------------------------------------------------
        # Step 3: Matches Details
        # --------------------------------------------------
        match_files = glob.glob("data/raw/matches/*.html")
        print(f"\n[3/4] Parsing {len(match_files):,} match HTML files...")
        match_tuples = []
        player_tuples = {}
        match_player_roles = {}  # (match_id, player_id) -> (is_captain, is_awp)

        results = pool.map(parse_match_file, match_files, chunksize=100)
        for res in results:
            if res:
                match_tuple, teams, players, role_tuples = res
                match_tuples.append(match_tuple)
                team_tuples.update(teams)
                for pid, tuple_val in players.items():
                    if pid not in player_tuples or (tuple_val[2] and not player_tuples[pid][2]):
                        player_tuples[pid] = tuple_val
                for mid, pid, is_cap, is_awp in role_tuples:
                    match_player_roles[(mid, pid)] = (is_cap, is_awp)

        cursor.executemany("""
            INSERT INTO match (match_id, event_id, datetime_utc, team1_id, team1_name, team2_id, team2_name, team1_score, team2_score, format, maps_played, lineup1_player_ids, lineup2_player_ids)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, match_tuples)
        print(f"  -> Inserted {len(match_tuples):,} match rows.")

        # Insert unique teams
        cursor.executemany("""
            INSERT INTO team (team_id, name, logo_url, country_name)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(team_id) DO NOTHING
        """, list(team_tuples.values()))

        # --------------------------------------------------
        # Step 4: Map Stats & Player Performance
        # --------------------------------------------------
        stats_files = glob.glob("data/raw/stats/*.html")
        print(f"\n[4/4] Parsing {len(stats_files):,} map stats HTML files...")
        map_result_tuples = []
        player_stats_tuples = []

        results = pool.map(parse_stats_file, stats_files, chunksize=200)
        for res in results:
            if res:
                map_tuple, p_stat_tuples, players = res
                if map_tuple:
                    map_result_tuples.append(map_tuple)
                for pid, tuple_val in players.items():
                    if pid not in player_tuples or (tuple_val[3] and not player_tuples[pid][3]):
                        player_tuples[pid] = tuple_val
                for st in p_stat_tuples:
                    mid = st[1]
                    pid = st[3]
                    is_cap, is_awp = match_player_roles.get((mid, pid), (0, 0))
                    full_stat_tuple = st + (is_cap, is_awp)
                    player_stats_tuples.append(full_stat_tuple)

        cursor.executemany("""
            INSERT INTO map_result (map_stats_id, match_id, map_name, team1_id, team2_id, team1_score, team2_score, overtime)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, map_result_tuples)
        print(f"  -> Inserted {len(map_result_tuples):,} map_result rows.")

        cursor.executemany("""
            INSERT INTO player_map_stats (
                map_stats_id, match_id, team_id, player_id, player_name, kills, deaths, assists,
                headshot_kills, flash_assists, opening_kills, opening_deaths, multi_kills, clutches_won,
                adr, kast_pct, rating, is_captain, is_awp
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, player_stats_tuples)
        print(f"  -> Inserted {len(player_stats_tuples):,} player_map_stats rows.")

        cursor.executemany("""
            INSERT INTO player (player_id, nickname, real_name, country_name)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(player_id) DO UPDATE SET
                nickname=excluded.nickname,
                real_name=COALESCE(excluded.real_name, player.real_name),
                country_name=COALESCE(excluded.country_name, player.country_name)
        """, list(player_tuples.values()))

    conn.commit()

    # --------------------------------------------------
    # Step 5: Recalculate match map scores
    # --------------------------------------------------
    print("\nRecalculating match scores from map results...")
    storage.recalculate_match_scores()

    conn.close()

    elapsed = time.time() - start_time
    print("\n==================================================")
    print("             REBUILD COMPLETE SUMMARY             ")
    print("==================================================")
    print(f"Total time elapsed: {elapsed:.2f} seconds ({elapsed/60:.2f} minutes)")

    with storage._get_connection() as c:
        print(f"  - Ranking Snapshots: {c.execute('SELECT COUNT(*) FROM ranking_snapshot').fetchone()[0]:,}")
        print(f"  - Events:            {c.execute('SELECT COUNT(*) FROM event').fetchone()[0]:,}")
        print(f"  - Matches:           {c.execute('SELECT COUNT(*) FROM match').fetchone()[0]:,}")
        print(f"  - Map Results:       {c.execute('SELECT COUNT(*) FROM map_result').fetchone()[0]:,}")
        print(f"  - Player Map Stats:  {c.execute('SELECT COUNT(*) FROM player_map_stats').fetchone()[0]:,}")
        print(f"  - Players:           {c.execute('SELECT COUNT(*) FROM player').fetchone()[0]:,}")
        print(f"  - LAN Events:        {c.execute('SELECT COUNT(*) FROM event WHERE is_lan = 1').fetchone()[0]:,} / {c.execute('SELECT COUNT(*) FROM event').fetchone()[0]:,}")

if __name__ == "__main__":
    main()
