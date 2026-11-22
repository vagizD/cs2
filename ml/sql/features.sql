WITH context_teams AS (
    SELECT example_id, as_of_utc, team_a_id AS team_id, 'a' AS side
    FROM prediction_context
    UNION ALL
    SELECT example_id, as_of_utc, team_b_id, 'b'
    FROM prediction_context
),
lookbacks AS (
    SELECT *, datetime(as_of_utc, '-' || :short_days || ' days') AS short_start,
              datetime(as_of_utc, '-' || :long_days || ' days') AS long_start
    FROM context_teams
),
team_features AS MATERIALIZED (
    SELECT c.example_id, c.side, r.rank, r.points,
           avg(h.won) FILTER (WHERE h.datetime_utc >= c.short_start) AS win_rate_short,
           count(h.match_id) FILTER (WHERE h.datetime_utc >= c.short_start) AS match_count_short,
           avg(h.won) AS win_rate_long,
           count(h.match_id) AS match_count_long
    FROM lookbacks AS c
    LEFT JOIN team_ranking_history AS r
      ON r.team_id = c.team_id
     AND r.snapshot_date = (
         SELECT snapshot_date
         FROM team_ranking_history
         WHERE team_id = c.team_id AND snapshot_date < date(c.as_of_utc)
         ORDER BY snapshot_date DESC
         LIMIT 1
     )
    LEFT JOIN team_match_history AS h
      ON h.team_id = c.team_id
     AND h.datetime_utc >= c.long_start AND h.datetime_utc < c.as_of_utc
     AND h.match_id <> c.example_id
    GROUP BY c.example_id, c.side, r.rank, r.points
)
SELECT c.example_id, c.team_a_id, c.team_b_id, c.as_of_utc,
       a.rank - b.rank AS rank_diff,
       a.points - b.points AS points_diff,
       a.win_rate_short - b.win_rate_short AS win_rate_short_diff,
       a.match_count_short - b.match_count_short AS match_count_short_diff,
       a.win_rate_long - b.win_rate_long AS win_rate_long_diff,
       a.match_count_long - b.match_count_long AS match_count_long_diff
FROM prediction_context AS c
JOIN team_features AS a ON a.example_id = c.example_id AND a.side = 'a'
JOIN team_features AS b ON b.example_id = c.example_id AND b.side = 'b'
ORDER BY c.as_of_utc, c.example_id;
