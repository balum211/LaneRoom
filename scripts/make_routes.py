"""Fetch real road geometry for every lane leg (data/routes/road_geometry.json).

The route card draws each carrier's trucks driving along the actual highway, so it needs the road path between the
lane's cities. This script asks the public OSRM demo router (OpenStreetMap data) once per leg and commits the result,
so the app never calls a routing service at runtime.

    python scripts/make_routes.py
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from laneroom.maps import CITIES, LANE_ROUTES  # noqa: E402

OUT = ROOT / "data" / "routes" / "road_geometry.json"
URL = "https://router.project-osrm.org/route/v1/driving/{a};{b}?overview=full&geometries=geojson"


def thin(pts: list[list[float]], max_pts: int = 160) -> list[list[float]]:
    """Keep about max_pts evenly spaced points (plus the last) so the file stays small."""
    if len(pts) <= max_pts:
        return pts
    step = len(pts) / (max_pts - 1)
    out = [pts[int(i * step)] for i in range(max_pts - 1)]
    return out + [pts[-1]]


def leg(a: str, b: str) -> dict:
    (lo1, la1), (lo2, la2) = CITIES[a], CITIES[b]
    req = urllib.request.Request(URL.format(a=f"{lo1},{la1}", b=f"{lo2},{la2}"), headers={"User-Agent": "LaneRoom-demo"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.load(r)
    route = data["routes"][0]
    pts = [[round(lat, 4), round(lon, 4)] for lon, lat in route["geometry"]["coordinates"]]
    return {"miles": round(route["distance"] / 1609.344), "hours": round(route["duration"] / 3600, 1), "pts": thin(pts)}


if __name__ == "__main__":
    legs = sorted({tuple(x) for routes in LANE_ROUTES.values() for x in routes})
    out = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    for a, b in legs:
        key = f"{a}|{b}"
        if key in out:
            continue
        out[key] = leg(a, b)
        print(f"{key}: {out[key]['miles']} mi, {len(out[key]['pts'])} pts")
        time.sleep(1.1)  # be polite to the free demo server
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"_source": "OSRM demo router, OpenStreetMap data (ODbL)", **out}, separators=(",", ":")),
                   encoding="utf-8")
    print(f"{len(out)} legs -> {OUT}")
