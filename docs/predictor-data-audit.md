# Predictor data audit

The bundled HLTV snapshot passed SQLite `PRAGMA integrity_check` at the start of development. Its SHA-256 is `9dc4989cba70c3d78ca650925fb7db625004784b8a6d9859d9818a05abf5fa00`.

| Table | Rows |
| --- | ---: |
| team | 1,580 |
| player | 4,652 |
| ranking_snapshot | 34,826 |
| event | 1,250 |
| match | 17,821 |
| map_result | 25,774 |
| player_map_stats | 257,777 |

All match rows have both team IDs in `team` and a second-resolution UTC timestamp. There are 13,091 distinct match timestamps from 2024-01-09 13:10:00 through 2026-09-08 13:45:00 UTC. The ranking dates span 2024-01-01 through 2026-09-07. They have no publication time, so the predictor only uses snapshots dated before the match day in UTC. The 156 matches outside their event's recorded date range and one event with missing dates make event dates unsuitable as substitutes for match timestamps.

The database builder recalculates scores from available maps. Consequently, 265 rows have tied scores, and 887 non-tied rows have a winning score inconsistent with the recorded series format, including 861 BO3 rows with a 1–0 score. Training labels and form features accept only integer scores consistent with a completed BO1, BO3, or BO5. This leaves 16,669 matches. Format is an outcome quality check. The predictor uses team and form features, so it can also serve a matchup before a format is known. The source has match start times but no reliable completion or result publication times. Earlier matches on overlapping schedules may still have been in progress at the prediction time.

The match and stats parsers return four and three values respectively, including when parsing fails. The offline database builder already uses those contracts. The online collectors now unpack the intended values and skip a missing match cleanly. Results pages are cached by calendar month and offset, so rerunning the original collector can read a stale partial month. The predictor reads the bundled or downloaded SQLite snapshot.
