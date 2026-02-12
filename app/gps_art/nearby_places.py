from typing import Dict, List, Any
from sqlalchemy.orm import Session

from app.models.route import Place
from .road_network import haversine_distance

# 경로 좌표 기준 반경 500m 이내 places 조회 (cafe /convenience)
def get_places_ids(
    db: Session,
    coordinates: List[Dict[str, float]],
    radius_m: float = 50,
) -> Dict[str, List[str]]:
    """
    반환: {"cafe": [place_id, ...], "convenience": [place_id, ...]}
    """
    result: Dict[str, List[str]] = {"cafe": [], "convenience": []}
    if not coordinates:
        return result

    places = db.query(Place).filter(Place.is_active == True).all()
    for place in places:
        try:
            lat = float(place.latitude)
            lon = float(place.longitude)
        except (TypeError, ValueError):
            continue
        place_pos = (lon, lat)
        min_dist = float('inf')
        for c in coordinates:
            try:
                clat = float(c.get("lat", 0))
                clng = float(c.get("lng", 0))
            except (TypeError, ValueError):
                continue
            d = haversine_distance(place_pos, (clng, clat))
            if d < min_dist:
                min_dist = d
        if min_dist > radius_m:
            continue
        cat = (place.category or "").strip().lower()
        if cat == "cafe" and str(place.id) not in result["cafe"]:
            result["cafe"].append(str(place.id))
        elif cat == "convenience" and str(place.id) not in result["convenience"]:
            result["convenience"].append(str(place.id))
    return result
