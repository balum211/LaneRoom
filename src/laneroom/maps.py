"""Logistics visuals: a US route map (dot-matrix SVG with animated trucks), carrier badges and lane geometry.

Everything is drawn in plain SVG/HTML so it renders the same locally, on Streamlit Cloud and in screenshots,
with no map tiles or API keys. Carrier "logos" are original monogram badges (mode icon + initials), not the
companies' real trademarks.
"""
from __future__ import annotations

import math
from functools import lru_cache
from html import escape

# Categorical palette for carriers, fixed order (dataviz skill, dark-mode steps, validated against the app surfaces).
PROVIDERS = {
    "J.B. Hunt": {"color": "#3987e5", "mono": "JB", "icon": "train", "mode": "Intermodal · dedicated · truckload", "source": "FY2025 10-K"},
    "C.H. Robinson": {"color": "#d95926", "mono": "CR", "icon": "graph", "mode": "Broker / 3PL network", "source": "FY2025 10-K"},
    "Old Dominion": {"color": "#199e70", "mono": "OD", "icon": "package", "mode": "LTL carrier", "source": "FY2025 10-K"},
    "Armada": {"color": "#c98500", "mono": "AR", "icon": "truck", "mode": "Regional truckload", "source": "synthetic profile"},
    "Edge Logistics": {"color": "#d55181", "mono": "EL", "icon": "graph", "mode": "Freight brokerage", "source": "synthetic profile"},
    "First Star": {"color": "#008300", "mono": "FS", "icon": "truck", "mode": "Asset-light truckload", "source": "synthetic profile"},
    "BlueGrace Logistics": {"color": "#9085e9", "mono": "BG", "icon": "stack", "mode": "LTL 3PL / managed transport", "source": "synthetic profile"},
}
FALLBACK = {"color": "#8a9aa5", "mono": "??", "icon": "truck", "mode": "Carrier", "source": ""}

CITIES = {  # lon, lat
    "Seattle": (-122.3, 47.6), "Los Angeles": (-118.2, 34.05), "Phoenix": (-112.1, 33.45), "Denver": (-104.99, 39.74),
    "Dallas": (-96.8, 32.78), "Houston": (-95.37, 29.76), "Kansas City": (-94.58, 39.1), "Chicago": (-87.63, 41.88),
    "Memphis": (-90.05, 35.15), "Atlanta": (-84.39, 33.75), "Columbus": (-82.99, 39.96), "Charlotte": (-80.84, 35.23),
    "Newark": (-74.17, 40.74), "Miami": (-80.19, 25.76),
}
# Lane geometry: (origin, destination) pairs drawn for each scorecard lane.
LANE_ROUTES = {
    "DAL-ATL": [("Dallas", "Atlanta")],
    "CHI-LAX": [("Chicago", "Los Angeles")],
    "DAL-HOU": [("Dallas", "Houston")],
    "ATL-MIA": [("Atlanta", "Miami")],
    "LAX-PHX": [("Los Angeles", "Phoenix")],
    "CHI-NWK": [("Chicago", "Newark")],
    "LTL-NAT": [("Memphis", "Chicago"), ("Memphis", "Dallas"), ("Memphis", "Atlanta"), ("Columbus", "Newark"),
                ("Columbus", "Chicago"), ("Kansas City", "Denver"), ("Denver", "Seattle"), ("Dallas", "Houston"),
                ("Atlanta", "Charlotte"), ("Atlanta", "Miami"), ("Memphis", "Columbus"), ("Kansas City", "Memphis")],
    "PEAK-NAT": [("Los Angeles", "Phoenix"), ("Phoenix", "Dallas"), ("Los Angeles", "Chicago"), ("Chicago", "Newark"),
                 ("Dallas", "Atlanta"), ("Atlanta", "Newark"), ("Chicago", "Atlanta"), ("Seattle", "Chicago")],
}
LANE_HUBS = {"LTL-NAT": ["Memphis", "Columbus", "Kansas City"], "PEAK-NAT": ["Los Angeles", "Chicago", "Dallas", "Atlanta"]}

