"""Generate SYNTHETIC provider profiles for privately held carriers (data/raw/<slug>_profile_synthetic.html).

Edge Logistics, First Star and BlueGrace Logistics are privately held and file nothing with the SEC. LaneRoom
needs a document per provider for the Researcher and Quant, so it uses illustrative profiles in the same
5-page layout as the Armada profile. EVERY figure and statement below is made up for the demo: none of it is
data from, or a claim about, the real companies with these names. Each page carries a "SYNTHETIC PROFILE" banner.

    python scripts/make_profiles.py          # writes the HTML
    # then print each HTML to PDF (the repo does this with headless Microsoft Edge on Windows):
    msedge --headless=new --no-pdf-header-footer --print-to-pdf=data/raw/<slug>_profile_synthetic.pdf <html>
"""
from __future__ import annotations

from html import escape
from pathlib import Path

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"

PROFILES = {
    "edge": {
        "name": "Edge Logistics", "legal": "Edge Logistics LLC",
        "type": "non-asset freight brokerage",
        "business": [
            "Edge Logistics is presented in this demo as a privately held, non-asset freight brokerage that arranges dry van, refrigerated and flatbed truckload capacity through contracted motor carriers.",
            "In this illustrative profile the brokerage has 18,000 active contracted carriers and 410 employees, of whom 300 work in carrier sales and customer service.",
            "Its carrier network can cover surge freight quickly, and it offers spot and contract truckload, partial truckload and LTL through partner carriers.",
            "Its ten largest shippers generated 41% of revenue in 2025 in this synthetic profile.",
            "It quotes tender acceptance of 90% on contracted lanes, supported by a digital load board and automated carrier matching.",
        ],
        "risks": [
            "Edge Logistics owns no tractors or trailers, so its service depends on third-party carriers, and its tender acceptance falls when the truckload market tightens.",
            "In the fourth quarter of 2025 its average purchased transportation cost per load rose 9% as spot rates increased during peak season.",
            "Customer concentration is a risk: the loss of one of its ten largest shippers could reduce revenue materially.",
            "The company is privately held and its financial statements are not audited by a registered public accounting firm or filed with the SEC.",
            "Brokers can face claims when a contracted carrier is involved in an accident, and cargo claims are recovered from carriers only after a delay.",
        ],
        "properties": [("Main office", "Office", "0"), ("Carrier sales office", "Office", "0"), ("Cross-dock (partner)", "Partner facility", "24")],
        "properties_note": "Edge Logistics operates no terminals or service centers of its own in this profile; partner carriers provide all equipment.",
        "fin": (("Revenue (in millions)", "$548.0", "$596.5"), ("Operating income (in millions)", "$9.3", "$12.5"),
                ("Operating ratio", "98.3%", "97.9%"), ("Net cash provided by operating activities (in millions)", "$13.4", "$17.8"),
                ("Active contracted carriers", "18,000", "16,500"), ("Loads brokered (in thousands)", "212", "224")),
        "summary": [
            "Revenue decreased 8.1% in 2025 as truckload spot rates stayed soft for most of the year, and operating income declined as purchased transportation costs rose in the fourth quarter.",
            "The brokerage reported an on-time delivery rate of 92.1% and a cargo claims ratio of 0.35% of revenue on contract lanes in 2025.",
            "Its average linehaul rate on dry van contract freight, excluding fuel surcharge, was $2.15 per mile in 2025.",
        ],
    },
    "firststar": {
        "name": "First Star", "legal": "First Star LLC",
        "type": "small asset-light carrier and 3PL",
        "business": [
            "First Star is presented in this demo as a privately held, asset-light carrier and third-party logistics provider that runs a small truckload fleet and brokers overflow freight.",
            "In this illustrative profile the company operates 140 company tractors and 420 dry van trailers and works with 3,100 contracted partner carriers.",
            "It offers regional truckload, LTL consolidation and expedited service, with a focus on Midwest origins.",
            "Its ten largest shippers generated 62% of revenue in 2025 in this synthetic profile, and its largest shipper generated 17%.",
            "It targets tender acceptance of 90% on contracted lanes and shares a monthly scorecard with each shipper.",
        ],
        "risks": [
            "First Star's small fleet limits its capacity in peak season: in the fourth quarter of 2025 partner carriers hauled 44% of its loads, compared with 29% earlier in the year.",
            "Customer concentration is high, so losing one large shipper could reduce revenue and lane density materially.",
            "The company is privately held and its financial statements are not audited by a registered public accounting firm or filed with the SEC.",
            "A shortage of qualified drivers could raise driver pay and leave tractors unseated.",
            "Its revolving credit facility of $12 million was $8 million drawn at year-end 2025, which may limit fleet growth.",
        ],
        "properties": [("Main terminal", "Terminal", "28"), ("Drop yard", "Drop yard", "0")],
        "properties_note": "First Star does not operate intermodal service in this profile; long-haul and West Coast freight is brokered to partner carriers.",
        "fin": (("Revenue (in millions)", "$96.4", "$88.1"), ("Operating income (in millions)", "$3.1", "$2.6"),
                ("Operating ratio", "96.8%", "97.0%"), ("Net cash provided by operating activities (in millions)", "$4.0", "$3.3"),
                ("Company tractors", "140", "128"), ("Loads hauled and brokered (in thousands)", "61", "57")),
        "summary": [
            "Revenue increased 9.4% in 2025 on new regional contract awards, and operating income rose as the fleet ran more loaded miles.",
            "The company reported an on-time delivery rate of 92.8% and a cargo claims ratio of 0.29% of revenue on contract lanes in 2025.",
            "Its average linehaul rate on dry van contract freight, excluding fuel surcharge, was $2.24 per mile in 2025.",
        ],
    },
    "bluegrace": {
        "name": "BlueGrace Logistics", "legal": "BlueGrace Logistics LLC",
        "type": "non-asset 3PL focused on LTL and managed transportation",
        "business": [
            "BlueGrace Logistics is presented in this demo as a privately held, non-asset third-party logistics provider focused on LTL brokerage, truckload brokerage and managed transportation for small and mid-size shippers.",
            "In this illustrative profile the company works with 9,500 contracted carriers, including contracts with national and regional LTL carriers, and has 780 employees.",
            "Its transportation management software rates and books LTL shipments across many carriers, which lets shippers compare price and transit time per shipment.",
            "Its ten largest shippers generated 22% of revenue in 2025 in this synthetic profile.",
            "It targets tender acceptance of 93% on contracted LTL lanes.",
        ],
        "risks": [
            "BlueGrace Logistics owns no trucks, so its LTL service quality depends on the carriers it books, and on-time performance varies by carrier.",
            "Price increases from national LTL carriers flow through to shippers with a lag, which can compress margins.",
            "The company is privately held and its financial statements are not audited by a registered public accounting firm or filed with the SEC.",
            "Cargo claims on brokered LTL freight are filed against the carrier, which can delay recovery for shippers.",
            "A cyber incident affecting its transportation management software could disrupt booking and tracking for many shippers at once.",
        ],
        "properties": [("Main office", "Office", "0"), ("Regional office", "Office", "0"), ("Regional office", "Office", "0")],
        "properties_note": "BlueGrace Logistics operates no terminals in this profile; LTL carriers' service centers handle all freight.",
        "fin": (("Revenue (in millions)", "$612.0", "$640.5"), ("Operating income (in millions)", "$14.6", "$16.0"),
                ("Operating ratio", "97.6%", "97.5%"), ("Net cash provided by operating activities (in millions)", "$20.3", "$22.0"),
                ("Contracted carriers", "9,500", "9,100"), ("Shipments managed (in thousands)", "1,180", "1,215")),
        "summary": [
            "Revenue decreased 4.4% in 2025 as LTL tonnage declined across the industry, while operating ratio was broadly flat.",
            "The company reported an on-time delivery rate of 93.1% and a cargo claims ratio of 0.38% of revenue across brokered LTL shipments in 2025.",
            "Its average LTL linehaul-equivalent rate was $5.02 per mile in 2025, below most asset-based national LTL carriers.",
        ],
    },
}

