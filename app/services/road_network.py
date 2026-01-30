import osmnx as ox
import networkx as nx
from typing import Tuple, List, Optional, Dict
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
