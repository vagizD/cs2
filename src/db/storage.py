import sqlite3
import json
from pathlib import Path
from typing import List, Set, Optional
from src.db.schema import CREATE_TABLES_SQL
from src.graph.objects import (
    Team, Player, RankingSnapshot, Event, Match, MapResult, PlayerMapStats
)

class Storage:
    def __init__(self, db_path: str = "data/processed/hltv_database.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.executescript(CREATE_TABLES_SQL)

    def save_team_conn(self, conn: sqlite3.Connection, team: Team):
        conn.execute("""
            INSERT INTO team (team_id, name, logo_url, country_name)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(team_id) DO UPDATE SET
                name=excluded.name,
                logo_url=COALESCE(excluded.logo_url, team.logo_url),
                country_name=COALESCE(excluded.country_name, team.country_name)
        """, (team.team_id, team.name, team.logo_url, team.country_name))

    def save_team(self, team: Team):
        with self._get_connection() as conn:
            self.save_team_conn(conn, team)

    def save_player_conn(self, conn: sqlite3.Connection, player: Player):
        conn.execute("""
            INSERT INTO player (player_id, nickname, real_name, country_name)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(player_id) DO UPDATE SET
                nickname=excluded.nickname,
                real_name=COALESCE(excluded.real_name, player.real_name),
                country_name=COALESCE(excluded.country_name, player.country_name)
        """, (player.player_id, player.nickname, player.real_name, player.country_name))

    def save_player(self, player: Player):
        with self._get_connection() as conn:
            self.save_player_conn(conn, player)

    def save_ranking_snapshots(self, snapshots: List[RankingSnapshot]):
        with self._get_connection() as conn:
            for s in snapshots:
                p_ids = s.player_ids + [None] * (5 - len(s.player_ids))
                conn.execute("""
                    INSERT INTO ranking_snapshot (snapshot_date, rank, team_id, team_name, points, player_id1, player_id2, player_id3, player_id4, player_id5)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(snapshot_date, team_id) DO UPDATE SET
                        rank=excluded.rank,
                        team_name=excluded.team_name,
                        points=excluded.points,
                        player_id1=excluded.player_id1,
                        player_id2=excluded.player_id2,
                        player_id3=excluded.player_id3,
                        player_id4=excluded.player_id4,
                        player_id5=excluded.player_id5
                """, (s.snapshot_date, s.rank, s.team_id, s.team_name, s.points, p_ids[0], p_ids[1], p_ids[2], p_ids[3], p_ids[4]))
                self.save_team_conn(conn, Team(team_id=s.team_id, name=s.team_name))

    def get_cohort_team_ids(self, max_rank: int = 30) -> Set[int]:
        """Returns set of team IDs that appeared in top max_rank at any point."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT DISTINCT team_id FROM ranking_snapshot WHERE rank <= ?", (max_rank,)).fetchall()
            return {row["team_id"] for row in rows}

    def get_cohort_team_names(self, max_rank: int = 30) -> Set[str]:
        """Returns set of normalized team names that appeared in top max_rank at any point."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT DISTINCT team_name FROM ranking_snapshot WHERE rank <= ?", (max_rank,)).fetchall()
            return {row["team_name"].strip().lower() for row in rows}

    def save_event(self, event: Event):
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO event (event_id, name, start_date, end_date, date_range_str, location, prize_pool, prize_pool_usd, is_lan, event_type, event_tier)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(event_id) DO UPDATE SET
                    name=excluded.name,
                    start_date=COALESCE(excluded.start_date, event.start_date),
                    end_date=COALESCE(excluded.end_date, event.end_date),
                    date_range_str=COALESCE(excluded.date_range_str, event.date_range_str),
                    location=COALESCE(excluded.location, event.location),
                    prize_pool=COALESCE(excluded.prize_pool, event.prize_pool),
                    prize_pool_usd=COALESCE(excluded.prize_pool_usd, event.prize_pool_usd),
                    is_lan=COALESCE(excluded.is_lan, event.is_lan),
                    event_type=COALESCE(excluded.event_type, event.event_type),
                    event_tier=COALESCE(excluded.event_tier, event.event_tier)
            """, (
                event.event_id, event.name, event.start_date, event.end_date,
                event.date_range_str, event.location, event.prize_pool, event.prize_pool_usd,
                1 if event.is_lan else (0 if event.is_lan is False else None),
                event.event_type, event.event_tier
            ))

    def recalculate_match_scores(self):
        """Derives maps won from map_result and updates match.team1_score and match.team2_score."""
        with self._get_connection() as conn:
            score_updates = conn.execute("""
                SELECT 
                    m.match_id,
                    SUM(CASE 
                        WHEN mr.team1_id = m.team1_id AND mr.team1_score > mr.team2_score THEN 1
                        WHEN mr.team2_id = m.team1_id AND mr.team2_score > mr.team1_score THEN 1
                        ELSE 0 
                    END) as t1_maps,
                    SUM(CASE 
                        WHEN mr.team1_id = m.team2_id AND mr.team1_score > mr.team2_score THEN 1
                        WHEN mr.team2_id = m.team2_id AND mr.team2_score > mr.team1_score THEN 1
                        ELSE 0 
                    END) as t2_maps
                FROM match m
                JOIN map_result mr ON m.match_id = mr.match_id
                GROUP BY m.match_id
            """).fetchall()

            params = [(row["t1_maps"], row["t2_maps"], row["match_id"]) for row in score_updates]
            conn.executemany("""
                UPDATE match 
                SET team1_score = ?, team2_score = ?
                WHERE match_id = ?
            """, params)

            # Standardize any remaining BO1 round scores to maps won (1-0 or 0-1)
            conn.execute("""
                UPDATE match
                SET team1_score = CASE WHEN team1_score > team2_score THEN 1 ELSE 0 END,
                    team2_score = CASE WHEN team2_score > team1_score THEN 1 ELSE 0 END
                WHERE format = 'bo1' AND (team1_score > 1 OR team2_score > 1)
            """)

    def save_match(self, match: Match):
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO match (match_id, event_id, datetime_utc, team1_id, team1_name, team2_id, team2_name, team1_score, team2_score, format, maps_played, lineup1_player_ids, lineup2_player_ids)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(match_id) DO UPDATE SET
                    event_id=COALESCE(excluded.event_id, match.event_id),
                    datetime_utc=COALESCE(excluded.datetime_utc, match.datetime_utc),
                    team1_score=COALESCE(excluded.team1_score, match.team1_score),
                    team2_score=COALESCE(excluded.team2_score, match.team2_score),
                    format=COALESCE(excluded.format, match.format),
                    maps_played=COALESCE(excluded.maps_played, match.maps_played),
                    lineup1_player_ids=COALESCE(excluded.lineup1_player_ids, match.lineup1_player_ids),
                    lineup2_player_ids=COALESCE(excluded.lineup2_player_ids, match.lineup2_player_ids)
            """, (
                match.match_id, match.event_id, match.datetime_utc,
                match.team1_id, match.team1_name, match.team2_id, match.team2_name,
                match.team1_score, match.team2_score, match.format,
                json.dumps(match.maps_played),
                json.dumps(match.lineup1_player_ids),
                json.dumps(match.lineup2_player_ids)
            ))
            self.save_team_conn(conn, Team(team_id=match.team1_id, name=match.team1_name))
            self.save_team_conn(conn, Team(team_id=match.team2_id, name=match.team2_name))

    def save_map_result(self, map_res: MapResult):
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO map_result (map_stats_id, match_id, map_name, team1_id, team2_id, team1_score, team2_score, overtime)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(map_stats_id) DO UPDATE SET
                    team1_score=excluded.team1_score,
                    team2_score=excluded.team2_score,
                    overtime=excluded.overtime
            """, (map_res.map_stats_id, map_res.match_id, map_res.map_name, map_res.team1_id, map_res.team2_id, map_res.team1_score, map_res.team2_score, 1 if map_res.overtime else 0))

    def save_player_map_stats(self, stats_list: List[PlayerMapStats]):
        with self._get_connection() as conn:
            for s in stats_list:
                conn.execute("""
                    INSERT INTO player_map_stats (
                        map_stats_id, match_id, team_id, player_id, player_name, kills, deaths, assists,
                        headshot_kills, flash_assists, opening_kills, opening_deaths, multi_kills, clutches_won,
                        adr, kast_pct, rating, is_captain, is_awp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(map_stats_id, player_id) DO UPDATE SET
                        kills=excluded.kills,
                        deaths=excluded.deaths,
                        assists=excluded.assists,
                        headshot_kills=COALESCE(excluded.headshot_kills, player_map_stats.headshot_kills),
                        flash_assists=COALESCE(excluded.flash_assists, player_map_stats.flash_assists),
                        opening_kills=COALESCE(excluded.opening_kills, player_map_stats.opening_kills),
                        opening_deaths=COALESCE(excluded.opening_deaths, player_map_stats.opening_deaths),
                        multi_kills=COALESCE(excluded.multi_kills, player_map_stats.multi_kills),
                        clutches_won=COALESCE(excluded.clutches_won, player_map_stats.clutches_won),
                        adr=excluded.adr,
                        kast_pct=excluded.kast_pct,
                        rating=excluded.rating,
                        is_captain=COALESCE(excluded.is_captain, player_map_stats.is_captain),
                        is_awp=COALESCE(excluded.is_awp, player_map_stats.is_awp)
                """, (
                    s.map_stats_id, s.match_id, s.team_id, s.player_id, s.player_name, s.kills, s.deaths, s.assists,
                    s.headshot_kills, s.flash_assists, s.opening_kills, s.opening_deaths, s.multi_kills, s.clutches_won,
                    s.adr, s.kast_pct, s.rating, s.is_captain, s.is_awp
                ))
                self.save_player_conn(conn, Player(player_id=s.player_id, nickname=s.player_name))
