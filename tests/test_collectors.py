from unittest.mock import Mock

from src.sourcing.collectors.matches_collector import MatchesCollector
from src.sourcing.collectors.stats_collector import StatsCollector

MATCH_HTML = """
<div class="teamsBox">
  <div class="team"><a href="/team/9565/vitality"><div class="teamName">Vitality</div></a></div>
  <div class="team"><a href="/team/4494/mouz"><div class="teamName">MOUZ</div></a></div>
</div>
<a href="/events/100/test">Event</a>
<a href="/stats/matches/mapstatsid/200/test">Stats</a>
"""

STATS_HTML = """
<a href="/matches/10/test">Match</a>
<div class="match-info-box">
  <div class="small-text">Map</div>Mirage
  <div class="team-left"><a href="/stats/teams/9565/vitality">Vitality</a><div class="won">13</div></div>
  <div class="team-right"><a href="/stats/teams/4494/mouz">MOUZ</a><div class="lost">7</div></div>
</div>
"""


def test_match_collector_uses_parser_contract():
    client = Mock()
    client.get_html.side_effect = [MATCH_HTML, "<html></html>"]
    storage = Mock()
    assert MatchesCollector(client, storage).collect_matches(
        [{"match_id": 10}, {"match_id": 11}]
    ) == ({100}, {200})
    storage.save_match.assert_called_once()
    assert storage.save_match.call_args.args[0].match_id == 10


def test_stats_collector_uses_parser_contract():
    client = Mock()
    client.get_html.side_effect = [STATS_HTML, "<html></html>"]
    storage = Mock()
    StatsCollector(client, storage).collect_stats({200, 201})
    storage.save_map_result.assert_called_once()
    assert storage.save_map_result.call_args.args[0].map_stats_id == 200
