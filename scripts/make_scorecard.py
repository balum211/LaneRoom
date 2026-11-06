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
}

# lane -> carrier -> (tenders offered per quarter, acceptance %, on-time %, rate per mile, claims %),
# then per-quarter deltas (acceptance pts, on-time pts, rate $) for Q1..Q4.
BASE = {
    "DAL-ATL": {
        "J.B. Hunt": (2600, 94.0, 96.4, 2.36, 0.14),
        "C.H. Robinson": (2300, 89.0, 92.8, 2.17, 0.31),
        "Armada": (1600, 92.0, 95.3, 2.29, 0.21),
    },
    "LTL-NAT": {
        "Old Dominion": (3200, 99.1, 99.0, 5.92, 0.09),
        "C.H. Robinson": (2400, 95.0, 93.6, 5.08, 0.44),
        "Armada": (900, 92.5, 93.2, 5.36, 0.33),
    },
    "PEAK-NAT": {
        "J.B. Hunt": (3000, 92.0, 94.8, 2.58, 0.17),
        "C.H. Robinson": (2800, 91.0, 91.2, 2.83, 0.36),
        "Old Dominion": (1800, 98.0, 98.4, 6.31, 0.10),
        "Armada": (1400, 88.0, 93.4, 2.52, 0.24),
    },
    "CHI-LAX": {
        "J.B. Hunt": (2200, 95.5, 95.0, 1.84, 0.12),
        "C.H. Robinson": (1700, 90.0, 91.5, 2.06, 0.29),
    },
}
# Seasonality: peak season (Q4) squeezes asset fleets harder than brokers' flexible networks.
SEASON = {"asset": ((0.6, 0.3, -0.03), (0.2, 0.1, -0.01), (-0.4, -0.2, 0.02), (-2.4, -1.1, 0.09)),
          "broker": ((0.4, 0.2, -0.05), (0.0, 0.0, -0.02), (-0.2, -0.1, 0.03), (-1.0, -0.6, 0.14)),
          "small": ((0.8, 0.4, -0.02), (0.4, 0.2, 0.0), (-0.8, -0.3, 0.03), (-9.5, -2.6, 0.11))}
KIND = {"J.B. Hunt": "asset", "Old Dominion": "asset", "C.H. Robinson": "broker", "Armada": "small"}
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
