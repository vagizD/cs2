-- TEMP indexes keep bounded lookbacks indexed without modifying the snapshot.
CREATE TEMP TABLE team_match_history AS
SELECT match_id, team1_id AS team_id, datetime_utc, team1_score > team2_score AS won
FROM finalized_match
UNION ALL
SELECT match_id, team2_id, datetime_utc, team2_score > team1_score
FROM finalized_match;

CREATE INDEX temp.team_match_time
    ON team_match_history (team_id, datetime_utc, match_id, won);

CREATE TEMP TABLE team_ranking_history (
    team_id INTEGER NOT NULL,
    snapshot_date TEXT NOT NULL,
    rank INTEGER NOT NULL,
    points INTEGER NOT NULL,
    PRIMARY KEY (team_id, snapshot_date)
) WITHOUT ROWID;

INSERT INTO team_ranking_history
SELECT team_id, snapshot_date, rank, points FROM valid_ranking;