# Coarse outline of the contiguous US (lon, lat). Stylised: it only bounds the dot matrix.
_US = [(-124.7, 48.4), (-122.8, 49.0), (-95.2, 49.0), (-94.8, 49.4), (-89.6, 48.0), (-84.8, 46.5), (-82.5, 45.3),
       (-82.4, 43.0), (-79.0, 43.3), (-76.3, 44.2), (-74.9, 45.0), (-71.5, 45.0), (-69.2, 47.4), (-67.8, 47.1),
       (-67.0, 44.8), (-70.0, 43.7), (-70.6, 41.7), (-74.0, 40.6), (-75.5, 39.0), (-76.0, 37.0), (-75.5, 35.3),
       (-77.9, 33.9), (-80.9, 32.0), (-81.4, 30.4), (-80.0, 26.9), (-80.4, 25.2), (-81.8, 26.1), (-82.8, 28.0),
       (-83.7, 29.9), (-85.3, 29.7), (-86.5, 30.4), (-89.6, 30.2), (-90.0, 29.1), (-93.8, 29.7), (-94.7, 29.3),
       (-97.2, 27.6), (-97.4, 25.9), (-99.5, 27.5), (-101.4, 29.8), (-103.3, 29.0), (-104.7, 30.0), (-106.5, 31.8),
       (-108.2, 31.3), (-111.1, 31.3), (-114.8, 32.5), (-117.1, 32.5), (-118.5, 34.0), (-120.6, 34.6), (-121.9, 36.6),
       (-123.0, 38.0), (-124.2, 40.4), (-124.4, 42.8), (-124.0, 46.3)]

W, H = 1000, 560
_K = 15.6  # px per degree of latitude


def project(lon: float, lat: float) -> tuple[float, float]:
    return (lon + 126) * _K * math.cos(math.radians(38)) * 1.12 + 10, (50.5 - lat) * _K * 1.32 + 6


def _inside(lon: float, lat: float) -> bool:
    inside, j = False, len(_US) - 1
    for i, (xi, yi) in enumerate(_US):
        xj, yj = _US[j]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


@lru_cache(maxsize=1)
def _dots() -> str:
    out = []
    lat = 24.6
    while lat < 49.4:
        lon = -125.0
        while lon < -66.5:
            if _inside(lon, lat):
                x, y = project(lon, lat)
                out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.1"/>')
            lon += 0.95
        lat += 0.8
    return f'<g class="usdots">{"".join(out)}</g>'


def miles(a: str, b: str) -> int:
    """Great-circle miles × 1.15 road factor (an estimate, labelled as such in the UI)."""
    (lo1, la1), (lo2, la2) = CITIES[a], CITIES[b]
    p1, p2 = math.radians(la1), math.radians(la2)
    d = math.acos(min(1, math.sin(p1) * math.sin(p2) + math.cos(p1) * math.cos(p2) * math.cos(math.radians(lo2 - lo1))))
    return int(round(3958.8 * d * 1.15, -1))


def _arc(a: str, b: str, bend: float = 0.18, offset: float = 0.0) -> str:
    (x1, y1), (x2, y2) = project(*CITIES[a]), project(*CITIES[b])
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy) or 1
    nx, ny = dy / length, -dx / length  # normal (points "up" for west->east lanes)
    if ny > 0:
        nx, ny = -nx, -ny
    k = bend * length + offset
    return f"M{x1:.1f},{y1:.1f} Q{mx + nx * k:.1f},{my + ny * k:.1f} {x2:.1f},{y2:.1f}"


TRUCK = ('<symbol id="lr-truck" viewBox="-14 -7 28 14"><rect x="-13" y="-5" width="17" height="10" rx="1.5" fill="currentColor"/>'
         '<path d="M5 -3 h4.5 l3.5 3.5 v4.5 h-8z" fill="currentColor"/><circle cx="-8" cy="5.5" r="2" fill="#04131B"/>'
         '<circle cx="8" cy="5.5" r="2" fill="#04131B"/></symbol>')
TRAIN = ('<symbol id="lr-train" viewBox="-16 -7 32 14"><rect x="-15" y="-5" width="13" height="9" rx="1.5" fill="currentColor"/>'
         '<rect x="0" y="-5" width="15" height="9" rx="2.5" fill="currentColor"/><circle cx="-11" cy="5.5" r="1.8" fill="#04131B"/>'
         '<circle cx="-5" cy="5.5" r="1.8" fill="#04131B"/><circle cx="4" cy="5.5" r="1.8" fill="#04131B"/>'
         '<circle cx="11" cy="5.5" r="1.8" fill="#04131B"/></symbol>')