CSS = """body{font-family:Arial,Helvetica,sans-serif;font-size:11pt;line-height:1.45;margin:0 40px;color:#111}
.banner{border:2px solid #b00;color:#b00;padding:6px 10px;font-weight:bold;font-size:10pt;margin:14px 0}
h1{font-size:18pt} h2{font-size:14pt;margin-top:18px}
table{border-collapse:collapse;margin:8px 0} td,th{border:1px solid #999;padding:3px 8px;font-size:10pt}
.page{page-break-after:always}"""


def html(p: dict) -> str:
    short = (f'<div class="banner">SYNTHETIC PROFILE. Not an SEC filing and not data from {escape(p["legal"])}. '
             "Illustrative figures for the LaneRoom demo.</div>")
    full = (f'<div class="banner">SYNTHETIC PROFILE. Not an SEC filing. Illustrative data written by Team 24 for the '
            f'LaneRoom demo. It is not information from or about the real company {escape(p["legal"])}, and no figure '
            "in it is a real reported result.</div>")
    para = lambda items: "".join(f"<p>{escape(x)}</p>" for x in items)  # noqa: E731
    props = "".join(f"<tr><td>{escape(a)}</td><td>{escape(b)}</td><td>{escape(c)}</td></tr>" for a, b, c in p["properties"])
    fin = "".join(f"<tr><td>{escape(a)}</td><td>{escape(b)}</td><td>{escape(c)}</td></tr>" for a, b, c in p["fin"])
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{escape(p['name'])} carrier profile (SYNTHETIC)</title><style>{CSS}</style></head><body>
<div class="page">{full}
<h1>{escape(p['name'])}</h1>
<p>Carrier and 3PL profile prepared for shipper tender review, fiscal year 2025.</p>
<p>Profile type: provider questionnaire (synthetic). Provider type assumed for the demo: {escape(p['type'])}. Status: unaudited. Ownership: privately held, so no Form 10-K is filed with the SEC.</p>
<p>Contents</p><p>Item 1. Business</p><p>Item 1A. Risk Factors</p><p>Item 2. Properties</p><p>Item 7. Operating and financial summary</p>
</div>
<div class="page">{short}<h2>Item 1. Business</h2>{para(p['business'])}</div>
<div class="page">{short}<h2>Item 1A. Risk Factors</h2>{para(p['risks'])}</div>
<div class="page">{short}<h2>Item 2. Properties</h2>
<table><tr><th>Location</th><th>Type</th><th>Doors</th></tr>{props}</table><p>{escape(p['properties_note'])}</p></div>
<div class="page">{short}<h2>Item 7. Operating and financial summary</h2>
<p>All figures are synthetic, illustrative and unaudited.</p>
<table><tr><th>Metric</th><th>2025</th><th>2024</th></tr>{fin}</table>{para(p['summary'])}</div>
</body></html>
"""


if __name__ == "__main__":
    for slug, p in PROFILES.items():
        out = RAW / f"{slug}_profile_synthetic.html"
        out.write_text(html(p), encoding="utf-8")
        print("wrote", out)
