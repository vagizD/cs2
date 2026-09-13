import datetime
import logging
from pathlib import Path
from typing import List, Set
from src.sourcing.client import HLTVClient
from src.sourcing.parsers.rankings_parser import RankingsParser
from src.db.storage import Storage

logger = logging.getLogger(__name__)

class RankingsCollector:
    def __init__(self, client: HLTVClient, storage: Storage):
        self.client = client
        self.storage = storage

    @staticmethod
    def get_monday_dates(start_year: int = 2024, end_date: datetime.date = None) -> List[datetime.date]:
        if end_date is None:
            end_date = datetime.date.today()

        # Find first Monday of start_year (or 2024-01-01 if it's a Monday)
        d = datetime.date(start_year, 1, 1)
        while d.weekday() != 0:  # 0 is Monday
            d += datetime.timedelta(days=1)

        mondays = []
        while d <= end_date:
            mondays.append(d)
            d += datetime.timedelta(days=7)
        return mondays

    def collect_rankings(self, start_year: int = 2024) -> Set[int]:
        """
        Collects all weekly rankings from start_year to present.
        Saves raw HTML files, parses them offline into DB, and returns set of cohort team IDs.
        """
        mondays = self.get_monday_dates(start_year=start_year)
        logger.info(f"Collecting ranking snapshots for {len(mondays)} weeks starting from {start_year}...")

        month_names = [
            "january", "february", "march", "april", "may", "june",
            "july", "august", "september", "october", "november", "december"
        ]

        for m_date in mondays:
            date_str = m_date.strftime("%Y-%m-%d")
            month_str = month_names[m_date.month - 1]
            day_str = str(m_date.day)  # no leading zero
            url = f"https://www.hltv.org/ranking/teams/{m_date.year}/{month_str}/{day_str}"
            cache_path = Path(f"data/raw/rankings/{date_str}.html")

            try:
                html = self.client.get_html(url, cache_path)
                snapshots = RankingsParser.parse_ranking_html(html, snapshot_date=date_str)
                if snapshots:
                    self.storage.save_ranking_snapshots(snapshots)
                    logger.info(f"Saved {len(snapshots)} team rankings for snapshot {date_str}")
                else:
                    logger.warning(f"No ranking snapshots parsed from {date_str}")
            except Exception as e:
                logger.error(f"Error processing ranking snapshot {date_str}: {e}")

        cohort_team_ids = self.storage.get_cohort_team_ids(max_rank=30)
        logger.info(f"Total dynamic top-30 cohort team count: {len(cohort_team_ids)}")
        return cohort_team_ids