def _vehicle(path_id: str, kind: str, color: str, dur: float, begin: float, scale: float = 1.0) -> str:
    w = 26 * scale
    return (f'<use href="#lr-{kind}" width="{w:.0f}" height="{w / 2:.0f}" x="{-w / 2:.0f}" y="{-w / 4:.0f}" '
            f'style="color:{color}"><animateMotion dur="{dur:.1f}s" begin="-{begin:.1f}s" repeatCount="indefinite" '
            f'rotate="auto"><mpath href="#{path_id}"/></animateMotion></use>')


def _city(name: str, hub: bool = False, label_side: str = "right", z: float = 1.0) -> str:
    x, y = project(*CITIES[name])
    anchor, dx = ("start", 12 * z) if label_side == "right" else ("end", -12 * z)
    ring = f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{12 * z:.1f}" class="pulse"/>' if hub else ""
    return (f'{ring}<circle cx="{x:.1f}" cy="{y:.1f}" r="{(7 if hub else 5.5) * z:.1f}" class="city{" hub" if hub else ""}" '
            f'style="stroke-width:{2 * z:.1f}"/><text x="{x + dx:.1f}" y="{y + 6 * z:.1f}" text-anchor="{anchor}" class="clabel" '
            f'style="font-size:{19 * z:.1f}px;stroke-width:{4 * z:.1f}px">{escape(name)}</text>')


_LEFT_LABELS = {"Los Angeles", "Seattle", "Phoenix", "Houston", "Miami", "Dallas"}


def network_svg(uid: str = "hero", lanes: list[str] | None = None, accent: str = "#FF8A3D") -> str:
    """Hero map: every scorecard lane as a dashed animated route with trucks (and a train on intermodal)."""
    lanes = lanes or list(LANE_ROUTES)
    paths, vehicles, cities = [], [], set()
    n = 0
    for lane in lanes:
        for a, b in LANE_ROUTES[lane]:
            pid = f"{uid}-r{n}"
            kind = "train" if lane == "CHI-LAX" else "truck"
            paths.append(f'<path id="{pid}" d="{_arc(a, b)}" class="route"/>')
            vehicles.append(_vehicle(pid, kind, accent if lane != "CHI-LAX" else "#3987e5", 7 + (n % 5) * 1.7, n * 1.3, 0.9))
            cities.update((a, b))
            n += 1
    city_svg = "".join(_city(c, hub=c in ("Chicago", "Dallas", "Atlanta", "Memphis"),
                             label_side="left" if c in _LEFT_LABELS else "right") for c in sorted(cities))
    return (f'<svg class="lrmap" viewBox="0 0 860 560" role="img" aria-label="Route map of the scorecard lanes">'
            f'<defs>{TRUCK}{TRAIN}</defs>{_dots()}<g>{"".join(paths)}</g>{city_svg}<g>{"".join(vehicles)}</g></svg>')


def _viewbox(cities: set[str], pad: float = 120) -> tuple[str, float]:
    """Zoom to the lane: bounding box of its cities plus padding, at the map's aspect ratio. Returns (viewBox, zoom)."""
    pts = [project(*CITIES[c]) for c in cities] or [(0, 0), (W, H)]
    x0, x1 = min(p[0] for p in pts) - pad, max(p[0] for p in pts) + pad
    y0, y1 = min(p[1] for p in pts) - pad, max(p[1] for p in pts) + pad
    w, h = x1 - x0, y1 - y0
    if w / h < W / H:
        w2 = h * W / H
        x0, w = x0 - (w2 - w) / 2, w2
    else:
        h2 = w * H / W
        y0, h = y0 - (h2 - h) / 2, h2
    w, h = min(w, W), min(h, H)
    x0, y0 = max(min(x0, W - w), 0), max(min(y0, H - h), 0)
    return f"{x0:.0f} {y0:.0f} {w:.0f} {h:.0f}", w / W


