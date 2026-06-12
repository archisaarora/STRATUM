"""GDELT DOC corroboration client — query construction + API contract."""
from stratum.core.clients.gdelt_doc import build_query, search_articles
from test.test_alternate_sources import FakeSession


def test_query_targets_country_and_domain_terms():
    q = build_query("Iran", "propellants_and_explosives")
    assert q.startswith('"Iran" ')
    assert "propellant" in q and " OR " in q
    # unknown domains degrade to a readable phrase
    assert build_query("China", "weird_new_domain") == '"China" ("weird new domain")'


def test_search_articles_params_and_outlet_dedupe():
    session = FakeSession([{
        "articles": [
            {"title": "Iran ramps up propellant imports", "url": "http://a/1",
             "domain": "reuters.com", "seendate": "20260601T120000Z",
             "language": "English"},
            {"title": "duplicate outlet story", "url": "http://a/2",
             "domain": "reuters.com", "seendate": "20260601T130000Z",
             "language": "English"},
            {"title": "Analyse: l'Iran et les missiles", "url": "http://b/1",
             "domain": "lemonde.fr", "seendate": "20260530T080000Z",
             "language": "French"},
        ]
    }])
    arts = search_articles(session, "https://api.gdeltproject.org",
                           country_name="Iran",
                           domain="propellants_and_explosives")
    method, url, kwargs = session.calls[0]
    assert url.endswith("/api/v2/doc/doc")
    p = kwargs["params"]
    assert p["mode"] == "ArtList" and p["format"] == "json"
    assert p["timespan"] == "12m"
    assert '"Iran"' in p["query"]

    assert len(arts) == 2  # reuters deduped to one
    assert arts[0]["date"] == "2026-06-01"
    assert arts[1]["source"] == "lemonde.fr"


def test_non_json_response_returns_empty():
    class TextResponse:
        status_code, headers, text = 200, {}, "Your query was too short"

        def json(self):
            raise ValueError("no json")

        def raise_for_status(self):
            pass

    class TextSession:
        def request(self, *a, **k):
            return TextResponse()

    assert search_articles(TextSession(), country_name="Iran",
                           domain="nuclear") == []
