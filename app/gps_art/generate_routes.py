from typing import List, Dict, Tuple, Optional

from fsspec.caching import P
from road_network import RoadNetworkFetcher
from gps_art_router import GPSArtRouter

# 프론트에서 보내줄 그림 포인트 형식:
# drawing_points = [{"lat": 37.5007, "lng": 127.0369}, ...]
LonLat = Tuple[float, float]

# svg_path + 시작점 + 목표거리 → 보행자 도로 위 GPS 아트 경로 3개 생성
def generate_routes(
    start_lat: float,
    start_lon: float,
    svg_path: str,
    target_distance_km: float,
    mode: str = "custom", # "custom" or "shape"
    shape_id: Optional[str] | None = None,
    enable_rotation: bool = True,
    rotation_angles: Optional[List[float]] = [i for i in range(-180, 180, 10)],
    length_feedback: bool = True, # True면 1회 실행 후 거리 보정해 최대 2회 실행
    return_node_paths: bool = True, # True면 각 route에 node_path(그래프 노드 ID 리스트) 포함
) -> Dict:
    """
    Args:
        start_lat: 시작점 위도
        start_lon: 시작점 경도
        target_distance_km: 목표 거리 (km)
        mode: 경로 모드 (custom 또는 shape)
        shape_id: 프리셋 도형 ID
        svg_path: SVG 경로 문자열
        enable_rotation: 회전 활성화 여부
        rotation_angles: 회전 각도 리스트
        length_feedback: 거리 보정 활성화 여부
        
    Returns:
        {
          "routes": [
            {
              "id": 1,
              "angle": 30.0,
              "distance_m": ...,
              "distance_km": ...,
              "coordinates": [{lat,lng}, ...],
              "similarity_score": ...,
            },
            ...
          ],
          "scaled_drawing": [{lat,lng}, ...],  # 최종 스케일+로테이션된 이론적 그림
          "best_angle": 30.0,
          "validation": {...},                 # 거리 검증 등 (원하면 포함)
        }
    """

    # 보행자 도로 그래프 로드 (시작점 기준 target_distance의 1.5배 반경)
    fetcher = RoadNetworkFetcher(timeout=30)
    graph = fetcher.fetch_pedestrian_network_from_point(
        center_point=(start_lat, start_lon),
        distance=target_distance_km * 1500, # 미터 단위 변경 (1.5배)
        network_type="walk",
        simplify=False, # 횡단보도 등 유지
    )
    router = GPSArtRouter(graph)

    # svg_path -> Canvas -> Geo(drawing_points)
    canvas_points = router.parse_svg_path_to_canvas_coordinates(svg_path)
    drawing_points = router.convert_canvas_to_geographic(
        canvas_points,
        start_lat,
        start_lon,
    )
    # (lon, lat) 튜플 리스트로 반환
    drawing_lonlat: List[LonLat] = [
        (p["lon"], p["lat"]) for p in drawing_points
    ]

    # 그림 최소 거리 계산 + 유효성 체크
    min_dist_m = fetcher.calculate_drawing_minimum_distance(drawing_lonlat)
    validation = fetcher.validate_target_distance(
        minimum_distance=min_dist_m,
        target_distance=target_distance_km * 1000,
    )

    # 로테이션 각도 설정
    if enable_rotation:
        angles = rotation_angles or [0, 15, 30, 45, 60, -15, -30, -45]
    else:
        angles = [0.0]

    def _run_with_target(effective_target_km: float) -> Dict:
         # (각도, k) 조합마다 후보 전부 수집: (angle, scaled, route_dict)
        all_candidates: List[Tuple[float, List[LonLat], Dict]] = []

        n_placements = 30 # K: 선분 위 후보 점 개수 (코/꼬리/몸통 등)
        sampled = router._sample_polyline_evenly(drawing_lonlat, n_samples=n_placements)

        # (K 배치 전수 조사) → 각 배치마다 회전 → 스케일 → 유사도 평가
        for k in range(len(sampled)):
            # K 배치: k번째 점이 출발지에 오도록 평행이동만
            point_at_k = sampled[k]
            placed_k = router.translate_coordinates(
                drawing_lonlat,
                (start_lon - point_at_k[0], start_lat - point_at_k[1]),
            )

            for angle in angles:
                # 회전: 출발지(현재 위치) 기준
                rotated = router.rotate_coordinates(
                    placed_k,
                    center=(start_lon, start_lat),
                    angle_degrees=angle,
                )
                # 스케일: 출발지 기준, 목표 거리
                scaled = router.scale_drawing_coordinates(
                    rotated,
                    start_point=(start_lon, start_lat),
                    target_distance=effective_target_km * 1000,
                )
                # 유사도 평가: 
                wp_nodes = router._compute_waypoint_nodes(
                    start_point=(start_lon, start_lat),
                    drawing_polyline=scaled,
                    n_samples=n_placements,
                )
                if not wp_nodes:
                    continue

            # 시작 인덱스 k마다 경로 생성 후 유사도 계산 -> 최고인 k만 사용
            best_sim = float('inf')
            best_node_path = None
            for k in range(len(wp_nodes)):
                node_path_k = router.build_full_path(wp_nodes, k)
                if not node_path_k:
                    continue
                info_k = fetcher.get_path_info(graph, node_path_k)
                sim_k = router.calculate_route_similarity(
                    original_drawing=scaled,
                    generated_route=info_k["coordinates"],
                )
                if sim_k < best_sim:
                    best_sim = sim_k
                    best_node_path = node_path_k

            if best_node_path is None:
                continue

            info = fetcher.get_path_info(graph, best_node_path)            
            candidate = {
                "id": 1,
                "angle": float(angle),
                "distance_m": info["distance"],
                "distance_km": info["distance_km"],
                "coordinates": info["coordinates"],
                "similarity_score": best_sim,
            }
            if return_node_paths:
                candidate["node_path"] = best_node_path
            all_candidates.append((float(angle), scaled, candidate))
                
        # 각도별 1등을 유사도로 정렬 후 상위 3개를 최종 routes로
        all_candidates.sort(key=lambda x: x[2]["similarity_score"])
        top3 = all_candidates[:3]
        best_routes = [item[2] for item in top3]
        for i, r in enumerate(best_routes, start=1):
            r["id"] = i

        # top3 각 경로에 해당 각도의 원본 path(scaled_drawing) 추가
        for item, r in zip(top3, best_routes):
            _, scaled, _ = item
            r["scaled_drawing"] = [{"lat": lat, "lng": lon} for (lon, lat) in scaled]

        # 상위 1개 경로의 각도/스케일로 scaled_drawing, best_angle 결정
        best_angle = 0.0
        best_scaled: List[LonLat] = drawing_lonlat
        if top3:
            best_angle = top3[0][0]
            best_scaled = top3[0][1]

        # 최종 스케일+로테이션된 그림을 kakao용 포맷으로
        scale_drawing_for_kakao = [
            {"lat": lat, "lng": lon} for (lon, lat) in best_scaled
        ]

        return {
            "routes": best_routes,
            "scaled_drawing": scale_drawing_for_kakao,
            "best_angle": best_angle,
            "validation": validation,
        }
    
    result = _run_with_target(target_distance_km)

    if length_feedback and result.get("routes"):
        best_route = min(
            result["routes"],
            key=lambda r: r["similarity_score"],
        )
        actual_km = best_route["distance_km"]
        ratio = actual_km / target_distance_km if target_distance_km > 0 else 1.0
        if ratio > 1.12 or ratio < 0.88: # 12% 이상 오차 시 한 번만 보정
            adjusted_target_km = target_distance_km * target_distance_km / actual_km
            result = _run_with_target(adjusted_target_km)

    return result