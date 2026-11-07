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
        road = road_leg(*routes[0])
        if road:
            return f"{road['miles']:,} road miles · ~{road['hours']:g} h drive"
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


# ---------------------------------------------------------------- real-map lane view (Leaflet)
def _bezier(a: tuple, b: tuple, bend: float, offset: float, n: int = 48) -> list[list[float]]:
    """Quadratic curve from a to b (lon, lat) bowed sideways by bend * length + offset degrees; returns [lat, lon]."""
    (x1, y1), (x2, y2) = a, b
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / length, dx / length
    k = bend * length + offset
    cx, cy = (x1 + x2) / 2 + nx * k, (y1 + y2) / 2 + ny * k
    pts = []
    for i in range(n + 1):
        t = i / n
        x = (1 - t) ** 2 * x1 + 2 * (1 - t) * t * cx + t * t * x2
        y = (1 - t) ** 2 * y1 + 2 * (1 - t) * t * cy + t * t * y2
        pts.append([round(y, 4), round(x, 4)])
    return pts


@lru_cache(maxsize=1)
def road_geometry() -> dict:
    """Real road paths per leg ("A|B" -> {"miles", "hours", "pts": [[lat, lon], ...]}), from scripts/make_routes.py."""
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "data" / "routes" / "road_geometry.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def road_leg(a: str, b: str) -> dict | None:
    return road_geometry().get(f"{a}|{b}")


def lane_routes_geo(lane_id: str, allocation: list[dict]) -> list[dict]:
    """Per-carrier routes in lat/lon for the real map. Each follows the actual road (OSRM / OpenStreetMap geometry)
    when it is on file, else a gentle curve; the browser offsets parallel carriers by a few pixels."""
    routes = LANE_ROUTES.get(lane_id, [])
    awarded = [r for r in allocation if r.get("share", 0) > 0]
    out = []
    for ri, (a, b) in enumerate(routes):
        road = road_leg(a, b)
        pts = road["pts"] if road else _bezier(CITIES[a], CITIES[b], 0.10, 0)
        if len(routes) > 1:  # network lanes: one leg per line, coloured by a lead carrier
            r = awarded[ri % len(awarded)] if awarded else {"company": "", "share": 0}
            out.append({"carrier": r["company"], "share": r.get("share", 0), "loads": r.get("loads"),
                        "color": PROVIDERS.get(r["company"], FALLBACK)["color"], "leg": f"{a} → {b}", "pts": pts,
                        "weight": 4, "trucks": 1, "kind": "truck", "slot": 0, "road": bool(road)})
            continue
        n = len(awarded)
        for i, r in enumerate(awarded):
            out.append({"carrier": r["company"], "share": r["share"], "loads": r.get("loads"),
                        "color": PROVIDERS.get(r["company"], FALLBACK)["color"], "leg": f"{a} → {b}", "pts": pts,
                        "weight": round(3 + r["share"] / 10, 1), "trucks": max(1, round(r["share"] / 15)),
                        "kind": "train" if lane_id == "CHI-LAX" and r["company"] == "J.B. Hunt" else "truck",
                        "slot": i - (n - 1) / 2, "road": bool(road)})
    return out


