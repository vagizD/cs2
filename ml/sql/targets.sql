CREATE TEMP TABLE ml_targets (
    example_id INTEGER PRIMARY KEY,
    team_a_won INTEGER NOT NULL CHECK (team_a_won IN (0, 1))
);

INSERT INTO ml_targets
SELECT match_id,
       CASE WHEN team1_id < team2_id THEN team1_score > team2_score
            ELSE team2_score > team1_score END
FROM finalized_match;
