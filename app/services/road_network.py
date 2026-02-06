import osmnx as ox
import networkx as nx
from typing import Tuple, List, Optional, Dict
from sqlalchemy.orm import Session
import logging
from math import radians, cos, sin, asin, sqrt
from app.core.exceptions import ExternalAPIException
import os
import hashlib

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
            center_point: (위도, 경도) 튜플
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

        # 좌표를 100m 단위로 반올림 (캐시 히트율 향상)
        lat_rounded = round(lat, 3)  # 약 111m 단위
        lon_rounded = round(lon, 3)
        
        # 캐시 키 생성
        cache_key = f"{lat_rounded}_{lon_rounded}_{int(distance)}_{network_type}"
        cache_key_hash = hashlib.md5(cache_key.encode()).hexdigest()
        
        # 캐시 디렉토리 및 파일 경로
        from app.config import settings
        cache_dir = settings.OSMNX_CACHE_DIR
        os.makedirs(cache_dir, exist_ok=True)
        cache_file = os.path.join(cache_dir, f"{cache_key_hash}.gpickle")
        
        # 캐시 확인
        if os.path.exists(cache_file):
            try:
                logger.info(f"✅ Using cached network: {cache_key}")
                G = ox.load_graphml(cache_file)
                logger.info(f"Loaded cached graph with {G.number_of_nodes()} nodes")
                return G
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}. Fetching from OSM...")
                # 캐시 로드 실패 시 파일 삭제하고 새로 다운로드
                os.remove(cache_file)

        try:
            # OSMnx로 도로 네트워크 가져오기 (반올림된 좌표 사용)
            logger.info(f"Fetching network from OSM for ({lat_rounded}, {lon_rounded}) with distance {distance}m")
            G = ox.graph_from_point(
                center_point=(lat_rounded, lon_rounded),  # 반올림된 좌표 사용
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
            
            # 캐시 저장
            try:
                ox.save_graphml(G, cache_file)
                logger.info(f"Saved network to cache: {cache_file}")
            except Exception as e:
                logger.warning(f"Failed to save cache: {e}")

            return G
        except TimeoutError as e:
            logger.error(f"OSMnx timeout: {e}")
            raise ExternalAPIException("도로 정보를 가져오는데 시간이 초과되었습니다")
        except Exception as e:
            logger.error(f"OSMnx error: {e}")
            raise ExternalAPIException("도로 정보를 가져오는데 실패했습니다")

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
        db: Optional[Session] = None
    ) -> nx.Graph:
        """
        노드에 고도(elevation) 데이터를 비동기로 추가합니다 (캐시 우선).
        """
        if db:
            logger.info("Using ElevationService with DB Cache...")
            from app.services.elevation_service import ElevationService
            
            # Context Manager 패턴으로 리소스 자동 관리
            async with ElevationService(db) as elevation_service:
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
        else:
            logger.info("No DB session provided. Using simulated elevation data.")
            self._add_simulated_elevation(G)
        return G



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
                    # OSMnx 그래프는 'x'(경도), 'y'(위도) 속성 사용
                    lon1 = graph.nodes[node1].get('x')
                    lat1 = graph.nodes[node1].get('y')
                    lon2 = graph.nodes[node2].get('x')
                    lat2 = graph.nodes[node2].get('y')
                    
                    if lon1 and lat1 and lon2 and lat2:
                        edge_len = haversine_distance((lon1, lat1), (lon2, lat2))
                        
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

            # OSMnx 그래프는 'x'(경도), 'y'(위도) 속성 사용
            if 'x' in node_data and 'y' in node_data:
                lng = node_data['x']
                lat = node_data['y']
                coordinates.append({
                    'lat': float(lat),
                    'lng': float(lng)
                })
            else:
                logger.warning(f"Node {node_id} missing x/y coordinate data")

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

    def calculate_total_elevation_change(self, G: nx.Graph, path: List[int]) -> float:
        """경로의 총 고도 변화량 계산 (절대값 누적합)
        
        오르막과 내리막의 고도 차이를 모두 절대값으로 변환하여 누적합니다.
        이를 통해 경로의 전체적인 고저 변화의 강도를 파악할 수 있습니다.
        
        Args:
            G: NetworkX 그래프
            path: 노드 ID 리스트
        
        Returns:
            총 고도 변화량 (미터) - 오르막/내리막 절대값 누적
        """
        total_change = 0.0
        
        for i in range(len(path) - 1):
            u, v = path[i], path[i+1]
            node_u = G.nodes[u]
            node_v = G.nodes[v]
            
            if 'elevation' in node_u and 'elevation' in node_v:
                # 절대값을 씌워서 누적
                elev_diff = abs(node_v['elevation'] - node_u['elevation'])
                total_change += elev_diff
        
        return round(total_change, 2)

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
    # 가장 가까운 노드 찾기
    def get_nearest_node(self, G: nx.Graph, point: Tuple[float, float]) -> int:
        """
        Args:
            G: NetworkX 그래프
            point: (lat, lon)
        Returns:
            노드 ID
        """
        return ox.distance.nearest_nodes(G, point[1], point[0])

    # 루프 경로 생성 (실제 도로 기반)
    def generate_loop_route(
        self,
        G: nx.Graph,
        start_node: int,
        target_distance_km: float,
        attempt_number: int = 0
    ) -> List[int]:
        """
        출발지에서 목표 거리만큼의 루프 경로를 생성합니다.
        
        Args:
            G: NetworkX 그래프
            start_node: 출발 노드 ID
            target_distance_km: 목표 거리 (km)
            attempt_number: 시도 횟수 (다양한 방향 생성을 위해 사용)
            
        Returns:
            노드 ID 리스트 (경로)
        """
        import random
        import math
        
        # 1. 반환점(Destination) 찾기
        # 시도 횟수에 따라 방향을 다르게 설정
        # 0: 0도, 1: 60도, 2: 120도 ... (랜덤성 추가)
        base_bearing = (attempt_number * 60) % 360
        bearing = base_bearing + random.uniform(-20, 20)
        
        # 목표 반경 (왕복이므로 전체 거리의 절반)
        # 도로 굴곡도(Tortuosity)를 고려하여 직선 거리는 더 짧게 설정
        tortuosity_factor = 1.3
        target_radius_km = (target_distance_km / 2) / tortuosity_factor
        target_radius_m = target_radius_km * 1000
        
        # 해당 거리와 방향에 있는 노드 탐색
        min_dist = target_radius_m * 0.8
        max_dist = target_radius_m * 1.2
        
        candidate_nodes = []
        
        start_data = G.nodes[start_node]
        start_lat = start_data['y']
        start_lng = start_data['x']
        
        for node, data in G.nodes(data=True):
            if 'y' not in data or 'x' not in data:
                continue
                
            node_lat = data['y']
            node_lng = data['x']
            
            # 거리 계산
            dist = ox.distance.great_circle(start_lat, start_lng, node_lat, node_lng)
            
            if min_dist <= dist <= max_dist:
                # 방위각 계산
                y = math.sin(math.radians(node_lng - start_lng)) * math.cos(math.radians(node_lat))
                x = math.cos(math.radians(start_lat)) * math.sin(math.radians(node_lat)) - \
                    math.sin(math.radians(start_lat)) * math.cos(math.radians(node_lat)) * \
                    math.cos(math.radians(node_lng - start_lng))
                calc_bearing = math.degrees(math.atan2(y, x))
                calc_bearing = (calc_bearing + 360) % 360
                
                angle_diff = abs(calc_bearing - bearing)
                angle_diff = min(angle_diff, 360 - angle_diff)
                
                if angle_diff < 40:
                    candidate_nodes.append((node, angle_diff))
        
        if not candidate_nodes:
            # 방향 조건 완화하여 다시 검색
            for node, data in G.nodes(data=True):
                 if 'y' not in data or 'x' not in data: continue
                 dist = ox.distance.great_circle(start_lat, start_lng, data['y'], data['x'])
                 if min_dist * 0.7 <= dist <= max_dist * 1.3:
                     candidate_nodes.append((node, random.uniform(0, 100)))
        
        if not candidate_nodes:
            logger.warning("No destination validation candidates found.")
            return []
            
        # 가장 조건에 맞는 노드 선택
        candidate_nodes.sort(key=lambda x: x[1])
        dest_node = candidate_nodes[0][0]
        
        # 2. 경로 탐색 (가는 길)
        try:
            route_to = nx.shortest_path(G, start_node, dest_node, weight='length')
        except nx.NetworkXNoPath:
            return []
            
        # 3. 오는 길 (가는 길과 겹치지 않게 페널티 부여)
        # 엣지 가중치 임시 변경
        original_weights = {}
        for u, v in zip(route_to[:-1], route_to[1:]):
            if G.has_edge(u, v):
                edge_data = G.get_edge_data(u, v)
                # MultiGraph 처리
                if 0 in edge_data:
                    edge_data = edge_data[0]
                
                if 'length' in edge_data:
                    original_weights[(u, v)] = edge_data['length']
                    edge_data['length'] *= 10 # 페널티
        
        try:
            route_from = nx.shortest_path(G, dest_node, start_node, weight='length')
        except nx.NetworkXNoPath:
            route_from = route_to[::-1] # 되돌아오기
        finally:
            # 가중치 복구
            for (u, v), w in original_weights.items():
                if G.has_edge(u, v):
                     edge_data = G.get_edge_data(u, v)
                     if 0 in edge_data: edge_data = edge_data[0]
                     edge_data['length'] = w
                     
        # 4. 경로 합치기
        full_route = route_to + route_from[1:]
        return full_route
