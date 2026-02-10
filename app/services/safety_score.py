from __future__ import annotations  # 

from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, Iterable, List, Optional, Tuple
import csv
import math
import os

from shapely.geometry import LineString, Point, Polygon
from shapely.strtree import STRtree
from pyproj import Transformer


LatLng = Dict[str, float]  # {"lat": .., "lng": ..}
LonLat = Tuple[float, float]  # (lon, lat)

DEFAULT_CCTV_CSV = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "Gangnam_CCTV.csv")
)
DEFAULT_LAMP_CSV = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "Gangnam_Lamp.csv")
)


@dataclass
class SafetyParams:
    # 샘플링 간격(m): 10~20m 권장
    sample_step_m: float = 20.0

    # 레이어별 커버 반경(m)
    lamp_radius_m: float = 15.0
    cctv_radius_m: float = 50.0

    # 밀도 포화 파라미터(k): density_score = 1 - exp(-density/k)
    density_k_per_km: float = 20.0

    # 최대 공백 패널티 기준(G)
    gap_G_m: float = 150.0

    # 최종 가중치
    w_density: float = 0.35
    w_coverage: float = 0.45
    w_gap: float = 0.20

    # 최고점 80점 문제 해결: raw / 0.80
    rescale_max: float = 0.80

    # 투영 좌표계
    metric_crs: str = "EPSG:5179"


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _transformer(metric_crs: str) -> Transformer:
    return Transformer.from_crs("EPSG:4326", metric_crs, always_xy=True)


def _project_lonlat_list(
    coords: Iterable[LonLat],
    transformer: Transformer,
) -> List[Tuple[float, float]]:
    return [transformer.transform(lon, lat) for lon, lat in coords]

def _sample_points_along_line(line_m: LineString, step_m: float) -> List[Point]:
    length = float(line_m.length)
    if length <= 0:
        return []

    pts: List[Point] = []
    d = 0.0
    while d <= length:
        pts.append(line_m.interpolate(d))
        d += step_m

    if pts and pts[-1].distance(Point(line_m.coords[-1])) > 1e-6:
        pts.append(Point(line_m.coords[-1]))
    return pts


def _max_gap_m_from_flags(sample_points_m: List[Point], flags: List[int]) -> float:
    if not sample_points_m or not flags or len(sample_points_m) != len(flags):
        return 0.0

    max_gap = 0.0
    cur_gap = 0.0

    for i in range(1, len(sample_points_m)):
        seg_len = float(sample_points_m[i - 1].distance(sample_points_m[i]))

        if flags[i - 1] == 0 and flags[i] == 0:
            cur_gap += seg_len
        elif flags[i - 1] == 0 and flags[i] == 1:
            cur_gap += seg_len
            max_gap = max(max_gap, cur_gap)
            cur_gap = 0.0
        elif flags[i - 1] == 1 and flags[i] == 0:
            cur_gap = seg_len
        else:
            max_gap = max(max_gap, cur_gap)
            cur_gap = 0.0

    max_gap = max(max_gap, cur_gap)
    return float(max_gap)


def _density_score(count: int, route_len_m: float, k_per_km: float) -> float:
    if route_len_m <= 0 or k_per_km <= 0:
        return 0.0
    route_len_km = route_len_m / 1000.0
    density = count / route_len_km
    return float(1.0 - math.exp(-density / k_per_km))


def _build_tree(points: List[Point]) -> Optional[STRtree]:
    if not points:
        return None
    return STRtree(points)


def _query_tree(tree: STRtree, geom, predicate: Optional[str] = None):
    try:
        if predicate:
            return tree.query(geom, predicate=predicate)
        return tree.query(geom)
    except TypeError:
        # shapely<2.0: predicate 미지원
        return tree.query(geom)


def _query_indices(
    tree: STRtree,
    geom,
    points: List[Point],
    predicate: Optional[str] = None,
) -> List[int]:
    res = _query_tree(tree, geom, predicate=predicate)
    if res is None or len(res) == 0:
        return []
    first = res[0]
    if isinstance(first, int):
        return list(res)

    idx_map = {id(p): i for i, p in enumerate(points)}
    out: List[int] = []
    for g in res:
        idx = idx_map.get(id(g))
        if idx is not None:
            out.append(idx)
    return out


def _covered_flags(
    sample_points_m: List[Point],
    infra_points_m: List[Point],
    infra_tree: Optional[STRtree],
    radius_m: float,
) -> List[int]:
    if not sample_points_m:
        return []
    if not infra_points_m:
        return [0] * len(sample_points_m)

    flags: List[int] = []
    for p in sample_points_m:
        if infra_tree is None:
            hit = any(q.distance(p) <= radius_m for q in infra_points_m)
            flags.append(1 if hit else 0)
            continue

        search = p.buffer(radius_m)
        idxs = _query_indices(infra_tree, search, infra_points_m, predicate="intersects")
        if not idxs:
            flags.append(0)
            continue
        hit = False
        for i in idxs:
            if infra_points_m[i].distance(p) <= radius_m:
                hit = True
                break
        flags.append(1 if hit else 0)
    return flags


def _count_within_corridor(
    corridor: Polygon,
    infra_points_m: List[Point],
    infra_tree: Optional[STRtree],
) -> int:
    if not infra_points_m:
        return 0
    if infra_tree is None:
        return sum(1 for p in infra_points_m if corridor.contains(p))
    idxs = _query_indices(infra_tree, corridor, infra_points_m, predicate="within")
    if idxs:
        return len(idxs)
    # shapely<2.0: predicate 미지원 → 후보 다시 필터
    cand = _query_indices(infra_tree, corridor, infra_points_m, predicate=None)
    return sum(1 for i in cand if corridor.contains(infra_points_m[i]))


