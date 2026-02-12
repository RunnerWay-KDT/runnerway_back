from __future__ import annotations # 순환 참조 문제 방지

from typing import Any, Dict, Optional, List, Callable
from sqlalchemy.orm import Session

from app.core.exceptions import ValidationException
from app.gps_art.generate_routes import generate_routes
from app.models.route import Route, RouteOption, RouteShape
from app.utils.safety_score import calculate_safety_score


def generate_gps_art_impl(
    *, 
    body: dict, 
    user_id: str, 
    db: Session, 
    on_progress: Optional[Callable[[int, str], None]] = None,
) -> dict:
    route_id_from_body = body.get("route_id")
    shape_id = body.get("shape_id")
    target_km = float(body.get("target_distance_km", 5.0))
    enable_rotation = body.get("enable_rotation", True)
    rotation_angles = body.get("rotation_angles")

    # 커스텀: route_id 있음
    if route_id_from_body:
        route = db.query(Route).filter(
            Route.id == route_id_from_body,
            Route.user_id == user_id,
        ).first()
        if not route:
            raise ValidationException(message="해당 경로를 찾을 수 없습니다.", field="route_id")
        if not route.svg_path:
            raise ValidationException(message="해당 경로에 SVG 데이터가 없습니다.", field="route_id")

        start_lat = float(route.start_latitude)
        start_lon = float(route.start_longitude)
        svg_path = route.svg_path

        result = generate_routes(
            start_lat=start_lat,
            start_lon=start_lon,
            svg_path=svg_path,
            target_distance_km=target_km,
            mode="custom",
            shape_id=None,
            enable_rotation=enable_rotation,
            rotation_angles=rotation_angles,
            on_progress=on_progress,
        )
        route_id = route.id

    # 프리셋: shape_id 있음
    elif shape_id:
        shape = db.query(RouteShape).filter(
            RouteShape.id == shape_id,
            RouteShape.is_active == True,
        ).first()

        # DB에 shape 행이 없으면, body.svg_path를 이용해 새로 등록
        if not shape:
            svg_path_from_body = (body.get("svg_path") or "").strip()
            if not svg_path_from_body:
                raise ValidationException(
                    message="프리셋 도형 정보가 없습니다. svg_path가 필요합니다.",
                    field="shape_id",
                )

            shape = RouteShape(
                id=shape_id,
                name=body.get("shape_name") or shape_id,
                icon_name=body.get("icon_name") or shape_id,
                category=body.get("category") or "shape",
                estimated_distance=body.get("target_distance_km"),
                svg_path=svg_path_from_body,
                is_active=True,
            )
            db.add(shape)
            db.commit()
            db.refresh(shape)

        # 여기서부터는 항상 shape가 존재하는 상태
        svg_path = (shape.svg_path or "").strip() or (body.get("svg_path") or "").strip()
        if not svg_path:
            raise ValidationException(
                message="해당 도형에 SVG 경로가 없습니다.", 
                field="shape_id"
            )

        # DB에 없었으면 body에서 받은 값 저장 (원하면 유지)
        if not (shape.svg_path or "").strip():
            shape.svg_path = svg_path
            db.commit()

        start = body.get("start", {})
        start_lat = float(start.get("lat", 37.5))
        start_lon = float(start.get("lng", 127.0))

        result = generate_routes(
            start_lat=start_lat,
            start_lon=start_lon,
            svg_path=svg_path,
            target_distance_km=target_km,
            mode="shape",
            shape_id=shape_id,
            enable_rotation=enable_rotation,
            rotation_angles=rotation_angles,
            on_progress=on_progress,
        )

        route = Route(
            user_id=user_id,
            shape_id=shape_id,
            name=f"{shape.name} 경로",
            type="preset",
            mode=body.get("mode") or "none",
            start_latitude=start_lat,
            start_longitude=start_lon,
            svg_path=None,
            status="active",
        )
        db.add(route)
        db.flush()
        route_id = route.id

    # 그 외: route_id 없이 커스텀(바로 생성)
    else:
        svg_path = (body.get("svg_path") or "").strip()
        if not svg_path:
            raise ValidationException(
                message="커스텀 그리기 시 svg_path 또는 route_id가 필요합니다.",
                field="svg_path",
            )

        start = body.get("start", {})
        start_lat = float(start.get("lat", 37.5))
        start_lon = float(start.get("lng", 127.0))

        result = generate_routes(
            start_lat=start_lat,
            start_lon=start_lon,
            svg_path=svg_path,
            target_distance_km=target_km,
            mode="custom",
            shape_id=None,
            enable_rotation=enable_rotation,
            rotation_angles=rotation_angles,
            on_progress=on_progress,
        )

        route = Route(
            user_id=user_id,
            shape_id=None,
            name=body.get("name") or "커스텀 경로",
            type="custom",
            mode=body.get("mode") or "none",
            start_latitude=start_lat,
            start_longitude=start_lon,
            svg_path=svg_path,
            status="active",
        )
        db.add(route)
        db.flush()
        route_id = route.id

    # 공통: RouteOption 3건 생성
    option_names = ["1순위 (가장 유사)", "2순위", "3순위"]
    tags = ["BEST", "추천", None]
    option_ids: List[str] = []

    routes_list = result["routes"]
    distances_with_idx = [(i, float(r.get("distance_km", 0))) for i, r in enumerate(routes_list)]
    distances_with_idx.sort(key=lambda x: x[1])
    difficulty_by_idx = {
        distances_with_idx[0][0]: "짧은 코스",
        distances_with_idx[1][0]: "보통",
        distances_with_idx[2][0]: "긴 코스",
    }

    for i, r in enumerate(result["routes"]):
        coords = r.get("coordinates", [])
        distance_km = float(r.get("distance_km", 0))
        difficulty = difficulty_by_idx[i]

        # 안전점수 계산 (DB의 cctvs, lights 테이블 기반)
        safety = calculate_safety_score(coords, db)

        opt = RouteOption(
            route_id=route_id,
            option_number=i + 1,
            name=option_names[i],
            distance=distance_km,
            estimated_time=max(1, int(round(distance_km * 5))),
            difficulty=difficulty,
            tag=tags[i],
            coordinates=coords,
            safety_score=safety,
            max_elevation_diff=0,
            lighting_score=0,
        )
        db.add(opt)
        db.flush()
        option_ids.append(str(opt.id))

    return {
        "route_id": str(route_id),
        "option_ids": option_ids,
    }