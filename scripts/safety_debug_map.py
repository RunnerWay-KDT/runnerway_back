import argparse
import json
import os

from app.services.safety_score import (
    SafetyParams,
    compute_safety_score,
    load_cctv_points,
    load_lamp_points,
)


def main():
    parser = argparse.ArgumentParser(description="Safety score debug map (Leaflet HTML)")
    parser.add_argument("--route-json", required=True, help="경로 좌표 JSON 파일 (list of {lat,lng})")
    parser.add_argument("--output", default="safety_debug_map.html", help="출력 HTML 경로")
    parser.add_argument(
        "--cctv-csv",
        default=os.path.join(os.path.dirname(__file__), "..", "app", "data", "Seoul_CCTV.csv"),
        help="CCTV CSV 경로 (lat,lon 헤더)",
    )
    parser.add_argument(
        "--lamp-csv",
        default=os.path.join(os.path.dirname(__file__), "..", "app", "data", "Seoul_Lamp.csv"),
        help="가로등 CSV 경로 (위도,경도 헤더)",
    )
    parser.add_argument("--max-cctv", type=int, default=1500, help="지도에 찍을 CCTV 최대 개수")
    parser.add_argument("--max-lamp", type=int, default=1500, help="지도에 찍을 가로등 최대 개수")
    args = parser.parse_args()

    with open(args.route_json, "r", encoding="utf-8") as f:
        route_coords = json.load(f)

    cctv_points = load_cctv_points(os.path.abspath(args.cctv_csv))
    lamp_points = load_lamp_points(os.path.abspath(args.lamp_csv))
    if args.max_cctv and len(cctv_points) > args.max_cctv:
        cctv_points = cctv_points[: args.max_cctv]
    if args.max_lamp and len(lamp_points) > args.max_lamp:
        lamp_points = lamp_points[: args.max_lamp]

    params = SafetyParams()
    infra_points = cctv_points + lamp_points
    result = compute_safety_score(route_coords, infra_points, params=params, debug=True)

    center = route_coords[0] if route_coords else {"lat": 37.5665, "lng": 126.9780}
    html = render_html(
        center=center,
        route_coords=route_coords,
        cctv_points=cctv_points,
        lamp_points=lamp_points,
        debug=result.get("debug", {}),
        score=result.get("score"),
        features=result.get("features", {}),
    )

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"OK: {args.output}")


def render_html(center, route_coords, cctv_points, lamp_points, debug, score, features):
    route_json = json.dumps(route_coords, ensure_ascii=False)
    cctv_json = json.dumps(
        [{"lat": p["lat"], "lng": p["lon"]} for p in cctv_points],
        ensure_ascii=False,
    )
    lamp_json = json.dumps(
        [{"lat": p["lat"], "lng": p["lon"]} for p in lamp_points],
        ensure_ascii=False,
    )
    sample_json = json.dumps(debug.get("sample_points", []), ensure_ascii=False)
    corridor_json = json.dumps(debug.get("corridors", {}), ensure_ascii=False)
    center_json = json.dumps(center, ensure_ascii=False)
    features_json = json.dumps(features, ensure_ascii=False)

    return f"""<!doctype html>
<html lang="ko">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Safety Debug Map</title>
    <link
      rel="stylesheet"
      href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
      integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
      crossorigin=""
    />
    <style>
      html, body, #map {{ height: 100%; margin: 0; }}
      .panel {{
        position: absolute;
        top: 12px;
        right: 12px;
        z-index: 999;
        background: rgba(255,255,255,0.95);
        padding: 10px 12px;
        border-radius: 8px;
        font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif;
        font-size: 12px;
        line-height: 1.4;
        box-shadow: 0 4px 12px rgba(0,0,0,0.12);
      }}
      .label {{ font-weight: 600; }}
    </style>
  </head>
  <body>
    <div id="map"></div>
    <div class="panel">
      <div class="label">Safety Score: {score}</div>
      <pre style="margin:6px 0 0 0; white-space:pre-wrap;">{features_json}</pre>
    </div>
    <script
      src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
      integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
      crossorigin=""
    ></script>
    <script>
      const center = {center_json};
      const route = {route_json};
      const cctv = {cctv_json};
      const lamp = {lamp_json};
      const samples = {sample_json};
      const corridors = {corridor_json};

      const map = L.map('map').setView([center.lat, center.lng], 14);
      L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap contributors'
      }}).addTo(map);

      if (route.length) {{
        const poly = L.polyline(route.map(p => [p.lat, p.lng]), {{ color: '#0b74ff', weight: 4 }}).addTo(map);
        map.fitBounds(poly.getBounds(), {{ padding: [20, 20] }});
      }}

      if (corridors.lamp) {{
        L.polygon(corridors.lamp.map(p => [p.lat, p.lng]), {{
          color: '#ff8c00', weight: 1, fillOpacity: 0.08
        }}).addTo(map);
      }}
      if (corridors.cctv) {{
        L.polygon(corridors.cctv.map(p => [p.lat, p.lng]), {{
          color: '#00b894', weight: 1, fillOpacity: 0.08
        }}).addTo(map);
      }}

      for (const s of samples) {{
        const color = s.covered ? '#2ecc71' : '#e74c3c';
        L.circleMarker([s.lat, s.lng], {{
          radius: 3,
          color,
          fillColor: color,
          fillOpacity: 0.9,
          weight: 1
        }}).addTo(map);
      }}

      for (const p of cctv) {{
        L.circleMarker([p.lat, p.lng], {{
          radius: 2,
          color: '#7f8c8d',
          fillColor: '#7f8c8d',
          fillOpacity: 0.7,
          weight: 0
        }}).addTo(map);
      }}

      for (const p of lamp) {{
        L.circleMarker([p.lat, p.lng], {{
          radius: 2,
          color: '#f39c12',
          fillColor: '#f39c12',
          fillOpacity: 0.7,
          weight: 0
        }}).addTo(map);
      }}
    </script>
  </body>
</html>
"""


if __name__ == "__main__":
    main()
