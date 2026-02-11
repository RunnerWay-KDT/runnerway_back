import osmnx as ox
import networkx as nx
import numpy as np
from typing import Tuple, List, Optional, Dict, Any
import logging, os
from math import radians, cos, sin, asin, sqrt

# 프로그램 전체의 로깅 규칙을 INFO 레벨로 정함
logging.basicConfig(level=logging.INFO) 
# __name__을 사용해 로그가 어느 파일에서 발생했는지 이름이 찍힘
logger = logging.getLogger(__name__)

# OSMnx를 사용한 도로 네트워크 추출
class RoadNetworkFetcher:
    def __init__(self, timeout: int = 30):
        # OSMnx 설정
        ox.settings.use_cache = True
        ox.settings.log_console = True
        ox.settings.timeout = timeout
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
        ox.settings.cache_folder = os.path.join(base, 'cache')
        self.timeout = timeout

    # 출발지 좌표를 중심으로 반경 내 보행자 도로 네트워크를 추출
    def fetch_pedestrian_network_from_point (
        self,
        center_point: Tuple[float, float], # (latitude, longitude)
        distance: float = 1000, # 미터 단위 반경
        network_type: str = 'walk',
        simplify: bool = True,
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

            logger.info(f"Fetched graph with {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

            # 후처리: MultiDiGraph -> Graph 변환 및 pos 속성 추가
            G = self._postprocess_graph(G)

            # degree-2 체인 압축으로 노드/엣지 수 줄이기
            G = self._compress_degree_2_chains(G)

            logger.info(f"Built graph with {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

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
            logger.info(f"Fetched graph with {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

            # 후처리: MultiDiGraph -> Graph 변환 및 pos 속성 추가
            G = self._postprocess_graph(G)

            logger.info(f"Built graph with {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

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
            logger.info(f"Removing {len(isolated)} isolated nodes")
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
                # 직접 연결이 없으면 Haversine 거리 계산
                pos1 = graph.nodes[node1].get('pos')
                pos2 = graph.nodes[node2].get('pos')

                if pos1 and pos2:
                    total_distance += haversine_distance(pos1, pos2)
                else:
                    logger.warning(f"Edge ({node1}, {node2}) not found and no pos data")
            else:
                # 엣지의 length 속성 사용 (OSMnx가 계산한 실제 거리)
                edge_data = graph.get_edge_data(node1, node2)
                if 'length' in edge_data:
                    total_distance += edge_data['length']
                elif 'weight' in edge_data:
                    total_distance += edge_data['weight']
                else:
                    # length/weight가 없으면 Haversine 거리 계산
                    pos1 = graph.nodes[node1].get('pos')
                    pos2 = graph.nodes[node2].get('pos')
                    if pos1 and pos2:
                        total_distance += haversine_distance(pos1, pos2)

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
 
    # 경로의 상세 정보를 반환
    def get_path_info(
        self,
        graph: nx.Graph,
        path: List[int]
    ) -> Dict:
        """
        Args:
            graph: NetworkX 그래프
            path: 노드 ID 리스트

        Returns:
            {
                "distance": float, # 총 거리 (미터),
                "coordinates": List[Dict], # 카카오 좌표
                "node_count": int, # 노드 개수
                "edge_count": int, # 엣지 개수
                "distance_km": float, # 총 거리 (킬로미터)
            }
        """
        distance = self.calculate_path_distance(graph, path)
        coordinates = self.path_to_kakao_coordinates(graph, path)

        return {
            "distance": distance, # 미터
            "distance_km": distance / 1000.0, # 킬로미터
            "coordinates": coordinates,
            "node_count": len(path),
            "edge_count": len(path) - 1 if len(path) > 1 else 0
        }       

    # 그림을 그리기 위한 최소 거리를 계산합니다.
    # 그림 좌표들을 순서대로 연결했을 때의 총 길이를 반환합니다.
    def calculate_drawing_minimum_distance(
        self,
        drawing_coordinates: List[Tuple[float, float]]  # [(lon, lat), ...]
    ) -> float:
        """        
        Args:
            drawing_coordinates: 그림의 좌표 리스트 (순서대로) [(lon, lat), ...]
            
        Returns:
            최소 거리 (미터)
        """
        if len(drawing_coordinates) < 2:
            return 0.0
        
        total_distance = 0.0
        
        for i in range(len(drawing_coordinates) - 1):
            pos1 = drawing_coordinates[i]
            pos2 = drawing_coordinates[i + 1]
            total_distance += haversine_distance(pos1, pos2)
        
        return total_distance

    # 사용자가 입력한 거리와 최소 거리를 비교하여 검증합니다.
    def validate_target_distance(
        self,
        minimum_distance: float,
        target_distance: float,
        tolerance: float = 0.5  # 5% 여유
    ) -> Dict:
        """        
        Args:
            minimum_distance: 그림을 그리기 위한 최소 거리 (미터)
            target_distance: 사용자가 입력한 목표 거리 (미터)
            tolerance: 허용 오차 (기본 10%, 0.2 = 10%)
            
        Returns:
            {
                "is_valid": bool,  # 목표 거리가 충분한지
                "minimum_distance": float,  # 최소 거리 (미터)
                "minimum_distance_km": float,  # 최소 거리 (킬로미터)
                "target_distance": float,  # 목표 거리 (미터)
                "target_distance_km": float,  # 목표 거리 (킬로미터)
                "shortage": float,  # 부족한 거리 (미터, is_valid가 False일 때만)
                "shortage_km": float,  # 부족한 거리 (킬로미터)
                "message": str,  # 사용자에게 보여줄 메시지
                "options": List[str]  # 사용 가능한 옵션들
            }
        """
        minimum_distance_km = minimum_distance / 1000.0
        target_distance_km = target_distance / 1000.0
        
        # 최소 거리의 (1 - tolerance) 배 이상이면 유효
        threshold = minimum_distance * (1 - tolerance)
        is_valid = target_distance >= threshold
        
        result = {
            "is_valid": is_valid,
            "minimum_distance": minimum_distance,
            "minimum_distance_km": minimum_distance_km,
            "target_distance": target_distance,
            "target_distance_km": target_distance_km,
            "message": "",
            "options": []
        }
        
        if is_valid:
            result["message"] = f"목표 거리 {target_distance_km:.2f}km는 충분합니다. (최소: {minimum_distance_km:.2f}km)"
        else:
            shortage = minimum_distance - target_distance
            shortage_km = shortage / 1000.0
            
            result["shortage"] = shortage
            result["shortage_km"] = shortage_km
            result["message"] = (
                f"경고: 목표 거리 {target_distance_km:.2f}km는 부족합니다.\n"
                f"이 그림을 그리려면 최소 {minimum_distance_km:.2f}km가 필요합니다.\n"
                f"부족한 거리: {shortage_km:.2f}km"
            )
            result["options"] = [
                f"거리를 {minimum_distance_km:.2f}km 이상으로 늘리기",
                "그림을 단순화하기",
                "경로에 루프 추가 (형태는 약간 변할 수 있음)"
            ]
        
        return result

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

    # degree=2인 중간 노드들을 제거하고, 양 끝 노드를 하나의 엣지로 연결.
    # - 실제 도로 토폴로지는 유지하되, 노드/엣지 수만 줄인다.
    # - 엣지 길이(length)는 합쳐서 저장한다.
    def _compress_degree_2_chains(self, G: nx.Graph) -> nx.Graph:
        G = G.copy()
        removed = True

        while removed:
            removed = False
            # 순회 중 그래프가 바뀌므로, 노드 리스트를 따로 뽑아둠
            for node in list(G.nodes()):
                # 교차로/끝점 등은 degree != 2이므로 건드리지 않음
                if G.degree(node) != 2:
                    continue

                neighbors = list(G.neighbors(node))
                if len(neighbors) != 2:
                    continue

                u, v = neighbors

                # 이미 u-v 엣지가 있으면 패스
                if G.has_edge(u, v):
                    continue

                data_u = G.get_edge_data(u, node, default={})
                data_v = G.get_edge_data(node, v, default={})

                len_u = data_u.get('length', 0.0) if isinstance(data_u, dict) else 0.0
                len_v = data_v.get('length', 0.0) if isinstance(data_v, dict) else 0.0
                new_length = len_u + len_v

                # edge 속성 머지: dict 형태만 대상으로, 키가 문자열인 것만 모음
                attrs: Dict[str, Any] = {}

                for d in (data_u, data_v):
                    if isinstance(d, dict):
                        for key, val in d.items():
                            if isinstance(key, str):
                                attrs[key] = val

                # pos 등 기타 속성은 u-v 중 어느 한쪽/합친 dict를 사용
                attrs["length"] = new_length
                G.add_edge(u, v, **attrs)
                G.remove_node(node)
                removed = True

        return G

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

def haversine_matrix_meters(
    lon1: np.ndarray, lat1: np.ndarray,
    lon2: np.ndarray, lat2: np.ndarray,
) -> np.ndarray:
    """
    (N,) vs (M,) -> (N, M) 하버 사인 거리 행렬 (미터 단위).

    lon1, lat1: (N,) 도 단위
    lon2, lat2: (M,) 도 단위
    반환값: shape (N, M), [i, j] = (lon1[i], lat1[i]) ~ (lon2[j], lat2[j]) 거리(m)
    """
    lon1_rad = np.deg2rad(lon1)
    lat1_rad = np.deg2rad(lat1)
    lon2_rad = np.deg2rad(lon2)
    lat2_rad = np.deg2rad(lat2)

    # (N, 1) - (1, M) 브로드캐스트 (for문이 아닌 행렬 연산으로 한 번에 계산)
    dlon = lon2_rad - lon1_rad[:, None] # (N, M)
    dlat = lat2_rad - lat1_rad[:, None]

    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat1_rad)[:, None] * np.cos(lat2_rad)[None, :] * np.sin(dlon / 2.0) ** 2
    a = np.clip(a, 0.0, 1.0)
    c = 2.0 * np.arcsin(np.sqrt(a))
    r = 6371000.0

    return r * c