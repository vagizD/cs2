# HLTV Ingestion Execution Progress (Steps 1 – 5)

## Pipeline Status: COMPLETED (100%)

### Final Database Statistics (`data/processed/hltv_database.db`):
- **`player_map_stats`**: **257,867 rows** (Individual player performance metrics: K/D/A, ADR, KAST %, Rating)
- **`map_result`**: **25,784 rows** (Individual map scores, overtime flags)
- **`match`**: **17,821 rows** (Matches, BO1/BO3/BO5 format, UTC timestamp, lineups)
- **`player`**: **3,264 rows** (Unique players catalog)
- **`team`**: **1,580 rows** (Unique teams catalog)
- **`ranking_snapshot`**: **34,826 rows** (Weekly Monday Top-30 lineups & points from 2024 to present)

---

### Core Pipeline Modules Completed & Operational:
1. **Graph Data Models (`src/graph/objects/`)**:
   - `Team`, `Player`, `RankingSnapshot`, `Event`, `Match`, `MapResult`, `PlayerMapStats`

2. **Cloudflare Anti-Bot Hybrid Downloader (`src/sourcing/client.py`)**:
   - `nodriver` Cloudflare Turnstile token resolution + `curl_cffi` HTTP fetching.
   - Saves raw HTML files to `data/raw/<category>/`.

3. **Offline Parsers (`src/sourcing/parsers/`)**:
   - `rankings_parser.py`: Extracts Top 30 / Top 50 team rankings & 5-player lineups.
   - `results_parser.py`: Discovers match IDs & event links.
   - `matches_parser.py`: Extracts match date/time, teams, scores, format, lineups, and map stats IDs.
   - `events_parser.py`: Extracts prize pool, dates, location, and LAN/Online status.
   - `stats_parser.py`: Extracts map scores, overtime status, and individual player metrics (K, D, A, ADR, KAST, Rating).

4. **SQLite Database Storage (`src/db/storage.py`)**:
   - Relational database populated in `data/processed/hltv_database.db`.

5. **Master Pipeline Runner (`run_ingestion.py`)**:
   - Completed execution across all 26,685 map stats pages.