def _latlng_route_to_line_m(
    route_coords: List[LatLng],
    transformer: Transformer,
) -> LineString:
    lonlat_list: List[LonLat] = [(c["lng"], c["lat"]) for c in route_coords]
    xy = _project_lonlat_list(lonlat_list, transformer)
    return LineString(xy)


def _points_from_latlng(
    points: List[LatLng],
    transformer: Transformer,
) -> List[Point]:
    coords = [(p["lng"], p["lat"]) for p in points]
    xy = _project_lonlat_list(coords, transformer)
    return [Point(x, y) for x, y in xy]


@lru_cache(maxsize=4)
def load_cctv_points(csv_path: str) -> List[Dict]:
    if not os.path.exists(csv_path):
        return []

    out: List[Dict] = []
    with open(csv_path, "r", encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            lat = row.get("lat")
            lon = row.get("lon") or row.get("lng")
            if lat is None or lon is None:
                continue
            try:
                out.append({"type": "cctv", "lat": float(lat), "lon": float(lon)})
            except ValueError:
                continue
    return out


@lru_cache(maxsize=4)
def load_lamp_points(csv_path: str) -> List[Dict]:
    if not os.path.exists(csv_path):
        return []

    out: List[Dict] = []
    with open(csv_path, "r", encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # 헤더: 관리번호,위도,경도
            lat = row.get("위도") or row.get("lat") or row.get("LAT")
            lon = row.get("경도") or row.get("lon") or row.get("lng") or row.get("LON")
            if lat is None or lon is None:
                continue
            try:
                out.append({"type": "lamp", "lat": float(lat), "lon": float(lon)})
            except ValueError:
                continue
    return out


def compute_safety_score(
    route_coords: List[LatLng],
    infra_points: List[Dict],
    params: Optional[SafetyParams] = None,
    debug: bool = False,
) -> Dict:
    if params is None:
        params = SafetyParams()

    transformer = _transformer(params.metric_crs)
    transformer_inv = Transformer.from_crs(params.metric_crs, "EPSG:4326", always_xy=True)
    route_line_m = _latlng_route_to_line_m(route_coords, transformer)
    route_len_m = float(route_line_m.length)

    lamp_points = [
        {"lat": r.get("lat"), "lng": r.get("lon", r.get("lng"))}
        for r in infra_points if r.get("type") == "lamp"
    ]
    cctv_points = [
        {"lat": r.get("lat"), "lng": r.get("lon", r.get("lng"))}
        for r in infra_points if r.get("type") == "cctv"
    ]

    lamp_points_m = _points_from_latlng(lamp_points, transformer)
    cctv_points_m = _points_from_latlng(cctv_points, transformer)

    lamp_tree = _build_tree(lamp_points_m)
    cctv_tree = _build_tree(cctv_points_m)

    corridor_lamp_m: Polygon = route_line_m.buffer(params.lamp_radius_m)
    corridor_cctv_m: Polygon = route_line_m.buffer(params.cctv_radius_m)

    lamp_count = _count_within_corridor(corridor_lamp_m, lamp_points_m, lamp_tree)
    cctv_count = _count_within_corridor(corridor_cctv_m, cctv_points_m, cctv_tree)

    lamp_density_score = _density_score(lamp_count, route_len_m, params.density_k_per_km)
    cctv_density_score = _density_score(cctv_count, route_len_m, params.density_k_per_km)
    density_score = float(0.5 * lamp_density_score + 0.5 * cctv_density_score)

    sample_points_m = _sample_points_along_line(route_line_m, params.sample_step_m)
    lamp_flags = _covered_flags(sample_points_m, lamp_points_m, lamp_tree, params.lamp_radius_m)
    cctv_flags = _covered_flags(sample_points_m, cctv_points_m, cctv_tree, params.cctv_radius_m)

    combined_flags = [
        1 if (lamp_flags[i] == 1 or cctv_flags[i] == 1) else 0
        for i in range(len(sample_points_m))
    ] if sample_points_m else []

    coverage_score = float(sum(combined_flags) / len(combined_flags)) if combined_flags else 0.0
    max_gap_m = _max_gap_m_from_flags(sample_points_m, combined_flags)
    gap_penalty = clamp(max_gap_m / params.gap_G_m, 0.0, 1.0)

    raw = (
        params.w_density * density_score +
        params.w_coverage * coverage_score -
        params.w_gap * gap_penalty
    )
    final01 = clamp(raw / params.rescale_max, 0.0, 1.0)
    final100 = round(final01 * 100.0, 1)

    result = {
        "score": final100,
        "raw01": final01,
        "features": {
            "route_len_m": round(route_len_m, 2),
            "lamp_count": lamp_count,
            "cctv_count": cctv_count,
            "density_score": round(density_score, 4),
            "coverage_score": round(coverage_score, 4),
            "max_gap_m": round(max_gap_m, 2),
            "gap_penalty": round(gap_penalty, 4),
        },
    }

    if not debug:
        return result

    sample_points_out: List[Dict] = []
    for i, p in enumerate(sample_points_m):
        lon, lat = transformer_inv.transform(p.x, p.y)
        sample_points_out.append({
            "lat": float(lat),
            "lng": float(lon),
            "covered": int(combined_flags[i]) if i < len(combined_flags) else 0,
        })

    corridors_out: Dict[str, List[Dict[str, float]]] = {}
    for kind, poly in (("lamp", corridor_lamp_m), ("cctv", corridor_cctv_m)):
        coords = list(poly.exterior.coords)
        out = []
        for x, y in coords:
            lon, lat = transformer_inv.transform(x, y)
            out.append({"lat": float(lat), "lng": float(lon)})
        corridors_out[kind] = out

    result["debug"] = {
        "sample_points": sample_points_out,
        "corridors": corridors_out,
    }
    return result
