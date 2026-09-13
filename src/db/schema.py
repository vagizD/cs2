CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS team (
    team_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    logo_url TEXT,
    country_name TEXT
);

CREATE TABLE IF NOT EXISTS player (
    player_id INTEGER PRIMARY KEY,
    nickname TEXT NOT NULL,
    real_name TEXT,
    country_name TEXT
);

CREATE TABLE IF NOT EXISTS ranking_snapshot (
    snapshot_date TEXT NOT NULL,
    rank INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    team_name TEXT NOT NULL,
    points INTEGER NOT NULL,
    player_id1 INTEGER,
    player_id2 INTEGER,
    player_id3 INTEGER,
    player_id4 INTEGER,
    player_id5 INTEGER,
    PRIMARY KEY (snapshot_date, team_id)
);

CREATE TABLE IF NOT EXISTS event (
    event_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    date_range_str TEXT,
    start_date TEXT,
    end_date TEXT,
    location TEXT,
    prize_pool TEXT,
    prize_pool_usd INTEGER,
    is_lan INTEGER,
    event_type TEXT,
    event_tier TEXT
);

CREATE TABLE IF NOT EXISTS match (
    match_id INTEGER PRIMARY KEY,
    event_id INTEGER,
    datetime_utc TEXT,
    team1_id INTEGER NOT NULL,
    team1_name TEXT NOT NULL,
    team2_id INTEGER NOT NULL,
    team2_name TEXT NOT NULL,
    team1_score INTEGER,
    team2_score INTEGER,
    format TEXT,
    maps_played TEXT,
    lineup1_player_ids TEXT,
    lineup2_player_ids TEXT
);

CREATE TABLE IF NOT EXISTS map_result (
    map_stats_id INTEGER PRIMARY KEY,
    match_id INTEGER NOT NULL,
    map_name TEXT NOT NULL,
    team1_id INTEGER NOT NULL,
    team2_id INTEGER NOT NULL,
    team1_score INTEGER NOT NULL,
    team2_score INTEGER NOT NULL,
    overtime INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS player_map_stats (
    map_stats_id INTEGER NOT NULL,
    match_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    player_name TEXT NOT NULL,
    kills INTEGER NOT NULL,
    deaths INTEGER NOT NULL,
    assists INTEGER NOT NULL,
    headshot_kills INTEGER,
    flash_assists INTEGER,
    opening_kills INTEGER,
    opening_deaths INTEGER,
    multi_kills INTEGER,
    clutches_won INTEGER,
    adr REAL,
    kast_pct REAL,
    rating REAL,
    is_captain INTEGER DEFAULT 0,
    is_awp INTEGER DEFAULT 0,
    PRIMARY KEY (map_stats_id, player_id)
);
"""
