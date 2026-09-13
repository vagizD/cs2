# HLTV Data Sources, Identity Model & Database Schemas (`plan/data/`)

## 1. Database Schema (`data/processed/hltv_database.db`)

The database consists of 7 core tables constructed from raw HTML pages:

### Core Tables

1. **`ranking_snapshot`**: Weekly HLTV Top 30 team rankings, points, and 5-player active lineup IDs.
2. **`event`**: Tournament metadata, including ISO `start_date`, `end_date`, raw `date_range_str`, `is_lan`, `event_type`, and standardized `event_tier` (`Tier 1`, `Tier 2`, `Tier 3`, `Qualifier`).
3. **`match`**: Match results, team IDs, UTC timestamps, format (`bo1`, `bo3`, `bo5`), standardized BO1 map scores (`1-0` or `0-1`), maps played, and player lineup IDs.
4. **`map_result`**: Individual map round scores, map names, and overtime indicators.
5. **`player_map_stats`**: Detailed per-map player performance metrics:
   - Basic stats: `kills`, `deaths`, `assists`, `adr`, `kast_pct`, `rating`
   - Combat stats: `headshot_kills`, `flash_assists`, `opening_kills`, `opening_deaths`, `multi_kills`, `clutches_won`
   - Role indicators: `is_captain`, `is_awp`
6. **`player`**: Player profiles containing `player_id`, `nickname`, `real_name` (e.g. `Usukhbayar Banzragch`), and `country_name` (e.g. `Mongolia`).
7. **`team`**: Team profiles containing `team_id`, `name`, `logo_url`, and `country_name`.

---

## 2. Identity & Lineage Model

- **Source Team**: `hltv_team_id` represents an organization/team page.
- **Observed Lineup (`lineup_id`)**: A SHA256 hash of a sorted set of 5 player IDs.
- **Competitive Lineage (`lineage_id`)**: Represents core player continuity across organization rebrands or team ID changes:
  - Retains lineage if $\ge 3$ of 5 players are retained from the previous snapshot/match.
  - Generates a new `lineage_id` if $< 3$ players are retained.
- **Permanent Change vs Stand-in**:
  - **Permanent Change**: Incoming player appears in consecutive weekly ranking snapshots or $\ge 3$ consecutive matches over multiple days.
  - **Stand-in**: Short-term substitution for 1–2 matches without ranking update.
