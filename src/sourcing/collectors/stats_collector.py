import logging
from pathlib import Path
from typing import Set
from src.sourcing.client import HLTVClient
from src.sourcing.parsers.stats_parser import StatsParser
from src.db.storage import Storage

logger = logging.getLogger(__name__)

class StatsCollector:
    def __init__(self, client: HLTVClient, storage: Storage):
        self.client = client
        self.storage = storage

    def collect_stats(self, map_stats_ids: Set[int]):
        """
        Fetches map stats pages for all given map_stats_ids.
        Saves MapResult and PlayerMapStats objects to storage.
        """
        total = len(map_stats_ids)
        logger.info(f"Starting map stats collection for {total} pages...")

        for idx, ms_id in enumerate(sorted(map_stats_ids), start=1):
            url = f"https://www.hltv.org/stats/matches/mapstatsid/{ms_id}/stats"
            cache_path = Path(f"data/raw/stats/{ms_id}.html")

            try:
                html = self.client.get_html(url, cache_path)
                map_res, player_stats = StatsParser.parse_map_stats_html(html, map_stats_id=ms_id)

                if map_res:
                    self.storage.save_map_result(map_res)
                if player_stats:
                    self.storage.save_player_map_stats(player_stats)

                if idx % 10 == 0 or idx == total:
                    logger.info(f"Processed stats {idx}/{total} (MapStats #{ms_id})")
            except Exception as e:
                logger.error(f"Error processing stats #{ms_id}: {e}")

        logger.info("Map stats collection complete.")