LEAFLET_HTML = """<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
html,body{margin:0;height:100%;background:#e8eef1;font-family:system-ui,Segoe UI,sans-serif}
#m{position:absolute;inset:0;border-radius:14px;overflow:hidden}
.city{color:#0b2633;font:700 12px system-ui;text-shadow:0 0 3px #fff,0 0 3px #fff,0 0 5px #fff;white-space:nowrap}
.leaflet-tooltip.lr{background:#0b2633;color:#eaf6ff;border:1px solid #1d4252;border-radius:8px;font:12px system-ui}
.leaflet-tooltip.lr:before{display:none}
.veh svg{filter:drop-shadow(0 1px 2px rgba(0,0,0,.6))}
.legend{background:rgba(255,255,255,.92);border-radius:8px;padding:6px 8px;font:11px system-ui;color:#0b2633;
  box-shadow:0 1px 4px rgba(0,0,0,.3)}
.legend i{display:inline-block;width:14px;height:4px;border-radius:2px;margin-right:5px;vertical-align:middle}
</style></head><body><div id="m"></div><script>
const D = __DATA__;
const map = L.map('m', {zoomControl: true, scrollWheelZoom: false});
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
  {maxZoom: 18, attribution: 'Tiles &copy; Esri, HERE, Garmin, USGS &middot; Roads &copy; OpenStreetMap (OSRM)'}).addTo(map);
const TRUCK = c => `<svg width="34" height="18" viewBox="-14 -7 28 14"><rect x="-13" y="-5" width="17" height="10" rx="1.5" fill="${c}" stroke="#fff" stroke-width="1.2"/><path d="M5 -3 h4.5 l3.5 3.5 v4.5 h-8z" fill="${c}" stroke="#fff" stroke-width="1.2"/><circle cx="-8" cy="5.5" r="2.2" fill="#111"/><circle cx="8" cy="5.5" r="2.2" fill="#111"/></svg>`;
const TRAIN = c => `<svg width="38" height="18" viewBox="-16 -7 32 14"><rect x="-15" y="-5" width="13" height="9" rx="1.5" fill="${c}" stroke="#fff"/><rect x="0" y="-5" width="15" height="9" rx="2.5" fill="${c}" stroke="#fff"/><circle cx="-11" cy="5.5" r="1.8" fill="#111"/><circle cx="-5" cy="5.5" r="1.8" fill="#111"/><circle cx="4" cy="5.5" r="1.8" fill="#111"/><circle cx="11" cy="5.5" r="1.8" fill="#111"/></svg>`;
const GAP = 7;  // px between parallel carrier routes
// Shift a lat/lon path sideways by px screen pixels at the current zoom, so parallel carriers stay visible.
function shifted(pts, px) {
  if (!px) return pts;
  const P = pts.map(p => map.latLngToLayerPoint(p));
  return P.map((p, i) => {
    const a = P[Math.max(i - 1, 0)], b = P[Math.min(i + 1, P.length - 1)];
    const dx = b.x - a.x, dy = b.y - a.y, len = Math.hypot(dx, dy) || 1;
    return map.layerPointToLatLng(L.point(p.x - dy / len * px, p.y + dx / len * px));
  });
}
const lines = [], movers = [], all = [];
(D.context || []).forEach(c => {
  L.polyline(c.pts, {color: '#ffffff', weight: 5, opacity: .7}).addTo(map);
  L.polyline(c.pts, {color: '#5b6f7c', weight: 2.5, opacity: .85, dashArray: '6 5'}).addTo(map)
    .bindTooltip(`${c.lane}<br>${c.leg} &middot; ${c.miles.toLocaleString()} road mi`, {sticky: true, className: 'lr'});
  if (D.fit_all) c.pts.forEach(p => all.push(p));
});
D.routes.forEach((r, i) => {
  r.pts.forEach(p => all.push(p));
  const casing = L.polyline(r.pts, {color: '#ffffff', weight: r.weight + 3, opacity: .9}).addTo(map);
  const line = L.polyline(r.pts, {color: r.color, weight: r.weight, opacity: .95, lineCap: 'round', lineJoin: 'round'}).addTo(map);
  const loads = r.loads != null ? ` &middot; ${r.loads.toLocaleString()} loads/wk` : '';
  line.bindTooltip(`<b>${r.carrier}</b> &middot; ${Math.round(r.share)}%${loads}<br>${r.leg}`, {sticky: true, className: 'lr'});
  lines.push({r, casing, line});
  for (let t = 0; t < r.trucks; t++) {
    const icon = L.divIcon({className: 'veh', html: (r.kind === 'train' ? TRAIN : TRUCK)(r.color), iconSize: [34, 18], iconAnchor: [17, 9]});
    movers.push({r, m: L.marker(r.pts[0], {icon, interactive: false, zIndexOffset: 500}).addTo(map),
                 phase: t / r.trucks + i * 0.137, path: r.pts});
  }
});
D.cities.forEach(c => {
  L.circleMarker([c.lat, c.lon], {radius: c.hub ? 8 : 6, color: '#ffffff', weight: 2.5, fillColor: '#FF8A3D', fillOpacity: 1}).addTo(map);
  L.marker([c.lat, c.lon], {icon: L.divIcon({className: 'city', html: c.name, iconSize: null,
            iconAnchor: c.below ? [c.name.length * 3.5, -10] : c.left ? [c.name.length * 7 + 12, 8] : [-12, 8]}),
            interactive: false}).addTo(map);
});
const legend = L.control({position: 'bottomleft'});
legend.onAdd = () => { const d = L.DomUtil.create('div', 'legend');
  const seen = new Set(); d.innerHTML = D.routes.filter(r => !seen.has(r.carrier) && seen.add(r.carrier))
    .map(r => `<div><i style="background:${r.color}"></i>${r.carrier} ${Math.round(r.share)}%</div>`).join('');
  return d; };
legend.addTo(map);
map.fitBounds(all, {padding: [30, 30]});
function layout() {
  lines.forEach(({r, casing, line}) => { const p = shifted(r.pts, r.slot * GAP); casing.setLatLngs(p); line.setLatLngs(p); });
  movers.forEach(v => { v.path = shifted(v.r.pts, v.r.slot * GAP).map(p => [p.lat ?? p[0], p.lng ?? p[1]]); });
}
map.on('zoomend', layout); layout();
// Inside a hidden Streamlit tab the frame starts at 0x0: re-fit once it has a real size.
let fitted = document.getElementById('m').clientWidth > 0;
new ResizeObserver(() => {
  const el = document.getElementById('m');
  if (!el.clientWidth || !el.clientHeight) return;
  map.invalidateSize();
  if (!fitted) { map.fitBounds(all, {padding: [30, 30]}); fitted = true; layout(); }
}).observe(document.getElementById('m'));
// Trucks move at a steady map speed: walk the path by cumulative length, not by point index.
function cum(path) { const c = [0]; for (let i = 1; i < path.length; i++) c.push(c[i - 1] + Math.hypot(path[i][0] - path[i - 1][0], path[i][1] - path[i - 1][1])); return c; }
function at(path, f) {
  const c = v_c.get(path) || (v_c.set(path, cum(path)), v_c.get(path)), d = f * c[c.length - 1];
  let i = 1; while (i < c.length - 1 && c[i] < d) i++;
  const u = (d - c[i - 1]) / ((c[i] - c[i - 1]) || 1);
  return [path[i - 1][0] + (path[i][0] - path[i - 1][0]) * u, path[i - 1][1] + (path[i][1] - path[i - 1][1]) * u];
}
const v_c = new WeakMap();
const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const PERIOD = D.routes.length > 1 ? 9000 : 14000;
function tick(now) {
  movers.forEach(v => v.m.setLatLng(at(v.path, reduce ? (v.phase % 1) : ((now / PERIOD + v.phase) % 1))));
  if (!reduce) requestAnimationFrame(tick);
}
requestAnimationFrame(tick);
</script></body></html>"""


