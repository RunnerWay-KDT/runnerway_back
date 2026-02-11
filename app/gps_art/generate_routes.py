from typing import List, Dict, Tuple, Optional, Callable
from .road_network import RoadNetworkFetcher
from .gps_art_router import GPSArtRouter
from concurrent.futures import ProcessPoolExecutor, as_completed
import os

# 프론트에서 보내줄 그림 포인트 형식:
# drawing_points = [{"lat": 37.5007, "lng": 127.0369}, ...]
LonLat = Tuple[float, float]

_worker_graph = None
_worker_drawing_lonlat = None
_worker_sampled = None
_worker_start_lon = None
_worker_start_lat = None
_worker_effective_target_km = None
_worker_n_placements = None
_worker_return_node_paths = None

def _init_worker(graph, drawing_lonlat, sampled, start_lon, start_lat, effective_target_km, n_placements, return_node_paths):
    global _worker_graph, _worker_drawing_lonlat, _worker_sampled
    global _worker_start_lon, _worker_start_lat, _worker_effective_target_km
    global _worker_n_placements, _worker_return_node_paths
    _worker_graph = graph
    _worker_drawing_lonlat = drawing_lonlat
    _worker_sampled = sampled
    _worker_start_lon = start_lon
    _worker_start_lat = start_lat
    _worker_effective_target_km = effective_target_km
    _worker_n_placements = n_placements
    _worker_return_node_paths = return_node_paths

def _run_one_candidate(task):
    k, angle = task
    router = GPSArtRouter(_worker_graph)
    fetcher = RoadNetworkFetcher(timeout=30)

    point_at_k = _worker_sampled[k]
    placed_k = router.translate_coordinates(
        _worker_drawing_lonlat,
        (_worker_start_lon - point_at_k[0], _worker_start_lat - point_at_k[1]),
    )
    rotated = router.rotate_coordinates(
        placed_k,
        center=(_worker_start_lon, _worker_start_lat),
        angle_degrees=angle,
    )
    scaled_factor = 0.80
    scaled = router.scale_drawing_coordinates(
        rotated,
        start_point=(_worker_start_lon, _worker_start_lat),
        target_distance=_worker_effective_target_km * 1000 * scaled_factor,
    )
    wp_nodes = router._compute_waypoint_nodes(
        start_point=(_worker_start_lon, _worker_start_lat),
        drawing_polyline=scaled,
        n_samples=_worker_n_placements,
    )
    if not wp_nodes:
        return None

    # 세그먼트당 A* 1회만 수행 후, start_inx별로 캐시된 세그먼트만 이어붙여 중복 제거
    segment_paths = router._compute_segment_paths(wp_nodes)
    if not segment_paths:
        return None 

    best_sim = float('inf')
    best_node_path = None
    for start_idx in range(len(wp_nodes)):
        node_path_k = router.build_full_path(segment_paths, start_idx)
        if not node_path_k:
            continue
        info_k = fetcher.get_path_info(_worker_graph, node_path_k)
        sim_k = router.calculate_route_similarity(
            original_drawing=scaled,
            generated_route=info_k["coordinates"],
        )
        if sim_k < best_sim:
            best_sim = sim_k
            best_node_path = node_path_k

    if best_node_path is None:
        return None

    info = fetcher.get_path_info(_worker_graph, best_node_path)
    candidate = {
        "id": 1,
        "angle": float(angle),
        "distance_m": info["distance"],
        "distance_km": info["distance_km"],
        "coordinates": info["coordinates"],
        "similarity_score": best_sim,
    }
    if _worker_return_node_paths:
        candidate["node_path"] = best_node_path

    return (float(angle), scaled, candidate)

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
    return_node_paths: bool = True, # True면 각 route에 node_path(그래프 노드 ID 리스트) 포함
    on_progress: Optional[Callable[[int, str], None]] = None, # 진행 상태 콜백 (퍼센트, 단계 텍스트)
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
    
    if on_progress:
        on_progress(10, "processing")

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

    if on_progress:
        on_progress(12, "processing")

    # 로테이션 각도 설정
    if enable_rotation:
        angles = rotation_angles or [i for i in range(-180, 180, 10)]
    else:
        angles = [0.0]

    def _run_with_target(effective_target_km: float) -> Dict:
         # (각도, k) 조합마다 후보 전부 수집: (angle, scaled, route_dict)
        all_candidates: List[Tuple[float, List[LonLat], Dict]] = []

        n_placements = 30 # K: 선분 위 후보 점 개수 (코/꼬리/몸통 등)
        sampled = router._sample_polyline_evenly(drawing_lonlat, n_samples=n_placements)

        # (K 배치 전수 조사) → 각 배치마다 회전 → 스케일 → 유사도 평가
        tasks = [
            (k, angle) for k in range(len(sampled)) for angle in angles
        ]
        initargs = (
            graph,
            drawing_lonlat,
            sampled,
            start_lon,
            start_lat,
            effective_target_km,
            n_placements,
            return_node_paths,
        )
        max_workers = min(os.cpu_count() or 4, len(tasks), 8)

        if on_progress:
            on_progress(15, "processing")

        with ProcessPoolExecutor(
            max_workers=max_workers,
            initializer=_init_worker,
            initargs=initargs,
        ) as executor:
            futures = {executor.submit(_run_one_candidate, t): t for t in tasks}
            done = 0
            last_reported_percent = 0
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result is not None:
                        all_candidates.append(result)
                except Exception:
                    pass
                done += 1
                
                if on_progress and len(tasks) > 0:
                    percent = 10 + int(70 * done / len(tasks))
                    if percent - last_reported_percent >= 5:
                        last_reported_percent = percent
                        on_progress(min(percent, 80), "processing")

            if on_progress:
                on_progress(85, "processing")
                
        # 각도별 1등을 유사도로 정렬 후 상위 3개를 최종 routes로
        all_candidates.sort(key=lambda x: x[2]["similarity_score"])
        top3 = all_candidates[:3]
        best_routes = [item[2] for item in top3]
        for i, r in enumerate(best_routes, start=1):
            r["id"] = i

        if on_progress:
            on_progress(92, "processing")

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

        if on_progress:
            on_progress(99, "processing")

        return {
            "routes": best_routes,
            "scaled_drawing": scale_drawing_for_kakao,
            "best_angle": best_angle,
            "validation": validation,
        }
    
    result = _run_with_target(target_distance_km)

    return result