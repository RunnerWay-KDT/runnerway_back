import osmnx as ox
import networkx as nx
from typing import Tuple, List, Optional, Dict
from sqlalchemy.orm import Session
import logging
from math import radians, cos, sin, asin, sqrt

# 로깅 설정
logger = logging.getLogger(__name__)

# OSMnx를 사용한 도로 네트워크 추출
class RoadNetworkFetcher:
    def __init__(self, timeout: int = 30):
        # OSMnx 설정
        ox.settings.use_cache = True
        ox.settings.log_console = False # 콘솔 로그 너무 많지 않게 조정
        ox.settings.timeout = timeout
        self.timeout = timeout

    # 출발지 좌표를 중심으로 반경 내 보행자 도로 네트워크를 추출
    def fetch_pedestrian_network_from_point (
        self,
        center_point: Tuple[float, float], # (latitude, longitude)
        distance: float = 1000, # 미터 단위 반경
        network_type: str = 'walk',
        simplify: bool = True
    ) -> nx.Graph:
        """
        Args:
            center_point: (위도, 경도) 튜풀
            distance: 중심점으로부터의 거리 (미터)
            network_type: 'walk', 'bike', 'drive', 'all'
            simplify: True면 불필요한 중간 노드 제거, False면 모든 노드 유지

        Returns:
            NetworkX 그래프 객체 (무방향)
        """
        lat, lon = center_point
        if not (-90 <= lat <= 90):
            raise ValueError(f"Invalid latitude: {lat}. Must be between -90 and 90")
        if not (-180 <= lon <= 180):
            raise ValueError(f"Invalid longitude: {lon}. Must be between -180 and 180")

        try:
            # OSMnx로 도로 네트워크 가져오기
            G = ox.graph_from_point(
                center_point=(lat, lon),
                dist=distance,
                network_type=network_type,
                simplify=simplify,
                retain_all=False, # 연결되지 않은 작은 컴포넌트 제거
                truncate_by_edge=False # 경계 처리 방식
            )

            # logger.info(f"Fetched graph with {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

            # 후처리: MultiDiGraph -> Graph 변환 및 pos 속성 추가
            G = self._postprocess_graph(G)

            # logger.info(f"Built graph with {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

            return G
        except Exception as e:
            logger.error(f"OSMnx API error: {e}")
            raise

    # 경계 박스 내 보행자 도로 네트워크를 추출
    def fetch_pedestrian_network_from_bbox(
        self,
        bbox: List[float], # [south, west, north, east]
        network_type: str = 'walk',
        simplify: bool = True
    ) -> nx.Graph:
        """
        Args:
            bbox: [south, west, north, east] 형식의 경계 박스
            network_type: 'walk', 'bike', 'drive', 'all'
            simplify: True면 불필요한 중간 노드 제거, False면 모든 노드 유지
        Returns:
            NetworkX 그래프 객체 (무방향)
        """
        # BBox 검증
        self._validate_bbox(bbox)

        south, west, north, east = bbox
        
        logger.info(f"Fetching {network_type} network from bbox: {bbox}")

        try:
            # OSMnx로 도로 네트워크 가져오기
            G = ox.graph_from_bbox(
                north=north,
                south=south,
                east=east,
                west=west,
                network_type=network_type,
                simplify=simplify,
                retain_all=False, # 연결되지 않은 작은 컴포넌트 제외
                truncate_by_edge=False
            )
            # logger.info(f"Fetched graph with {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

            # 후처리: MultiDiGraph -> Graph 변환 및 pos 속성 추가
            G = self._postprocess_graph(G)

            # logger.info(f"Built graph with {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

            return G
        except Exception as e:
            logger.error(f"OSMnx API error: {e}")
            raise

    # OSMnx가 반환한 MultiDiGraph를 무방향 Graph로 변환하고,
    # 모든 노드에 pos 속성을 추가한다.
    def _postprocess_graph(self, G: nx.MultiDiGraph) -> nx.Graph:
        """
        Args:
            G: OSMnx가 반환한 MultiDiGraph 객체
        Returns:
            무방향 Graph (모든 노드에 pos 속성 포함)
        """
        # MultiDiGraph -> 무방향 Graph 변환
        G_undirected = G.to_undirected()

        # 모든 노드에 pos 속성 추가 (gps_art_router.py 호환성)
        # OSMnx는 노드에 'x'(경도), 'y'(위도) 속성을 가지고 있음
        for node_id, data in G_undirected.nodes(data=True):
            if 'x' in data and 'y' in data:
                # pos는 (lon, lat) 형식
                data['pos'] = (data['x'], data['y'])
                # lat, lon도 별도로 유지 (호환성)
                data['lon'] = data['x']
                data['lat'] = data['y']
            else:
                logger.warning(f"Node {node_id} missing x/y coordinates")

        # 고립된 노드 제거 (경로 생성에 사용 불가)
        isolated = list(nx.isolates(G_undirected))

        if isolated:
            # logger.info(f"Removing {len(isolated)} isolated nodes")
            G_undirected.remove_nodes_from(isolated)

        return G_undirected

    # 고도 데이터 추가 (비동기 지원)
    async def add_elevation_to_nodes_async(
        self, 
        G: nx.Graph, 
        api_key: Optional[str] = None,
        db: Optional[Session] = None
    ) -> nx.Graph:
        """
        노드에 고도(elevation) 데이터를 비동기로 추가합니다 (캐시 우선).
        """
        if api_key and db:
            logger.info("Using ElevationService with DB Cache...")
            from app.services.elevation_service import ElevationService
            elevation_service = ElevationService(db, api_key)
            
            # 모든 노드 좌표 추출
            all_nodes = list(G.nodes())
            coordinates = [(G.nodes[node]['y'], G.nodes[node]['x']) for node in all_nodes]
            
            # 배치 조회 (캐시 활용)
            elevations = await elevation_service.get_elevations_batch(coordinates)
            
            # 노드에 반영
            for node in all_nodes:
                lat, lon = G.nodes[node]['y'], G.nodes[node]['x']
                G.nodes[node]['elevation'] = elevations.get((lat, lon), 20.0)
                
            logger.info(f"Elevation update completed using cache/API.")
        elif api_key:
            logger.info("Using VWorld API for elevation (No DB Cache)...")
            await self._add_vworld_elevation_async(G, api_key)
        else:
            logger.info("No API key provided. Using simulated elevation data.")
            self._add_simulated_elevation(G)
        return G

    async def _add_vworld_elevation_async(self, G: nx.Graph, api_key: str):
        """브이월드 API를 비동기 병렬로 호출하되, 샘플링을 통해 속도를 최적화합니다."""
        import httpx
        import asyncio
        import random

        # 1. 샘플링 대상 노드 선정 (모든 노드가 아닌 일부만 요청)
        # 노드 수가 너무 많으면 성능 저하의 주범이 되므로, 최대 200개 정도로 제한하거나 5개 중 1개 선택
        all_nodes = list(G.nodes())
        if len(all_nodes) > 200:
            sample_size = 200
            request_nodes = random.sample(all_nodes, sample_size)
            logger.info(f"Sampling {sample_size} nodes out of {len(all_nodes)} for elevation.")
        else:
            request_nodes = all_nodes
            logger.info(f"Requesting elevation for all {len(all_nodes)} nodes.")

        unique_coords = {}
        for node in request_nodes:
            data = G.nodes[node]
            lat, lon = data['y'], data['x']
            unique_coords[node] = (lat, lon)

        coord_cache = {}
        semaphore = asyncio.Semaphore(15) # 동시 요청 수 약간 상향

        async def fetch_node_elevation(client, node, lat, lon):
            cache_key = (round(lat, 5), round(lon, 5))
            if cache_key in coord_cache:
                return node, coord_cache[cache_key]

            url = "https://api.vworld.kr/req/data"
            params = {
                "service": "data",
                "request": "GetFeature",
                "data": "LT_CH_DEM_10M",
                "key": api_key,
                "domain": "localhost",
                "geomFilter": f"POINT({lon} {lat})"
            }

            async with semaphore:
                for attempt in range(2):
                    try:
                        response = await client.get(url, params=params, timeout=5.0)
                        if response.status_code == 200:
                            res_json = response.json()
                            if res_json.get("response", {}).get("status") == "OK":
                                features = res_json.get("response", {}).get("result", {}).get("featureCollection", {}).get("features", [])
                                if features:
                                    height = features[0].get("properties", {}).get("height")
                                    if height is not None:
                                        elev = float(height)
                                        coord_cache[cache_key] = elev
                                        return node, elev
                        
                        await asyncio.sleep(0.1) # 짧은 대기
                    except Exception:
                        await asyncio.sleep(0.1)
            
            return node, 20.0 # 기본값

        # 전체 과정에 15초 타임아웃 적용 (무한 대기 방지)
        try:
            async with httpx.AsyncClient() as client:
                tasks = [fetch_node_elevation(client, node, lat, lon) for node, (lat, lon) in unique_coords.items()]
                results = await asyncio.wait_for(asyncio.gather(*tasks), timeout=15.0)

            # 결과 반영
            fetched_elevs = {}
            for node, elev in results:
                G.nodes[node]['elevation'] = elev
                fetched_elevs[node] = elev

            # 2. 샘플링되지 않은 노드들에 고도 채우기 (가장 가까운 샘플 노드 기반 또는 전체 평균)
            avg_elev = sum(fetched_elevs.values()) / len(fetched_elevs) if fetched_elevs else 20.0
            for node in all_nodes:
                if 'elevation' not in G.nodes[node]:
                    G.nodes[node]['elevation'] = avg_elev

            logger.info(f"VWorld elevation update completed. Avg elevation: {avg_elev:.2f}m")
            
        except asyncio.TimeoutError:
            logger.warning("VWorld elevation fetching timed out. Using default elevation for remaining nodes.")
            # 타임아웃 시 기본값으로 모두 채움
            for node in all_nodes:
                if 'elevation' not in G.nodes[node]:
                    G.nodes[node]['elevation'] = 20.0

    def _add_simulated_elevation(self, G: nx.Graph):
        """가상의 지형 굴곡을 노드에 부여합니다."""
        import random
        import math
        
        # 지역 전체의 기본 고도와 변화 진폭 설정
        base_elevation = random.uniform(10, 50)
        amplitude = random.uniform(5, 30)
        frequency = random.uniform(500, 1500) # 지형 변화 주기 (미터)
        
        # 랜덤한 중심점 2~3개를 잡아 산/언덕처럼 표현
        center_points = []
        for _ in range(3):
            random_node = random.choice(list(G.nodes()))
            center_points.append((G.nodes[random_node]['y'], G.nodes[random_node]['x'], random.uniform(20, 100)))

        for node, data in G.nodes(data=True):
            lat, lon = data['y'], data['x']
            # 기본적인 물결 모양 지형
            elev = base_elevation + amplitude * math.sin(lat * frequency) * math.cos(lon * frequency)
            
            # 특정 지점을 언덕으로 설정
            for c_lat, c_lon, height in center_points:
                dist = ox.distance.great_circle(lat, lon, c_lat, c_lon)
                if dist < 500: # 500m 반경 내 언덕 효과
                    elev += height * (1 - (dist / 500))
            
            data['elevation'] = round(elev, 2)

    # 엣지에 경사도 및 가중치 계산
    def calculate_edge_grades_and_weights(self, G: nx.Graph):
        """노드 간 고도 차이를 이용해 경사도(grade)를 구하고 가중치를 설정합니다."""
        for u, v, data in G.edges(data=True):
            # 노드 데이터 가져오기
            node_u = G.nodes[u]
            node_v = G.nodes[v]
            
            if 'elevation' in node_u and 'elevation' in node_v:
                # 고도 차이 (미터)
                elev_diff = node_v['elevation'] - node_u['elevation']
                dist = data.get('length', 1.0)
                if dist < 1.0: dist = 1.0 # 0 나누기 방지
                
                # 경사도 (%)
                grade = (elev_diff / dist)
                data['grade'] = grade
                
                # 가중치 계산 (보행자는 오르막/내리막 모두 힘듦)
                abs_grade = abs(grade)
                
                # 쉬운 길 (경사도 기피): 경사가 급할수록 페널티 대폭 증가
                data['weight_easy'] = dist * (1 + abs_grade * 20) 
                # 어려운 길 (경사도 선호): 경사가 있을수록 거리를 짧게 인식하게 하여 선택 유도
                data['weight_hard'] = dist * (1 + (0.5 - abs_grade) * 2) if abs_grade < 0.2 else dist
            else:
                data['grade'] = 0
                data['weight_easy'] = data.get('length', 1.0)
                data['weight_hard'] = data.get('length', 1.0)

    # 경로의 총 거리를 계산
    def calculate_path_distance(
        self,
        graph: nx.Graph,
        path: List[int]
    ) -> float:
        """
        Args:
            graph: NetworkX 그래프 객체
            path: 노드 ID 리스트 [node1, node2, ...]

        Returns:
            총 거리 (미터)
        """
        if len(path) < 2:
            return 0.0

        total_distance = 0.0

        for i in range(len(path) - 1):
            node1 = path[i]
            node2 = path[i + 1]

            if not graph.has_edge(node1, node2):
                # 엣지가 없는 경우 (이론상 없어야 함)
                logger.warning(f"Edge ({node1}, {node2}) missing in graph")
                pos1 = graph.nodes[node1].get('pos')
                pos2 = graph.nodes[node2].get('pos')
                if pos1 and pos2:
                    total_distance += haversine_distance(pos1, pos2)
            else:
                # 엣지 데이터 가져오기
                edge_data = graph.get_edge_data(node1, node2)
                edge_len = 0.0
                
                # 1. 'length' 속성 시도
                if isinstance(edge_data, dict):
                     length = edge_data.get('length')
                     if length is not None:
                         if isinstance(length, list):
                             edge_len = min(float(x) for x in length)
                         else:
                             edge_len = float(length)
                
                # 2. 'length'가 없거나 0이면 Haversine으로 계산 (Fallback)
                if edge_len <= 0.001:
                    pos1 = graph.nodes[node1].get('pos')
                    pos2 = graph.nodes[node2].get('pos')
                    if pos1 and pos2:
                        edge_len = haversine_distance(pos1, pos2)
                        
                total_distance += edge_len

        return total_distance

    # 경로를 카카오 지도 좌표 형식으로 변환
    def path_to_kakao_coordinates(
        self,
        graph: nx.Graph,
        path: List[int]
    ) -> List[Dict[str, float]]:
        """
        Args: 
            graph: NetworkX 그래프
            path: 노드 ID 리스트

        Returns:
            [{'lat': y, "lng": x}, ...] 형식의 리스트
        """
        coordinates = []

        for node_id in path:
            node_data = graph.nodes[node_id]

            # _postprocess_graph에서 이미 pos 속성을 추가했으므로 pos만 체크
            if 'pos' in node_data:
                lon, lat = node_data['pos']
                coordinates.append({
                    'lat': lat,
                    "lng": lon
                })
            else:
                logger.warning(f"Node {node_id} missing pos coordinate data")

        return coordinates

    def get_elevation_stats(self, G: nx.Graph, path: List[int]) -> Dict:
        """경로의 고도 통계(총 상승 고도, 평균 경사도 등)를 계산합니다."""
        total_ascent = 0.0
        grades = []
        
        for i in range(len(path) - 1):
            u, v = path[i], path[i+1]
            node_u = G.nodes[u]
            node_v = G.nodes[v]
            
            if 'elevation' in node_u and 'elevation' in node_v:
                diff = node_v['elevation'] - node_u['elevation']
                if diff > 0:
                    total_ascent += diff
                
                # 경사도 수집
                edge_data = G.get_edge_data(u, v)
                if isinstance(edge_data, dict) and 'grade' in edge_data:
                    grades.append(abs(edge_data['grade']))
        
        avg_grade = (sum(grades) / len(grades)) * 100 if grades else 0
        
        return {
            "total_ascent": round(total_ascent, 2),
            "average_grade": round(avg_grade, 2)
        }

    def _validate_bbox(self, bbox: List[float]) -> None:
        # BBox 형식 검증
        if len(bbox) != 4:
            raise ValueError(f"BBox must have 4 elements, got {len(bbox)}")

        south, west, north, east = bbox

        # 위도 범위 체크 (-90 ~ 90)
        if not (-90 <= south < north <= 90):
            raise ValueError(
                f"Invalid latitude range: south={south}, north={north}."
                f"Must be: -90 <= south < north <= 90"
            )
        
        # 경도 범위 체크 (-180 ~ 180)
        if not (-180 <= west < east <= 180):
            raise ValueError(
                f"Invalid longtitude range: west={west}, east={east}"
                f"Must be: -180 <= west < east <= 180"
            )

        # 영역 크기 경고 (너무 크면 타임아웃 가능성, 가져올 도로 데이터 양이 많아지기 때문)
        lat_diff = north - south
        lon_diff = east - west
        area = lat_diff * lon_diff

        if area > 0.01: # 약 1km² 이상
            logger.warning(
                f"Large area detected ({area:.4f}°²)."
                f"Query might timeout. Consider splitting the area."
            )

    # Fallback: 자연스러운 랜덤 루프 경로 생성
    def generate_random_loop_route(
        self,
        center_point: Tuple[float, float],
        target_distance_km: float,
        seed: int = 0
    ) -> List[Dict[str, float]]:
        """
        사용자 위치를 시작/종료점으로 하는 자연스러운 다각형 루프 경로를 생성합니다.
        Args:
            center_point: (lat, lon) 시작/종료점
            target_distance_km: 목표 거리 (km)
            seed: 랜덤 시드 (경로 모양 다양화 용)
        Returns:
            [{'lat': y, 'lng': x}, ...] 좌표 리스트
        """
        import random
        import math
        
        # 시드 설정으로 재현성 확보 (옵션 간 차별화를 위해 외부에서 주입)
        rng = random.Random(seed)
        
        start_lat, start_lng = center_point
        
        # 다각형 꼭짓점 수 (3~5개)
        num_points = rng.randint(3, 5)
        
        # 각 꼭짓점까지의 거리 (대략적으로 전체 거리를 꼭짓점 수로 나눈 것의 절반 정도 반지름)
        # 단순히 원형으로 배치하되, 각도와 거리에 랜덤성을 부여
        avg_radius_km = (target_distance_km / (2 * math.pi)) # 둘레 기반 반지름 추정
        
        points = []
        # 시작점 추가
        points.append({"lat": start_lat, "lng": start_lng})
        
        current_angle = rng.uniform(0, 360)
        
        # 중간 점들 생성 (시작점에서 출발하여 반시계/시계 방향으로 회전하며 점 생성)
        # 하지만 "Start=End" 루프를 만들기 위해, 원형 궤적 위의 점들을 선택하는 것이 안정적
        
        # 1. 중심점 계산 (시작점에서 임의의 방향으로 반지름만큼 이동한 곳을 원의 중심으로 가정)
        center_angle = rng.uniform(0, 360)
        center_dist_deg = (avg_radius_km) / 111.0
        
        circle_center_lat = start_lat + center_dist_deg * math.cos(math.radians(center_angle))
        circle_center_lng = start_lng + (center_dist_deg * math.sin(math.radians(center_angle)) / math.cos(math.radians(start_lat)))
        
        # 2. 원 위의 점들 생성 (시작점 포함)
        # 시작점의 각도 계산
        start_angle_rad = math.atan2(
            (start_lng - circle_center_lng) * math.cos(math.radians(start_lat)), 
            start_lat - circle_center_lat
        )
        
        angle_step = (2 * math.pi) / num_points
        
        # 중간 점들
        route_points = []
        # 시작점 (정확히 입력받은 위치)
        route_points.append({"lat": start_lat, "lng": start_lng})
        
        for i in range(1, num_points):
            # 각도: 시작 각도 + 단계별 각도 + 약간의 랜덤성
            angle = start_angle_rad + (i * angle_step) + rng.uniform(-0.2, 0.2)
            
            # 거리: 평균 반지름 + 약간의 랜덤성 (찌그러뜨리기)
            radius_variation = rng.uniform(0.8, 1.2)
            r_deg = (avg_radius_km * radius_variation) / 111.0
            
            p_lat = circle_center_lat + r_deg * math.cos(angle)
            p_lng = circle_center_lng + (r_deg * math.sin(angle) / math.cos(math.radians(circle_center_lat)))
            
            route_points.append({"lat": p_lat, "lng": p_lng})
            
        # 다시 시작점으로 (Loop 완성)
        route_points.append({"lat": start_lat, "lng": start_lng})
        
        return route_points

# 구 위에 두 지점 사이의 최단 거리(대권 거리, Great-circle distance)를 구하는 공식 (미터 단위)
def haversine_distance(pos1: Tuple[float, float], pos2: Tuple[float, float]) -> float:
    """
    Args:
        pos1: (longitude, latitude)
        pos2: (longitude, latitude)

    Returns:
        거리 (미터)
    """
    lon1, lat1 = pos1
    lon2, lat2 = pos2

    # 라디안 변환
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

    # Haversine 공식
    # a = sin²(Δlat / 2) + cos(lat1) · cos(lat2) · sin²(Δlon / 2)
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))

    # 지구 반지름 (미터)
    r = 6371000

    # 호의 길이
    return c * r
