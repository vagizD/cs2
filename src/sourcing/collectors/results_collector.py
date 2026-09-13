import datetime
import logging
from pathlib import Path
from typing import List, Dict, Any, Set, Optional
from src.sourcing.client import HLTVClient
from src.sourcing.parsers.results_parser import ResultsParser

logger = logging.getLogger(__name__)

class ResultsCollector:
    def __init__(self, client: HLTVClient):
        self.client = client

    def collect_results_for_month(
        self,
        year: int,
        month: int,
        cohort_team_names: Optional[Set[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Collects result listing pages for a given year and month.
        Paginates offset=0, 100, 200... until no more results.
        If cohort_team_names is provided, only keeps matches where team1 or team2 matches a cohort team name.
        """
        start_date = datetime.date(year, month, 1)
        if month == 12:
            end_date = datetime.date(year + 1, 1, 1) - datetime.timedelta(days=1)
        else:
            end_date = datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)

        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        month_matches = []
        offset = 0

        while True:
            url = f"https://www.hltv.org/results?startDate={start_str}&endDate={end_str}&offset={offset}"
            cache_path = Path(f"data/raw/results/{year}_{month:02d}_offset_{offset}.html")

            try:
                html = self.client.get_html(url, cache_path)
                page_results = ResultsParser.parse_results_html(html)
                if not page_results:
                    logger.info(f"No more results for {year}-{month:02d} at offset {offset}")
                    break

                # Apply cohort filter if provided
                if cohort_team_names:
                    filtered_page = []
                    for res in page_results:
                        t1 = res["team1_name"].strip().lower()
                        t2 = res["team2_name"].strip().lower()
                        if t1 in cohort_team_names or t2 in cohort_team_names:
                            filtered_page.append(res)
                    month_matches.extend(filtered_page)
                else:
                    month_matches.extend(page_results)

                logger.info(f"Collected {len(page_results)} matches for {year}-{month:02d} offset {offset} (Kept cohort: {len(month_matches)})")

                if len(page_results) < 100:
                    break

                offset += 100
            except Exception as e:
                logger.error(f"Error fetching results for {year}-{month:02d} offset {offset}: {e}")
                break

        return month_matches

    def collect_all_results(
        self,
        start_year: int = 2024,
        cohort_team_names: Optional[Set[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Collects match results across all months from start_year to current month.
        Returns deduplicated list of match metadata dictionaries.
        """
        current_date = datetime.date.today()
        all_matches = []
        seen_match_ids: Set[int] = set()

        for y in range(start_year, current_date.year + 1):
            max_m = current_date.month if y == current_date.year else 12
            for m in range(1, max_m + 1):
                m_matches = self.collect_results_for_month(y, m, cohort_team_names=cohort_team_names)
                for match in m_matches:
                    m_id = match["match_id"]
                    if m_id not in seen_match_ids:
                        seen_match_ids.add(m_id)
                        all_matches.append(match)

        logger.info(f"Total deduplicated matches discovered: {len(all_matches)} (Cohort filter active: {cohort_team_names is not None})")
        return all_matches
