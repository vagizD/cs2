-- The source stores match start times as second-resolution UTC text.
CREATE TEMP VIEW match_metadata AS
SELECT match_id, team1_id, team2_id, datetime_utc
FROM main.match AS m
JOIN main.team AS t1 ON t1.team_id = m.team1_id
JOIN main.team AS t2 ON t2.team_id = m.team2_id
WHERE team1_id > 0 AND team2_id > 0 AND team1_id <> team2_id
  AND datetime(datetime_utc, '+0 seconds') = datetime_utc;

CREATE TEMP VIEW finalized_match AS
SELECT metadata.*, m.team1_score, m.team2_score
FROM match_metadata AS metadata
JOIN main.match AS m USING (match_id)
WHERE typeof(m.team1_score) = 'integer' AND typeof(m.team2_score) = 'integer'
  AND min(m.team1_score, m.team2_score) >= 0
  AND m.team1_score <> m.team2_score
  AND max(m.team1_score, m.team2_score) = CASE lower(m.format)
      WHEN 'bo1' THEN 1 WHEN 'bo3' THEN 2 WHEN 'bo5' THEN 3 END;

CREATE TEMP VIEW valid_ranking AS
SELECT snapshot_date, team_id, rank, points
FROM main.ranking_snapshot
JOIN main.team USING (team_id)
WHERE date(snapshot_date, '+0 days') = snapshot_date
  AND typeof(rank) = 'integer' AND rank > 0
  AND typeof(points) = 'integer' AND points >= 0;
