# ============================================
# app/services/place_service.py - 장소 추천 서비스
# ============================================
# 주변 편의시설(카페/편의점/화장실 등) 조회 로직을 처리합니다.
# ============================================

from math import radians, cos, sin, asin, sqrt
from typing import List

from sqlalchemy.orm import Session

from app.models.route import Place
from app.schemas.route import PlaceSchema, PlaceBriefSchema, CoordinateSchema


def _haversine_distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    두 좌표 사이의 Haversine 거리(미터)를 계산합니다.
    """
    # 지구 반지름 (미터)
    r = 6371000.0
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    c = 2 * asin(sqrt(a))
    return r * c


class PlaceService:
    """
    장소 추천 서비스
    - 반경 내 장소 조회
    - 별점/리뷰 수 기준 정렬
    """

    def __init__(self, db: Session):
        self.db = db

    def get_nearby_places(
        self,
        center_lat: float,
        center_lng: float,
        category: str,
        radius_m: int = 1000,
        limit: int = 3,
    ) -> List[PlaceSchema]:
        """
        반경 내 장소를 조회하고 별점 높은 순으로 반환합니다.

        정렬 기준:
        1) rating 내림차순
        2) review_count 내림차순
        3) distance 오름차순
        """
        if radius_m <= 0:
            return []

        # 간단한 bounding box로 1차 필터링 (DB에서 후보 수 축소)
        lat_delta = radius_m / 111320.0
        lng_denom = 111320.0 * max(cos(radians(center_lat)), 1e-6)
        lng_delta = radius_m / lng_denom

        candidates = (
            self.db.query(Place)
            .filter(Place.is_active == True)
            .filter(Place.category == category)
            .filter(Place.latitude >= center_lat - lat_delta)
            .filter(Place.latitude <= center_lat + lat_delta)
            .filter(Place.longitude >= center_lng - lng_delta)
            .filter(Place.longitude <= center_lng + lng_delta)
            .all()
        )

        # Haversine으로 실제 반경 필터링
        within_radius = []
        for place in candidates:
            lat = float(place.latitude)
            lng = float(place.longitude)
            dist_m = _haversine_distance_m(center_lat, center_lng, lat, lng)
            if dist_m <= radius_m:
                within_radius.append((place, dist_m))

        # 별점 우선, 리뷰 수 우선, 거리 가까운 순으로 정렬
        within_radius.sort(
            key=lambda item: (
                -(float(item[0].rating) if item[0].rating is not None else 0.0),
                -(int(item[0].review_count) if item[0].review_count is not None else 0),
                item[1],
            )
        )

        results: List[PlaceSchema] = []
        for place, _dist_m in within_radius[:limit]:
            results.append(
                PlaceSchema(
                    id=str(place.id),
                    name=place.name,
                    category=place.category,
                    address=place.address,
                    rating=float(place.rating) if place.rating is not None else None,
                    review_count=int(place.review_count) if place.review_count is not None else None,
                    icon=place.icon,
                    color=place.color,
                    location=CoordinateSchema(
                        lat=float(place.latitude),
                        lng=float(place.longitude),
                    ),
                )
            )

        return results

    def get_nearby_places_brief(
        self,
        center_lat: float,
        center_lng: float,
        category: str,
        radius_m: int = 1000,
        limit: int = 3,
    ) -> List[PlaceBriefSchema]:
        """
        반경 내 장소를 조회하고 요약 형태로 반환합니다.
        - 별점 높은 순
        - {위도, 경도, 별점, 이름, 특징} 포맷
        """
        places = self.get_nearby_places(
            center_lat=center_lat,
            center_lng=center_lng,
            category=category,
            radius_m=radius_m,
            limit=limit,
        )

        results: List[PlaceBriefSchema] = []
        for place in places:
            feature = place.address or place.icon or place.category
            results.append(
                PlaceBriefSchema(
                    name=place.name,
                    rating=place.rating,
                    feature=feature,
                    lat=place.location.lat,
                    lng=place.location.lng,
                )
            )
        return results
