import re
from typing import Optional, Tuple
from bs4 import BeautifulSoup
from src.graph.objects import Event

MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12
}

class EventsParser:
    """Parses raw HLTV event HTML pages into Event graph objects."""

    @staticmethod
    def parse_prize_usd(prize_str: Optional[str]) -> int:
        if not prize_str:
            return 0
        digits = re.sub(r'[^\d]', '', prize_str)
        if digits.isdigit():
            return int(digits)
        return 0

    @staticmethod
    def determine_event_tier(name: str, is_lan: Optional[bool], prize_usd: int) -> str:
        name_lower = name.lower()
        
        # Tier 1: Major, RMRs, Katowice, Cologne, EPL, BLAST Finals, EWC, or Prize >= $250,000
        if any(k in name_lower for k in ["major", "iem katowice", "iem cologne", "esl pro league", "esports world cup", "blast premier final", "blast.tv major"]):
            return "Tier 1"
        if prize_usd >= 250000:
            return "Tier 1"
            
        # Qualifiers
        if "qualifier" in name_lower or "open qualifier" in name_lower or "closed qualifier" in name_lower:
            return "Qualifier"
            
        # Tier 2: Prize >= $50,000 or LAN events with decent prize
        if prize_usd >= 50000 or (is_lan and prize_usd >= 20000):
            return "Tier 2"
            
        return "Tier 3"

    @staticmethod
    def parse_date_range(text: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
        if not text:
            return None, None
        clean = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", text).strip()

        # Pattern 3: Month Day Year - Month Day Year (e.g. Nov 28 2024 - Dec 1 2024)
        m3 = re.search(r"([A-Za-z]{3})\s+(\d+)\s+(20\d{2})\s*-\s*([A-Za-z]{3})\s+(\d+)\s+(20\d{2})", clean)
        if m3:
            m1_m, m1_d, y1, m2_m, m2_d, y2 = m3.groups()
            return f"{int(y1):04d}-{MONTHS[m1_m]:02d}-{int(m1_d):02d}", f"{int(y2):04d}-{MONTHS[m2_m]:02d}-{int(m2_d):02d}"

        # Pattern 1: Month Day - Month Day Year (e.g. Aug 25 - Sep 5 2025)
        m1 = re.search(r"([A-Za-z]{3})\s+(\d+)\s*-\s*([A-Za-z]{3})\s+(\d+)\s+(20\d{2})", clean)
        if m1:
            m1_m, m1_d, m2_m, m2_d, y = m1.groups()
            return f"{int(y):04d}-{MONTHS[m1_m]:02d}-{int(m1_d):02d}", f"{int(y):04d}-{MONTHS[m2_m]:02d}-{int(m2_d):02d}"

        # Pattern 2: Month Day - Day Year (e.g. Aug 5 - 7 2024)
        m2 = re.search(r"([A-Za-z]{3})\s+(\d+)\s*-\s*(\d+)\s+(20\d{2})", clean)
        if m2:
            m_m, m1_d, m2_d, y = m2.groups()
            return f"{int(y):04d}-{MONTHS[m_m]:02d}-{int(m1_d):02d}", f"{int(y):04d}-{MONTHS[m_m]:02d}-{int(m2_d):02d}"

        # Pattern 4: Single date Month Day Year (e.g. Dec 28 2024)
        m4 = re.search(r"([A-Za-z]{3})\s+(\d+)\s+(20\d{2})", clean)
        if m4:
            m_m, m_d, y = m4.groups()
            dt = f"{int(y):04d}-{MONTHS[m_m]:02d}-{int(m_d):02d}"
            return dt, dt

        return None, None

    @classmethod
    def parse_event_html(cls, html_content: str, event_id: int) -> Optional[Event]:
        soup = BeautifulSoup(html_content, "lxml")

        title_elem = soup.find("h1", class_="event-hub-title") or soup.find("h1") or soup.find("div", class_="event-name")
        if not title_elem:
            return None
        event_name = title_elem.text.strip()

        # Flag parent text (location & LAN vs Online)
        flag = soup.find("img", class_="flag")
        location_text = flag.parent.text.strip() if flag and flag.parent else None

        is_lan = None
        location = None

        if location_text:
            if "(Online)" in location_text or "Online" in location_text:
                is_lan = False
                location = location_text.replace("(Online)", "").strip()
            else:
                is_lan = True
                location = location_text

        # Prize pool
        prize_elem = soup.find("td", class_="prizepool") or soup.find("div", class_="prizepool")
        prize_pool = prize_elem.text.strip() if prize_elem else None

        if not prize_pool:
            for tr in soup.find_all("tr"):
                txt = tr.text.strip()
                if "prize" in txt.lower() and "$" in txt:
                    m_p = re.search(r'\$[\d,]+', txt)
                    if m_p:
                        prize_pool = m_p.group(0)
                        break

        # Dates
        raw_date_str = None
        for text in [td.text.strip() for td in soup.find_all("td") if td.text.strip()]:
            if re.search(r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b', text) and ("-" in text or re.search(r'20\d{2}', text)):
                if not raw_date_str:
                    raw_date_str = text
                    break

        start_date, end_date = cls.parse_date_range(raw_date_str)
        prize_usd = cls.parse_prize_usd(prize_pool)
        event_tier = cls.determine_event_tier(event_name, is_lan, prize_usd)

        return Event(
            event_id=event_id,
            name=event_name,
            date_range_str=raw_date_str,
            start_date=start_date,
            end_date=end_date,
            location=location,
            prize_pool=prize_pool,
            prize_pool_usd=prize_usd,
            is_lan=is_lan,
            event_type=event_tier,
            event_tier=event_tier
        )