def lane_svg(lane_id: str, allocation: list[dict], uid: str = "lane") -> str:
    """One lane, drawn as a bundle of parallel routes: one per awarded carrier, width ∝ its share, in its colour."""
    routes = LANE_ROUTES.get(lane_id, [])
    vb, z = _viewbox({c for r in routes for c in r}, pad=110 if len(routes) == 1 else 60)
    awarded = [r for r in allocation if r.get("share", 0) > 0]
    paths, vehicles, cities = [], [], set()
    for ri, (a, b) in enumerate(routes):
        cities.update((a, b))
        if len(routes) > 1:  # network lanes: one route per leg, coloured by the leg's lead carrier
            r = awarded[ri % len(awarded)] if awarded else None
            color = PROVIDERS.get(r["company"], FALLBACK)["color"] if r else "#5c7380"
            pid = f"{uid}-r{ri}"
            paths.append(f'<path id="{pid}" d="{_arc(a, b)}" class="lane-route" style="stroke:{color};stroke-width:{5 * z:.1f}"/>')
            vehicles.append(_vehicle(pid, "truck", color, 6 + (ri % 4) * 1.5, ri * 0.9, 1.1 * z))
            continue
        span = max(len(awarded) - 1, 1)
        for i, r in enumerate(awarded):
            p = PROVIDERS.get(r["company"], FALLBACK)
            off = (i - (len(awarded) - 1) / 2) * 34 * z / span * min(len(awarded) - 1, 3)
            pid = f"{uid}-{i}"
            width = (3 + r["share"] / 100 * 16) * z
            paths.append(f'<path id="{pid}" d="{_arc(a, b, 0.2, off)}" class="lane-route" '
                         f'style="stroke:{p["color"]};stroke-width:{width:.1f}"/>')
            kind = "train" if lane_id == "CHI-LAX" and r["company"] == "J.B. Hunt" else "truck"
            trucks = max(1, round(r["share"] / 20))
            for t in range(trucks):
                vehicles.append(_vehicle(pid, kind, p["color"], 9, t * 9 / trucks + i * 0.7, 1.3 * z))
    hubs = set(LANE_HUBS.get(lane_id, [])) | ({routes[0][0], routes[0][1]} if len(routes) == 1 else set())
    city_svg = "".join(_city(c, hub=c in hubs, label_side="left" if c in _LEFT_LABELS else "right", z=max(z, .45))
                       for c in sorted(cities))
    return (f'<svg class="lrmap lane" viewBox="{vb}" role="img" aria-label="Route map for the lane with carrier shares">'
            f'<defs>{TRUCK}{TRAIN}</defs>{_dots()}<g>{"".join(paths)}</g>{city_svg}<g>{"".join(vehicles)}</g></svg>')


def lane_distance(lane_id: str) -> str:
    routes = LANE_ROUTES.get(lane_id, [])
    if len(routes) == 1:
        return f"≈ {miles(*routes[0]):,} road miles (est.)"
    return f"{len(routes)} network legs · {len({c for r in routes for c in r})} metros"


# ---------------------------------------------------------------- Google Maps
# Real road geography for the route card. Point-to-point lanes show the driving route; network lanes show a
# representative trunk route through their hubs. With GOOGLE_MAPS_API_KEY set the official Maps Embed API is
# used; without one, the keyless classic embed (no account needed, fine for a demo).
STATES = {"Seattle": "WA", "Los Angeles": "CA", "Phoenix": "AZ", "Denver": "CO", "Dallas": "TX", "Houston": "TX",
          "Kansas City": "MO", "Chicago": "IL", "Memphis": "TN", "Atlanta": "GA", "Columbus": "OH",
          "Charlotte": "NC", "Newark": "NJ", "Miami": "FL"}
GOOGLE_ROUTES = {
    "LTL-NAT": ["Kansas City", "Memphis", "Columbus", "Newark"],
    "PEAK-NAT": ["Los Angeles", "Phoenix", "Dallas", "Atlanta", "Newark"],
}


def google_stops(lane_id: str) -> list[str]:
    stops = GOOGLE_ROUTES.get(lane_id) or list(LANE_ROUTES.get(lane_id, [()])[0])
    return [f"{c}, {STATES.get(c, '')}".strip(", ") for c in stops]


def google_maps_url(lane_id: str, api_key: str = "", embed: bool = True) -> str:
    """Google Maps directions URL for a lane: an iframe src (embed=True) or a link that opens Google Maps."""
    from urllib.parse import quote_plus

    stops = google_stops(lane_id)
    if not stops:
        return ""
    if not embed:
        return "https://www.google.com/maps/dir/" + "/".join(quote_plus(s) for s in stops)
    if api_key:
        url = (f"https://www.google.com/maps/embed/v1/directions?key={quote_plus(api_key)}"
               f"&origin={quote_plus(stops[0])}&destination={quote_plus(stops[-1])}&mode=driving")
        if len(stops) > 2:
            url += "&waypoints=" + "|".join(quote_plus(s) for s in stops[1:-1])
        return url
    daddr = "+to:".join(quote_plus(s) for s in stops[1:])
    return f"https://maps.google.com/maps?saddr={quote_plus(stops[0])}&daddr={daddr}&output=embed"
