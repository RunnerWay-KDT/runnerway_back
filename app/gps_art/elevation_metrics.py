from typing import List, Dict, Any
import math, logging

logger = logging.getLogger(__name__)

# 최종 선택된 경로의 좌표만으로 SRTM을 이용해 고도/경사도 메트릭을 계산

def _haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000 # 지구 반지름 (미터)
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return R * c

def compute_route_elevation_metrics(
    coordinates: List[Dict[str, float]]
) -> Dict[str, float]:
    """
    한 경로의 coordinates [{"lat", "lng"}, ...]에 대해 SRTM으로 고도를 조회하고
    route 스키마용 6개 메트릭을 계산합니다.

    Returns:
        max_elevation_diff, total_ascent, total_descent, total_elevation_change,
        average_grade, max_grade
    """
    if not coordinates or len(coordinates) < 2:
        return {
            "max_elevation_diff": 0,
            "total_ascent": 0.0,
            "total_descent": 0.0,
            "total_elevation_change": 0.0,
            "average_grade": 0.0,
            "max_grade": 0.0,
        }

    try:
        from app.services.elevation_service import ElevationService
        es = ElevationService()
        coords_tuples = [(float(c["lat"]), float(c["lng"])) for c in coordinates]
        elevations_map = es.get_elevations_batch(coords_tuples)
        elevations = [elevations_map.get((lat, lon), 0.0) for lat, lon in coords_tuples]
    except Exception as e:
        logger.warning(f"STRM 조회 실패", e)
        return {
            "max_elevation_diff": 0,
            "total_ascent": 0.0,
            "total_descent": 0.0,
            "total_elevation_change": 0.0,
            "average_grade": 0.0,
            "max_grade": 0.0,
        }

    total_ascent = 0.0
    total_descent = 0.0
    total_elevation_change = 0.0
    grades = []

    for i in range(len(coordinates) - 1):
        elev_u, elev_v = float(elevations[i]), float(elevations[i + 1])
        diff = elev_v - elev_u
        dist = _haversine_meters(
            coords_tuples[i][0], coords_tuples[i][1],
            coords_tuples[i + 1][0], coords_tuples[i + 1][1],
        )
        if dist < 0.1:
            dist = 0.1
        total_elevation_change += abs(diff)
        if diff > 0:
            total_ascent += diff
        else:
            total_descent += abs(diff)
        grade_ratio = diff / dist
        grades.append(abs(grade_ratio) * 100)

    max_elev_diff = max(elevations) - min(elevations) if elevations else 0
    avg_grade = (sum(grades) / len(grades)) if grades else 0.0
    max_grade = max(grades) if grades else 0.0
    
    return {
        "max_elevation_diff": int(round(max_elev_diff)),
        "total_ascent": round(total_ascent, 2),
        "total_descent": round(total_descent, 2),
        "total_elevation_change": round(total_elevation_change, 2),
        "average_grade": round(min(avg_grade, 99.99), 2),
        "max_grade": round(min(max_grade, 99.99), 2),
    }