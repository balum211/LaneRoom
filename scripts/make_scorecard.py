"""Generate the SYNTHETIC shipper scorecard (data/scorecard/shipper_scorecard_synthetic.csv).

Public 10-Ks do not report shipper-level tender acceptance, on-time %, rates or claims, so LaneRoom
uses an illustrative scorecard that a shipper's TMS would produce. Every value here is made up for the
demo. It is deterministic (no randomness), so the eval and tests are reproducible.

    python scripts/make_scorecard.py
"""
from __future__ import annotations

import csv
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data" / "scorecard" / "shipper_scorecard_synthetic.csv"

LANES = {
    "DAL-ATL": ("Dallas, TX to Atlanta, GA", "Dry van truckload"),
    "LTL-NAT": ("National LTL contract", "LTL"),
    "PEAK-NAT": ("Peak season surge (national)", "Truckload and LTL surge"),
    "CHI-LAX": ("Chicago, IL to Los Angeles, CA", "Intermodal and truckload"),
    "DAL-HOU": ("Dallas, TX to Houston, TX", "Dry van truckload (short haul)"),
    "ATL-MIA": ("Atlanta, GA to Miami, FL", "Dry van truckload"),
    "LAX-PHX": ("Los Angeles, CA to Phoenix, AZ", "Dry van truckload"),
    "CHI-NWK": ("Chicago, IL to Newark, NJ", "Truckload and intermodal"),
}

# lane -> carrier -> (tenders offered per quarter, acceptance %, on-time %, rate per mile, claims %),
# then per-quarter deltas (acceptance pts, on-time pts, rate $) for Q1..Q4.
BASE = {
    "DAL-ATL": {
        "J.B. Hunt": (2600, 94.0, 96.4, 2.36, 0.14),
        "C.H. Robinson": (2300, 89.0, 92.8, 2.17, 0.31),
        "Armada": (1600, 92.0, 95.3, 2.29, 0.21),
        "Edge Logistics": (1200, 87.0, 92.0, 2.14, 0.34),
        "BlueGrace Logistics": (900, 88.5, 92.6, 2.20, 0.30),
    },
    "LTL-NAT": {
        "Old Dominion": (3200, 99.1, 99.0, 5.92, 0.09),
        "C.H. Robinson": (2400, 95.0, 93.6, 5.08, 0.44),
        "Armada": (900, 92.5, 93.2, 5.36, 0.33),
        "BlueGrace Logistics": (1600, 94.0, 93.0, 5.02, 0.40),
        "First Star": (700, 91.0, 92.4, 5.20, 0.38),
    },
    "PEAK-NAT": {
        "J.B. Hunt": (3000, 92.0, 94.8, 2.58, 0.17),
        "C.H. Robinson": (2800, 91.0, 91.2, 2.83, 0.36),
        "Old Dominion": (1800, 98.0, 98.4, 6.31, 0.10),
        "Armada": (1400, 88.0, 93.4, 2.52, 0.24),
        "Edge Logistics": (1500, 89.0, 90.5, 2.78, 0.38),
        "First Star": (900, 86.0, 91.0, 2.70, 0.30),
    },
    "CHI-LAX": {
        "J.B. Hunt": (2200, 95.5, 95.0, 1.84, 0.12),
        "C.H. Robinson": (1700, 90.0, 91.5, 2.06, 0.29),
        "Edge Logistics": (900, 88.0, 90.8, 2.01, 0.33),
        "First Star": (600, 87.5, 91.6, 2.10, 0.27),
    },
    # Short haul: rates per mile run higher because fixed loading time is spread over fewer miles.
    "DAL-HOU": {
        "J.B. Hunt": (2400, 93.0, 96.0, 3.05, 0.13),
        "C.H. Robinson": (2100, 88.5, 92.4, 2.88, 0.30),
        "Armada": (1500, 93.5, 96.2, 2.96, 0.19),
        "Edge Logistics": (1300, 87.5, 91.8, 2.84, 0.33),
        "First Star": (800, 90.0, 93.0, 2.92, 0.26),
    },
    "ATL-MIA": {
        "J.B. Hunt": (1800, 92.5, 95.6, 2.48, 0.15),
        "C.H. Robinson": (1700, 89.5, 92.1, 2.31, 0.32),
        "Armada": (1100, 91.0, 94.8, 2.40, 0.22),
        "BlueGrace Logistics": (800, 88.0, 92.4, 2.34, 0.31),
    },
    "LAX-PHX": {
        "J.B. Hunt": (1900, 93.5, 95.8, 2.62, 0.14),
        "C.H. Robinson": (1800, 90.0, 92.5, 2.44, 0.30),
        "Edge Logistics": (1000, 88.0, 91.2, 2.39, 0.35),
        "First Star": (500, 87.0, 91.4, 2.51, 0.28),
    },
    "CHI-NWK": {
        "J.B. Hunt": (2300, 94.5, 95.2, 2.12, 0.13),
        "C.H. Robinson": (2000, 89.0, 91.9, 2.27, 0.31),
        "Old Dominion": (900, 98.5, 98.8, 4.95, 0.09),
        "Edge Logistics": (1100, 88.5, 91.0, 2.22, 0.34),
        "BlueGrace Logistics": (700, 89.0, 92.2, 2.30, 0.32),
    },
}
# Seasonality: peak season (Q4) squeezes asset fleets harder than brokers' flexible networks.
SEASON = {"asset": ((0.6, 0.3, -0.03), (0.2, 0.1, -0.01), (-0.4, -0.2, 0.02), (-2.4, -1.1, 0.09)),
          "broker": ((0.4, 0.2, -0.05), (0.0, 0.0, -0.02), (-0.2, -0.1, 0.03), (-1.0, -0.6, 0.14)),
          "small": ((0.8, 0.4, -0.02), (0.4, 0.2, 0.0), (-0.8, -0.3, 0.03), (-9.5, -2.6, 0.11))}
KIND = {"J.B. Hunt": "asset", "Old Dominion": "asset", "C.H. Robinson": "broker", "Armada": "small",
        "Edge Logistics": "broker", "BlueGrace Logistics": "broker", "First Star": "small"}
# Peak lane: tenders offered jump in Q4.
VOLUME = {"PEAK-NAT": (0.6, 0.7, 0.9, 1.8)}


def rows() -> list[dict]:
    out = []
    n = 0
    for lane_id, carriers in BASE.items():
        lane, mode = LANES[lane_id]
        for carrier, (offered, acc, ot, rate, claims) in carriers.items():
            for q in range(4):
                d_acc, d_ot, d_rate = SEASON[KIND[carrier]][q]
                off = round(offered * VOLUME.get(lane_id, (1, 1, 1, 1))[q])
                a = min(99.8, acc + d_acc * (1.6 if lane_id == "PEAK-NAT" else 1.0))
                accepted = round(off * a / 100)
                n += 1
                out.append({
                    "row_id": f"S{n:02d}", "lane_id": lane_id, "lane": lane, "mode": mode, "carrier": carrier,
                    "period": f"Q{q + 1} 2025", "tenders_offered": off, "tenders_accepted": accepted,
                    "acceptance_pct": round(accepted / off * 100, 1), "on_time_pct": round(min(99.9, ot + d_ot), 1),
                    "rate_per_mile": round(rate + d_rate, 2), "claims_pct": round(claims + (0.03 if q == 3 else 0.0), 2),
                    "source": "SYNTHETIC shipper scorecard (illustrative, not real carrier data)",
                })
    return out


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    data = rows()
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(data[0]))
        w.writeheader()
        w.writerows(data)
    print(f"{len(data)} rows -> {OUT}")
