# ============================================
# app/utils/safety_score.py - 안전점수 계산 유틸리티
# ============================================
# DB의 cctvs, lights 테이블에서 좌표를 조회하고,
# 경로의 커버리지 기반 안전점수(0~100)를 계산합니다.
# ============================================

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
from shapely.geometry import LineString, Point
from shapely.strtree import STRtree
from pyproj import Transformer
from sqlalchemy.orm import Session

from app.models.safety import Cctv, Light


# ---------- 타입 별칭 ----------
LatLng = Dict[str, float]       # {"lat": .., "lng": ..}
LonLat = Tuple[float, float]    # (lon, lat)


# ---------- 파라미터 ----------
@dataclass
class SafetyParams:
    # 샘플링 간격(m): 경로를 이 간격으로 잘라 포인트를 생성
    sample_step_m: float = 20.0

    # 레이어별 커버 반경(m)
    lamp_radius_m: float = 15.0
    cctv_radius_m: float = 50.0

    # 투영 좌표계 (미터 단위)
    metric_crs: str = "EPSG:5179"


# ============================================
# 내부 헬퍼 함수
# ============================================

def _transformer(metric_crs: str) -> Transformer:
    return Transformer.from_crs("EPSG:4326", metric_crs, always_xy=True)


def _project_lonlat_list(
    coords: Iterable[LonLat],
    transformer: Transformer,
) -> List[Tuple[float, float]]:
    return [transformer.transform(lon, lat) for lon, lat in coords]


def _sample_points_along_line(line_m: LineString, step_m: float) -> List[Point]:
    """경로(미터 좌표)를 step_m 간격으로 샘플링하여 Point 리스트 반환"""
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
    if isinstance(first, (int, np.integer)):
        return [int(x) for x in res]

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
    """각 샘플 포인트가 인프라 반경 내에 있으면 1, 아니면 0"""
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


# ============================================
# DB에서 인프라 데이터 조회
# ============================================

def _load_infra_from_db(db: Session) -> List[Dict]:
    """
    DB의 cctvs, lights 테이블에서 모든 좌표를 조회하여
    compute_safety_score에 전달할 infra_points 형태로 반환합니다.
    """
    infra: List[Dict] = []

    # CCTV 조회
    cctvs = db.query(Cctv.latitude, Cctv.longitude).all()
    for row in cctvs:
        infra.append({
            "type": "cctv",
            "lat": float(row.latitude),
            "lon": float(row.longitude),
        })

    # 가로등(보안등) 조회
    lights = db.query(Light.latitude, Light.longitude).all()
    for row in lights:
        infra.append({
            "type": "lamp",
            "lat": float(row.latitude),
            "lon": float(row.longitude),
        })

    return infra


# ============================================
# 핵심 계산 함수
# ============================================

def compute_safety_score(
    route_coords: List[LatLng],
    infra_points: List[Dict],
    params: Optional[SafetyParams] = None,
) -> Dict:
    """
    경로 좌표와 인프라 포인트를 받아 커버리지 기반 안전점수를 계산합니다.

    Args:
        route_coords: [{"lat": float, "lng": float}, ...] 경로 좌표 배열
        infra_points: [{"type": "cctv"|"lamp", "lat": float, "lon": float}, ...] 인프라 좌표
        params: 계산 파라미터

    Returns:
        {"score": 0~100, "covered_points": int, "total_points": int}
    """
    if params is None:
        params = SafetyParams()

    if not route_coords or len(route_coords) < 2:
        return {"score": 0, "covered_points": 0, "total_points": 0}

    transformer = _transformer(params.metric_crs)
    route_line_m = _latlng_route_to_line_m(route_coords, transformer)

    # 인프라 포인트를 lamp / cctv 로 분리
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

    # 경로를 샘플링하여 각 포인트의 커버 여부 판정
    sample_points_m = _sample_points_along_line(route_line_m, params.sample_step_m)
    lamp_flags = _covered_flags(sample_points_m, lamp_points_m, lamp_tree, params.lamp_radius_m)
    cctv_flags = _covered_flags(sample_points_m, cctv_points_m, cctv_tree, params.cctv_radius_m)

    combined_flags = [
        1 if (lamp_flags[i] == 1 or cctv_flags[i] == 1) else 0
        for i in range(len(sample_points_m))
    ] if sample_points_m else []

    # 단순 커버리지: 커버된 포인트 / 전체 포인트 × 100
    covered = sum(combined_flags)
    total = len(combined_flags)
    score = round((covered / total) * 100.0, 1) if total > 0 else 0.0

    return {
        "score": score,
        "covered_points": covered,
        "total_points": total,
    }


# ============================================
# 외부에서 호출하는 편의 함수
# ============================================

def calculate_safety_score(
    route_coords: List[LatLng],
    db: Session,
    params: Optional[SafetyParams] = None,
) -> int:
    """
    DB에서 인프라 데이터를 조회하고 경로의 안전점수(0~100 정수)를 반환합니다.

    Args:
        route_coords: [{"lat": float, "lng": float}, ...] 경로 좌표
        db: SQLAlchemy DB 세션
        params: 계산 파라미터 (기본값 사용 시 None)

    Returns:
        int: 안전점수 (0~100)
    """
    if not route_coords or len(route_coords) < 2:
        return 0

    infra_points = _load_infra_from_db(db)

    if not infra_points:
        return 0

    result = compute_safety_score(route_coords, infra_points, params)
    return int(round(result["score"]))
