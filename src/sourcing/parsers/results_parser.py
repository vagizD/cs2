import re
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup

class ResultsParser:
    """Parses raw HLTV results listing HTML into match metadata dictionaries."""

    @staticmethod
    def parse_results_html(html_content: str) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html_content, "lxml")
        results = []

        all_res_divs = soup.find_all("div", class_="result-con")
        for div in all_res_divs:
            match_a = div.find("a", class_="a-reset")
            if not match_a or "href" not in match_a.attrs:
                continue

            href = match_a["href"]
            match_id_match = re.search(r'/matches/(\d+)/', href)
            if not match_id_match:
                continue
            match_id = int(match_id_match.group(1))

            # Unix timestamp
            timestamp_ms = div.get("data-zonedgrouping-entry-unix")
            timestamp = int(timestamp_ms) // 1000 if timestamp_ms and timestamp_ms.isdigit() else None

            # Team names
            t1_elem = div.find("div", class_="team1")
            t2_elem = div.find("div", class_="team2")
            team1_name = t1_elem.text.strip() if t1_elem else "Unknown"
            team2_name = t2_elem.text.strip() if t2_elem else "Unknown"

            # Event name
            event_span = div.find("span", class_="event-name")
            event_name = event_span.text.strip() if event_span else None

            results.append({
                "match_id": match_id,
                "url": f"https://www.hltv.org{href}",
                "timestamp": timestamp,
                "team1_name": team1_name,
                "team2_name": team2_name,
                "event_name": event_name,
            })

        return results
