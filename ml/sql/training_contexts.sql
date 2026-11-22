INSERT INTO prediction_context (example_id, team_a_id, team_b_id, as_of_utc)
SELECT match_id, min(team1_id, team2_id), max(team1_id, team2_id), datetime_utc
FROM match_metadata;
