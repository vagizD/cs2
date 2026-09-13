import logging
from pathlib import Path
from typing import Set
from src.sourcing.client import HLTVClient
from src.sourcing.parsers.events_parser import EventsParser
from src.db.storage import Storage

logger = logging.getLogger(__name__)

class EventsCollector:
    def __init__(self, client: HLTVClient, storage: Storage):
        self.client = client
        self.storage = storage

    def collect_events(self, event_ids: Set[int]):
        """
        Fetches event pages for all given event_ids.
        Saves Event objects to storage.
        """
        total = len(event_ids)
        logger.info(f"Starting event collection for {total} events...")

        for idx, event_id in enumerate(sorted(event_ids), start=1):
            url = f"https://www.hltv.org/events/{event_id}/event"
            cache_path = Path(f"data/raw/events/{event_id}.html")

            try:
                html = self.client.get_html(url, cache_path)
                event_obj = EventsParser.parse_event_html(html, event_id=event_id)
                if event_obj:
                    self.storage.save_event(event_obj)
                    if idx % 10 == 0 or idx == total:
                        logger.info(f"Processed event {idx}/{total} (Event #{event_id})")
                else:
                    logger.warning(f"Could not parse event #{event_id}")
            except Exception as e:
                logger.error(f"Error processing event #{event_id}: {e}")

        logger.info("Event collection complete.")
