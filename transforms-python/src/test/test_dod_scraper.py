from stratum.core.clients.dod import parse_article

ARTICLE_HTML = """
<html><body><div class="body">
<p>June 5, 2026</p>
<p>NAVY</p>
<p>General Dynamics Electric Boat Corp., Groton, Connecticut, is awarded a
$517,255,000 cost-plus-incentive-fee modification to previously awarded contract
N00024-25-C-2100 for Virginia-class submarine lead yard support and development
studies, including towed array integration and undersea warfare systems engineering
work expected to be completed by March 2028. Naval Sea Systems Command, Washington
Navy Yard, Washington, D.C., is the contracting activity.</p>
<p>AIR FORCE</p>
<p>Raytheon Co., Tucson, Arizona, has been awarded a $96,000,000 firm-fixed-price
contract for production of hypersonic attack cruise missile test articles and
associated scramjet propulsion hardware, with work performed across multiple
locations and expected completion in 2027. The Air Force Life Cycle Management
Center, Eglin Air Force Base, Florida, is the contracting activity.</p>
<p>Small print: checks and images.</p>
</div></body></html>
"""


def test_parse_article_extracts_contracts():
    rows = list(parse_article(ARTICLE_HTML, "https://www.defense.gov/x"))
    assert len(rows) == 2

    navy, af = rows
    assert navy["contractor_name"].startswith("General Dynamics Electric Boat")
    assert navy["contract_value_usd"] == 517_255_000
    assert navy["contracting_command"] == "Navy"
    assert "contracting activity" in navy["contracting_activity"].lower()
    assert navy["announcement_date_text"] == "June 5, 2026"

    assert af["contractor_name"].startswith("Raytheon")
    assert af["contract_value_usd"] == 96_000_000
    assert af["contracting_command"] == "Air Force"
    assert af["contract_id"] != navy["contract_id"]
