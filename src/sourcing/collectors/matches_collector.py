import logging
from pathlib import Path
from typing import List, Dict, Any, Set, Tuple, Optional
from src.sourcing.client import HLTVClient
from src.sourcing.parsers.matches_parser import MatchesParser
from src.db.storage import Storage

logger = logging.getLogger(__name__)

class MatchesCollector:
    def __init__(self, client: HLTVClient, storage: Storage):
        self.client = client
        self.storage = storage

    def collect_matches(
        self,
        matches_metadata: List[Dict[str, Any]],
        cohort_team_ids: Optional[Set[int]] = None
    ) -> Tuple[Set[int], Set[int]]:
        """
        Fetches match pages for matches in matches_metadata.
        If cohort_team_ids is provided, only saves matches and collects map stats
        for matches involving at least one cohort team.
        Returns tuple of (discovered_event_ids, discovered_map_stats_ids).
        """
        discovered_event_ids: Set[int] = set()
        discovered_map_stats_ids: Set[int] = set()

        total = len(matches_metadata)
        logger.info(f"Starting match collection for {total} matches (Cohort filter active: {cohort_team_ids is not None})...")

        cohort_count = 0
        skipped_count = 0

        for idx, meta in enumerate(matches_metadata, start=1):
            match_id = meta["match_id"]
            url = meta.get("url", f"https://www.hltv.org/matches/{match_id}/match")
            cache_path = Path(f"data/raw/matches/{match_id}.html")

            try:
                html = self.client.get_html(url, cache_path)
                parsed_res = MatchesParser.parse_match_html(html, match_id=match_id)
                if parsed_res:
                    match_obj, map_stats_ids = parsed_res

                    # Filter by cohort if provided
                    if cohort_team_ids is not None:
                        is_cohort = (match_obj.team1_id in cohort_team_ids) or (match_obj.team2_id in cohort_team_ids)
                        if not is_cohort:
                            skipped_count += 1
                            continue

                    cohort_count += 1
                    self.storage.save_match(match_obj)

                    if match_obj.event_id:
                        discovered_event_ids.add(match_obj.event_id)
                    for ms_id in map_stats_ids:
                        discovered_map_stats_ids.add(ms_id)

                    if idx % 100 == 0 or idx == total:
                        logger.info(f"Processed {idx}/{total} matches (Cohort matches: {cohort_count}, Skipped non-cohort: {skipped_count})")
                else:
                    logger.warning(f"Could not parse match #{match_id}")
            except Exception as e:
                logger.error(f"Error processing match #{match_id}: {e}")

        logger.info(f"Match collection complete. Saved {cohort_count} cohort matches. Discovered {len(discovered_event_ids)} events and {len(discovered_map_stats_ids)} map stats pages.")
        return discovered_event_ids, discovered_map_stats_ids
