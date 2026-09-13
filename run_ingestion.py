import argparse
import sys
import logging
from pathlib import Path

# Setup logging
log_dir = Path("data/logs")
log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("data/logs/ingestion.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("run_ingestion")

from src.sourcing.client import HLTVClient
from src.db.storage import Storage
from src.sourcing.collectors.rankings_collector import RankingsCollector
from src.sourcing.collectors.results_collector import ResultsCollector
from src.sourcing.collectors.matches_collector import MatchesCollector
from src.sourcing.collectors.events_collector import EventsCollector
from src.sourcing.collectors.stats_collector import StatsCollector

def run_pipeline(sample_mode: bool = False, filter_cohort: bool = True, db_path: str = "data/processed/hltv_database.db"):
    logger.info("==================================================================")
    logger.info(f"Starting HLTV Data Retrieval Pipeline (Sample Mode: {sample_mode}, Filter Cohort: {filter_cohort})")
    logger.info("==================================================================")

    storage = Storage(db_path=db_path)
    client = HLTVClient()

    # Step 1: Rankings Discovery
    logger.info("\n--- STEP 1: Weekly Ranking Snapshots & Dynamic Cohort Discovery ---")
    rankings_collector = RankingsCollector(client, storage)
    if sample_mode:
        mondays = rankings_collector.get_monday_dates(2024)[:2]
        month_names = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
        from src.sourcing.parsers.rankings_parser import RankingsParser
        for m in mondays:
            date_str = m.strftime("%Y-%m-%d")
            url = f"https://www.hltv.org/ranking/teams/{m.year}/{month_names[m.month-1]}/{m.day}"
            html = client.get_html(url, Path(f"data/raw/rankings/{date_str}.html"))
            snaps = RankingsParser.parse_ranking_html(html, date_str)
            storage.save_ranking_snapshots(snaps)
        cohort_team_ids = storage.get_cohort_team_ids(30)
        cohort_team_names = storage.get_cohort_team_names(30)
    else:
        cohort_team_ids = rankings_collector.collect_rankings(start_year=2024)
        cohort_team_names = storage.get_cohort_team_names(30)

    logger.info(f"Step 1 Complete. Dynamic Top 30 Cohort count: {len(cohort_team_ids)} teams.")

    # Step 2: Match Results Discovery
    logger.info("\n--- STEP 2: Match Results Discovery (2024 - Present) ---")
    results_collector = ResultsCollector(client)
    target_team_names = cohort_team_names if filter_cohort else None

    if sample_mode:
        all_results = results_collector.collect_results_for_month(2024, 1, cohort_team_names=target_team_names)[:10]
    else:
        all_results = results_collector.collect_all_results(start_year=2024, cohort_team_names=target_team_names)

    logger.info(f"Step 2 Complete. Total matches discovered: {len(all_results)}")

    # Step 3: Match Details & Lineup Extraction
    logger.info("\n--- STEP 3: Match Page Ingestion & Lineups ---")
    matches_collector = MatchesCollector(client, storage)
    if sample_mode:
        all_results = all_results[:5]

    target_cohort_ids = cohort_team_ids if filter_cohort else None
    event_ids, map_stats_ids = matches_collector.collect_matches(all_results, cohort_team_ids=target_cohort_ids)
    logger.info(f"Step 3 Complete. Discovered {len(event_ids)} events and {len(map_stats_ids)} map stats pages.")

    # Step 4: Event Metadata Ingestion
    logger.info("\n--- STEP 4: Event Metadata Ingestion ---")
    events_collector = EventsCollector(client, storage)
    events_collector.collect_events(event_ids)
    logger.info("Step 4 Complete.")

    # Step 5: Map & Player Statistics Ingestion
    logger.info("\n--- STEP 5: Map & Player Statistics Ingestion ---")
    stats_collector = StatsCollector(client, storage)
    stats_collector.collect_stats(map_stats_ids)
    logger.info("Step 5 Complete.")

    logger.info("==================================================================")
    logger.info("HLTV Data Retrieval Pipeline Completed Successfully!")
    logger.info("==================================================================")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run HLTV Data Retrieval Pipeline")
    parser.add_argument("--sample", action="store_true", help="Run in sample/dry-run mode for quick testing")
    parser.add_argument("--all-matches", action="store_true", help="Ingest all matches, including non-cohort teams")
    parser.add_argument("--db", type=str, default="data/processed/hltv_database.db", help="Path to SQLite database")

    args = parser.parse_args()
    run_pipeline(sample_mode=args.sample, filter_cohort=not args.all_matches, db_path=args.db)