def lane_map_html(lane_id: str, allocation: list[dict], network: bool = False) -> str:
    """Self-contained Leaflet page: the lane on a street map (Esri World Street Map, keyless), one coloured route per
    carrier along the real road, and that carrier's trucks driving it."""
    import json

    routes = LANE_ROUTES.get(lane_id, [])
    names = sorted({c for r in routes for c in r})
    hubs = set(LANE_HUBS.get(lane_id, [])) | ({routes[0][0], routes[0][1]} if len(routes) == 1 else set())
    data = {"routes": lane_routes_geo(lane_id, allocation),
            "cities": [{"name": c, "lon": CITIES[c][0], "lat": CITIES[c][1], "hub": c in hubs, "left": c in _LEFT_LABELS,
                        "below": c == "Phoenix" and "Los Angeles" in names} for c in names]}
    if network:  # every other scorecard lane as a dashed grey road route, map fitted to the whole network
        from . import scorecard

        own = {tuple(r) for r in routes}
        seen, ctx = set(own), []
        lane_names = {k: v["lane"] for k, v in scorecard.lanes().items()}
        for other, legs in LANE_ROUTES.items():
            for a, b in legs:
                road = road_leg(a, b)
                if (a, b) in seen or not road:
                    continue
                seen.add((a, b))
                ctx.append({"lane": lane_names.get(other, other), "leg": f"{a} → {b}", "miles": road["miles"],
                            "pts": road["pts"]})
        allc = sorted({c for legs in LANE_ROUTES.values() for leg in legs for c in leg})
        data["context"], data["fit_all"] = ctx, True
        data["cities"] = [{"name": c, "lon": CITIES[c][0], "lat": CITIES[c][1], "hub": c in hubs or c in names,
                           "left": c in _LEFT_LABELS, "below": c == "Phoenix"} for c in allc]
    return LEAFLET_HTML.replace("__DATA__", json.dumps(data))
