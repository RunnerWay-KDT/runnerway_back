from queue import PriorityQueue
from typing import List, Tuple, Dict, Optional
from road_network import haversine_distance, RoadNetworkFetcher
from collections import defaultdict
import networkx as nx
import numpy as np
import logging
import math
import re

logger = logging.getLogger(__name__)

LonLat = [Tuple[float, float]]

# GPS 아트 경로 생성 클래스
class GPSArtRouter:
    def __init__(self, graph: nx.Graph):
        self.G = graph
        self.n_samples = 50 # C3 계산을 위한 샘플링 수

    # 노드를 경위도 그리드 셀에 넣어둠. cell_size_deg 약 0.0005 ≈ 50m. 처음 한 번만 호출
    def build_node_grid(self, cell_size_deg: float = 0.0005) -> None:
        self._node_grid = defaultdict(list) # 그리드 셀 번호 -> 노드 ID 리스트
        self._grid_cell_size = cell_size_deg
        for node_id in self.G.nodes():
            pos = self.G.nodes[node_id].get("pos")
            if pos is None:
                continue
            lon, lat = pos[0], pos[1]
            # 비슷한 위치의 노드들을 같은 그리드 셀에 넣어둠
            cell = (int(lat // cell_size_deg), int(lon // cell_size_deg))
            self._node_grid[cell].append(node_id)

    # point 주변 radius_m 이내 노드만 반환. 그리드 사용. (node_id, 거리m)
    def _get_nodes_in_cells_near_point(
        self, point: Tuple[float, float], radius_m: float
    ) -> List[Tuple[int, float]]:
        """
        Args:
            point: 점 좌표 (lon, lat)
            radius_m: 반경 거리(미터)

        Returns:
            점에서 radius_m 이내인 노드들을 (node_id, 거리m) 리스트
        """
        if not hasattr(self, "_node_grid") or self._node_grid is None:
            # 그리드 없으면 전체 스캔으로 (node_id, 거리m) 리스트 반환
            lon, lat = point[0], point[1]
            result: List[Tuple[int, float]] = []
            for node_id in self.G.nodes():
                pos = self.G.nodes[node_id].get("pos")
                if pos is None:
                    continue
                n_lon, n_lat = pos[0], pos[1]
                d = haversine_distance((lon, lat), (n_lon, n_lat))
                if d <= radius_m:
                    result.append((node_id, d))
            return result
        lon, lat = point[0], point[1]
        # 반경(미터)를 대략 경도/위도 차이로. 간단히 1도≈111km
        r_deg = radius_m / 111_000.0
        cell_size = getattr(self, "_grid_cell_size", 0.0005)
        # 검사할 셀 범위
        ci_min = int((lat - r_deg) // cell_size)
        ci_max = int((lat + r_deg) // cell_size)
        cj_min = int((lon - r_deg) // cell_size)
        cj_max = int((lon + r_deg) // cell_size)
        result: List[Tuple[int, float]] = []
        for ci in range(ci_min, ci_max + 1):
            for cj in range(cj_min, cj_max + 1):
                for node_id in self._node_grid.get((ci, cj), []):
                    pos = self.G.nodes[node_id].get("pos")
                    if pos is None:
                        continue
                    n_lon, n_lat = pos[0], pos[1]
                    d = haversine_distance((lon, lat), (n_lon, n_lat))
                    if d <= radius_m:
                        result.append((node_id, d))

        return result

    # 주어진 좌표(lon, lat)에 가장 가까운 그래프 노드 찾기. 그리드 있으면 근처 셀만 검사.
    def find_nearest_node(self, point: [LonLat], search_radius_m: float = 500.0) -> int:
        """
        Args:
            point: 좌표 (lon, lat)

        Returns:
            int: 가장 가까운 그래프 노드 ID
        """
        if hasattr(self, "_node_grid") and self._node_grid is not None:
            candidates = self._get_nodes_in_cells_near_point(point, radius_m=search_radius_m)
            if candidates:
                return min(candidates, key=lambda x: x[1])[0]
        # 그리드 없거나 후보 없으면 전체 스캔
        min_dist = float('inf')
        nearest = None
        px, py = point
        for node_id in self.G.nodes():
            nx_pos, ny_pos = self.G.nodes[node_id]['pos']
            dist = np.sqrt((px - nx_pos)**2 + (py - ny_pos)**2)
            if dist < min_dist:
                min_dist = dist
                nearest = node_id

        return nearest

    # 메트릭 C1: 목적지까지의 유클리드 거리
    # C1(N, E) = √((N_lat − E_lat)² + (N_lon − E_lon)²)
    def C1_distance_minimization(self, N: [LonLat], E: [LonLat]) -> float:
        # 벡터의 L2 Norm 길이 계산
        return np.linalg.norm(np.array(N) - np.array(E))

    # 메트릭 C2: 현재 노드에서 다음 노드까지의 거리
    # C2(P, N) = |P - N|
    def C2_path_minimization(self, P: [LonLat], N: [LonLat]) -> float:
        return np.linalg.norm(np.array(P) - np.array(N))

    # 웨이포인트 기반 경로 (스케일+회전된 polyline -> 샘플 -> 노드 시퀀스 -> A*로 연결)
    def _sample_polyline_evenly(
        self,
        points: List[Tuple[float, float]],
        n_samples: int=30,
    ) -> List[Tuple[float, float]]:
        """
        Args:
            points: 원본 좌표 리스트 [(lon, lat), ...]
            n_samples: 샘플링 수 (기본 30)

        Returns:
            샘플링된 좌표 리스트 [(lon, lat), ...]

        polyline [(lon, lat), ...] 을 전체 길이(haversine 거리) 기준으로 n_samples개로 균등 샘플링.
        """
        if len(points) < 2:
            return list(points)

        seg_lengths = []
        for i in range(len(points) - 1):
            seg_lengths.append(haversine_distance(points[i], points[i + 1]))

        total_len = sum(seg_lengths)
        if total_len <= 0:
            return list(points)

        cum = [0.0]
        for L in seg_lengths:
            cum.append(cum[-1] + L)

        if n_samples <= 1:
            targets = [0.0, total_len]
        else:
            step = total_len / (n_samples - 1)
            targets = [step * i for i in range(n_samples)]

        sampled: List[Tuple[float, float]] = []
        seg_idx = 0
        for t in targets:
            while seg_idx < len(seg_lengths) - 1 and cum[seg_idx + 1] < t:
                seg_idx += 1
            seg_start = cum[seg_idx]
            seg_len = seg_lengths[seg_idx]
            if seg_len <= 0:
                ratio = 0.0
            else:
                ratio = min(1.0, (t - seg_start) / seg_len)

            lon0, lat0 = points[seg_idx]
            lon1, lat1 = points[seg_idx + 1]
            lon = lon0 + ratio * (lon1 - lon0)
            lat = lat0 + ratio * (lat1 - lat0)
            sampled.append((lon, lat))

        return sampled

    # start -> goal 최단 경로(노드 ID 리스트). C2(엣지 길이)만 사용, 휴리스틱은 C1(목적지까지 거리).
    def _a_star_between_nodes(self, start: int, goal: int) -> Optional[List[int]]:
        frontier = PriorityQueue() # 우선순위 큐, 비용이 낮은 노드가 우선순위가 높음
        frontier.put((0, start)) # 시작 노드를 우선순위 큐에 추가, 비용 0
        came_from = {start: None} # 이전 노드 저장, 시작 노드는 이전 노드가 없음
        cost_so_far = {start: 0} # 비용 저장, 시작 노드의 비용은 0
        goal_pos = self.G.nodes[goal]['pos']

        while not frontier.empty():
            _, current = frontier.get() # 우선순위가 가장 낮은 노드를 꺼냄
            # 경로 재구성
            if current == goal:
                path = []
                while current is not None:
                    path.append(current)
                    current = came_from[current]
                return path[::-1] # 경로 노드 ID 리스트 반환
                
            for neighbor in self.G.neighbors(current):
                P = self.G.nodes[current]['pos']
                N = self.G.nodes[neighbor]['pos']
                # C2(엣지 길이)만 사용
                edge_cost = self.C2_path_minimization(P, N)
                new_cost = cost_so_far[current] + edge_cost

                if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                    cost_so_far[neighbor] = new_cost
                    # C1(목적지까지 거리) 휴리스틱 사용
                    heuristic = self.C1_distance_minimization(N, goal_pos)
                    priority = new_cost + heuristic
                    frontier.put((priority, neighbor))
                    came_from[neighbor] = current

        return None

    # 점에서 선분(그림의 한 구간)까지의 최단 거리(미터), haversine 사용
    def _distance_point_to_segment(
        self,
        point: Tuple[float, float],
        seg_start: Tuple[float, float],
        seg_end: Tuple[float, float],
    ) -> float:
        """
        Args:
            point: 점 좌표 (lon, lat)
            seg_start: 세그먼트 시작점 (lon, lat)
            seg_end: 세그먼트 끝점 (lon, lat)

        Returns:
            점에서 세그먼트까지의 최단 거리(미터)
        """
        lon, lat = point[0], point[1]
        a_lon, a_lat = seg_start[0], seg_start[1]
        b_lon, b_lat = seg_end[0], seg_end[1]
        ax = np.array([a_lon, a_lat])
        bx = np.array([b_lon, b_lat])
        px = np.array([lon, lat])
        ab = bx - ax
        ap = px - ax
        seg_len_sq = np.dot(ab, ab)
        # 예외 처리: 세그먼트가 한 점인 경우
        if seg_len_sq < 1e-18:
            return haversine_distance((lon, lat), (a_lon, a_lat))
        # 투영 비율 t 계산 (0~1 사이)
        t = np.dot(ap, ab) / seg_len_sq
        t = max(0.0, min(1.0, t))
        # 가장 가까운 점 계산
        closest_lon = a_lon + t * (b_lon - a_lon)
        closest_lat = a_lat + t * (b_lat - a_lat)
        # 대상 점과 선분 위의 가장 가까운 점 사이의 거리 계산
        return haversine_distance((lon, lat), (closest_lon, closest_lat))

    # sampled_points[i]에서의 polyline 진행 방향 벡터를 반환. 두 점 사이의 벡터 방향.
    def _polyline_direction_at(
        self, sampled_points: List[Tuple[float, float]], i: int
    ) -> np.ndarray:
        """
        Args:
            sampled_points: 샘플링된 좌표 리스트 [(lon, lat), ...]
            index: 샘플링 인덱스

        Returns:
            샘플링 인덱스에서의 polyline 진행 방향 벡터
        """
        if len(sampled_points) < 2:
            return np.array([1.0, 0.0])
        if i <= 0:
            d = np.array(sampled_points[1]) - np.array(sampled_points[0])
        elif i >= len(sampled_points) - 1:
            d = np.array(sampled_points[-1]) - np.array(sampled_points[-2])
        else:
            d = np.array(sampled_points[i + 1]) - np.array(sampled_points[i - 1])
        n = np.linalg.norm(d)
        if n < 1e-9:
            return np.array([1.0, 0.0])
        return d / n

    # 스케일+회전된 도형 polyline [(lon, lat), ...] 을 n_samples로 샘플링하고,
    # 각 샘플 포인트 근처 노드를 차례로 지나가도록 A*로 이어붙인 경로(노드 ID 리스트) 반환.
    def _compute_waypoint_nodes(
        self,
        start_point: Tuple[float, float],
        drawing_polyline: List[Tuple[float, float]],
        n_samples: int = 30,
        use_segment_neareast: bool = True,
        use_direction: bool = True,
        direction_weight: float = 0.4, # 0.4인 이유: 방향 가중치가 너무 크면 방향에 따라 경로가 크게 변함.
    ) -> Optional[List[int]]:
        """
        Args:
            start_point: 출발지 좌표 (lon, lat)
            drawing_polyline: 그림 선 좌표 리스트 [(lon, lat), ...]
            n_samples: 샘플링 수 (기본 30)
            use_segment_neareast: 세그먼트 근처 노드 사용 여부 (기본 True)
            use_direction: 방향 사용 여부 (기본 True)
            direction_weight: 방향 가중치 (기본 0.4)

        Returns:
            Optional[List[int]]: 경로 노드 ID 리스트 또는 None
        """
        if len(drawing_polyline) < 2:
            return None

        # 시작 노드
        start_node = self.find_nearest_node(start_point)
        # polyline를 균등하게 n_samples개로 샘플링
        sampled_points = self._sample_polyline_evenly(drawing_polyline, n_samples=n_samples)

        # 그리드 인덱스 한 번만 구축 (use_segment_nearest 일 때만)
        if use_segment_neareast and (not hasattr(self, "_node_grid") or self._node_grid is None):
            self.build_node_grid()

        # 각 샘플 포인트: 그림 선분에 가장 가까운 노드 선택 (전체 노드 순회)
        waypoint_nodes: List[int] = []
        last_node: Optional[int] = None
        prev_pos: Optional[Tuple[float, float]] = None

        for i, pt in enumerate(sampled_points):
            if not use_segment_neareast:
                node = self.find_nearest_node(pt)
                if last_node is None or node != last_node:
                    waypoint_nodes.append(node)
                    last_node = node
                continue

            if i < len(sampled_points) - 1:
                seg_start, seg_end = pt, sampled_points[i + 1]
            else:
                seg_start, seg_end = sampled_points[i - 1], pt

            # 이전 waypoint 좌표 (첫 샘플이면 start_node)
            if prev_pos is None:
                prev_pos = self.G.nodes[start_node]['pos']
            prev_pos_np = np.array(prev_pos)
            direction_vec = self._polyline_direction_at(sampled_points, i) if use_direction else None

            # 그리드 있으면 근처 노드만, 없으면 전체 노드 (폴백)
            if hasattr(self, "_node_grid") and self._node_grid is not None:
                candidates = self._get_nodes_in_cells_near_point(pt, radius_m=100.0)
            else:
                candidates = [(nid, 0.0) for nid in self.G.nodes() if self.G.nodes[nid].get("pos") is not None]

            best_node: Optional[int] = None
            best_score = float('inf')

            for node_id, _ in candidates:
                pos = self.G.nodes[node_id].get("pos")
                if pos is None:
                    continue
                if last_node is not None and node_id == last_node:
                    continue
                node_pos_tup = (pos[0], pos[1])
                # 거리 점수(d): 노드가 현재 그림 선분에 얼마나 가까운지, 낮을수록 좋음
                d = self._distance_point_to_segment(node_pos_tup, seg_start, seg_end)

                if use_direction and direction_vec is not None:
                    node_pos_np = np.array(pos)
                    to_node = node_pos_np - prev_pos_np
                    norm_to = np.linalg.norm(to_node)
                    if norm_to < 1e-9:
                        align = 1.0
                    else:
                        # 방향 점수(align): 노드 방향이 현재 그림 선분 방향과 얼마나 일치하는지, 1에 가까울수록 좋음
                        align = np.dot(to_node / norm_to, direction_vec)
                        align = max(-1.0, min(1.0, align))
                    direction_penalty_scale = 50.0
                    direction_penalty = direction_penalty_scale * (1.0 - align)                    
                    score = d + direction_weight * direction_penalty
                else:
                    score = d

                if score < best_score:
                    best_score = score
                    best_node = node_id

            if best_node is not None:
                waypoint_nodes.append(best_node)
                last_node = best_node
                prev_pos = self.G.nodes[best_node]['pos']
            else:
                # 후보가 비었을 때 폴백
                node = self.find_nearest_node(pt)
                if last_node is None or node != last_node:
                    waypoint_nodes.append(node)
                    last_node = node
                    prev_pos = self.G.nodes[node]['pos']

        if not waypoint_nodes:
            return None

        # 출발지에 가장 가까운 노드 -> 경로 상의 한 점으로만 쓰기 (출발지가 시작점이 아님)
        node_departure = self.find_nearest_node(start_point)

        # # polyline 상에서 출발지와 가장 가까운 샘플 인덱스 찾기
        def _dist_sq(a: Tuple[float, float], b: Tuple[float, float]) -> float:
            return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2

        i_closest = min(
            range(len(sampled_points)),
            key=lambda i: _dist_sq(sampled_points[i], start_point),
        )
        # # 그 위치의 waypoint를 출발지 노드로 고정 -> 경로가 출발지를 지나감
        if i_closest < len(waypoint_nodes):
            waypoint_nodes[i_closest] = node_departure
        else:
            waypoint_nodes.append(node_departure)

        return waypoint_nodes

    # waypoint 순서를 start_index부터 cyclic shift한 뒤, 
    # 인접 waypoint 사이를 A*로 이어붙인 전체 노드 경로 반환
    def build_full_path(
        self,
        waypoint_nodes: List[int],
        start_index: int,
    ) -> Optional[List[int]]:
        if not waypoint_nodes:
            return None
        n = len(waypoint_nodes)
        # cyclic shift: start_index가 n보다 크면 원형으로 돌아감(방어코드)
        start_index = start_index % n 
        node_sequence = waypoint_nodes[start_index:] + waypoint_nodes[:start_index]

        full_path: List[int] = []
        current_start = node_sequence[0]
        for next_node in node_sequence[1:]:
            sub_path = self._a_star_between_nodes(current_start, next_node)
            if not sub_path:
                return None
            if full_path and full_path[-1] == sub_path[0]:
                full_path.extend(sub_path[1:])
            else:
                full_path.extend(sub_path)
            current_start = next_node

        return full_path

    # waypoint 한 번 계산 후, 시작 인덱스 0으로 전체 경로 생성
    def find_path_via_waypoints(
        self,
        start_point: Tuple[float, float],
        drawing_polyline: List[Tuple[float, float]],
        n_samples: int = 30,
        use_segment_nearesest: bool = True,
        use_direction: bool = True,
        direction_weight: float = 0.4,
    ) -> Optional[List[int]]:
        wp_nodes = self._compute_waypoint_nodes(
            start_point, drawing_polyline, n_samples,
            use_segment_nearesest, use_direction, direction_weight,
        )
        if not wp_nodes:
            return None
        return self.build_full_path(wp_nodes, 0)

    # SVG 경로 문자열을 Canvas 좌표 리스트로 파싱
    def parse_svg_path_to_canvas_coordinates(
        self,
        svg_path: str, # SVG 경로 문자열
    ) -> List[Dict[str, float]]:
        """
        Args:
            svg_path: SVG 경로 문자열 (예: "M 10 20 L 30 40 L 50 60")
        Retruns:
            Canvas 좌표 리스트 [{"x": float, "y": float}, ...]

        SVG 경로 형식:
            - M x y: Move to (시작점)
            - L x y: Line to (직선)
            - 여러 경로가 공백으로 구분됨
        """
        if not svg_path:
            return []

        # SVG 경로를 토큰으로 분리
        # 예: "M 10 20 L 30 40 L 50 60" -> ["M", "10", "20", "L", "30", "40", "L", "50", "60"]
        tokens = re.findall(r'[ML]|-?\d+(?:\.\d+)?', svg_path)
        
        i = 0
        cmd = None
        points = []
        while i < len(tokens):
            t = tokens[i]
            if t in ('M', 'L'):
                cmd = t
                i += 1
                continue
            # Move to 또는 Line to 명령
            if i + 1 < len(tokens):
                x = float(tokens[i])
                y = float(tokens[i + 1])
                points.append({"x": x, "y": y})
                i += 2
            else:
                break

        return points

    # Canvas 좌표를 지리 좌표로 변환
    def convert_canvas_to_geographic(
        self,
        canvas_points: List[Dict[str, float]],  # [{"x": 175, "y": 350}, ...]
        start_lat: float,
        start_lon: float,
        canvas_size: float = 350.0,
    ) -> List[Dict[str, float]]: 
        """
       Canvas 좌표를 대략적인 지리 좌표(lat/lon)로 투영한다.
        - Canvas 중심 기준 정규화 후
        - 첫 점을 시작점(출발지)와 겹치도록 상대 좌표로 조정
        - 위도/경도 스케일은 대략적인 값 사용 (이후 scale_drawing_coordinates로 정확히 맞춤)
        반환: [{"lat": float, "lon": float}, ...]

        Args: 
            cavas_points: Canvas 픽셀 좌표 리스트 [{"x": float, "y": float}, ...]
            start_lat: 시작점 위도
            start_lon: 시작점 경도
            canvas_size: Canvas 크기 (픽셀, 기본값 350)

        Returns:
            지리 좌표 리스트 [{"lat": float, "lon": float}, ...]

        주의: 시작점은 Canvas의 첫 번째 점 또는 마지막 점이어야 함
        """
        if not canvas_points:
            return []

        # Canvas 좌표 정규화 (중심을 0,0으로, 범위 -1~1)
        canvas_center = canvas_size / 2.0
        normalized_points = [
            {
                "x": (pt["x"] - canvas_center) / canvas_center, # -1 ~ 1
                "y": (pt["y"] - canvas_center) / canvas_center, 
            }
            for pt in canvas_points
        ]

        # 시작점 찾기 (첫 점을 시작점으로 가정)
        start_canvas_point = normalized_points[0]
        # 시작점 기준 상대 좌표
        relative_points = [
            {
                "x": pt["x"] - start_canvas_point["x"],
                "y": pt["y"] - start_canvas_point["y"]
            }
            for pt in normalized_points
        ]

        # 임시 스케일로 지리 좌표 변환
        # (실제 스케일링은 scale_drawing_coordinates에서 목표 거리에 맞춰 수행)
        # 위도 1도 ≈ 111.32 km, 경도는 위도에 따라 다름
        # 때문에 임시 스케일링을 0.01로 설정하여 약 1.11km로 변환
        temp_scale_lat = 0.01
        # 경도 스케일은 위도에 따라 조정
        temp_scale_lon = 0.01 / math.cos(math.radians(start_lat)) # 위도에 따른 경도 스케일

        # 캔버스 좌표를 실제 위경도로 반환
        geographic_points = [
            {
                "lat": start_lat + pt["y"] * temp_scale_lat,
                "lon": start_lon + pt["x"] * temp_scale_lon
            }
            for pt in relative_points
        ]

        return geographic_points

    # 그림 좌표 리스트의 무게중심 (회전・스케일 기준용)
    def _drawing_centroid(
        self, coordinates: List[[LonLat]],
    ) -> [LonLat]:
        """
        Args:
            coordinates: 좌표 리스트 [(lon, lat), ...]

        Returns:
            좌표 리스트 [(lon, lat), ...]
        """
        if not coordinates:
            return []
        n = len(coordinates)
        clon = sum(c[0] for c in coordinates) / n
        clat = sum(c[1] for c in coordinates) / n
        return (clon, clat)

    # 좌표 리스트 전체를 (dx, dy)만큼 평행 이동
    def translate_coordinates(
        self,
        coordinates: List[[LonLat]],
        delta: Tuple[float, float],
    ) -> List[[LonLat]]:
        """
        Args:
            coordinates: 좌표 리스트 [(lon, lat), ...]
            delta: 평행 이동 거리 (dx, dy)

        Returns:
            좌표 리스트 [(lon, lat), ...]
        """
        dx, dy = delta
        return [(lon + dx, lat + dy) for lon, lat in coordinates]
        
    # 좌표를 중심점을 기준으로 회전
    def rotate_coordinates(
        self,
        coordinates: List[[LonLat]],
        center: [LonLat],
        angle_degrees: float,
    ) -> List[[LonLat]]:
        """
        Args:
            coordinates: 회전할 좌표 리스트 [(lon, lat), ...]
            center: 회전 중심점 (lon, lat), 여기서 출발지가 중심점이므로, (start_lon, start_lat)
            angle_degrees: 회전 각도 (도 단위, 시계 방향)

        Returns:
            회전된 좌표 리스트 [(lon, lat), ...]
        """
        if not coordinates:
            return []

        angle_rad = math.radians(angle_degrees)
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)

        center_lon, center_lat = center
        rotated: List[LonLat] = []

        # 위도에 따른 경도 스케일 계산
        lat_scale = 111.0 # 위도 1도 ≈ 111 km
        lon_scale = 111.0 * math.cos(math.radians(center_lat)) # 경도 1도 ≈ 111 km * cos(lat)

        # 중심점 기준 상대 좌표
        for lon, lat in coordinates:
            dx = lon - center_lon
            dy = lat - center_lat

            # 정규화된 좌표로 변환 (km 단위)
            dx_norm = dx * lon_scale
            dy_norm = dy * lat_scale
            
            # 회전 변환 (2D 회전 행렬)
            # [x'] = [cos θ  -sin θ] [x]
            # [y'] = [sin θ  +cos θ] [y]
            dx_rot = dx_norm * cos_a - dy_norm * sin_a
            dy_rot = dx_norm * sin_a + dy_norm * cos_a

            # 다시 지리 좌표(위경도)로 변환
            new_lon = center_lon + dx_rot / lon_scale 
            new_lat = center_lat + dy_rot / lat_scale
            
            rotated.append((new_lon, new_lat))

        return rotated

    # 그림 좌표를 목표 거리에 맞게 스케일링한다.
    def scale_drawing_coordinates(
        self,
        drawing_coordinates: List[[LonLat]],
        start_point: [LonLat],
        target_distance: float,
    ) -> List[[LonLat]]:
        """
        Args:
            drawing_coordinates: 원본 그림 좌표 리스트 [(lon, lat), ...]
            start_point: 출발지 좌표 (lon, lat) - 스케일링 기준점
            target_distance: 목표 거리 (미터)

        Returns:
            스케일링된 좌표 리스트
        """
        # 현재 그림의 거리 계산
        current_distance = 0.0
        for i  in range(len(drawing_coordinates) - 1):
            current_distance += haversine_distance(
                drawing_coordinates[i],
                drawing_coordinates[i + 1],
            )

        if current_distance < 1e-6:
            return drawing_coordinates

        # 스케일 비율 계산
        scale_ratio = target_distance / current_distance

        # 출발지를 기준으로 스케일링
        scaled_coords: List[LonLat] = []
        start_lon, start_lat = start_point

        for lon, lat in drawing_coordinates:
            # 출발지로부터의 상대적 위치 계산
            delta_lon = lon - start_lon
            delta_lat = lat - start_lat

            # 스케일링 적용
            scaled_lon = start_lon + delta_lon * scale_ratio
            scaled_lat = start_lat + delta_lat * scale_ratio

            scaled_coords.append((scaled_lon, scaled_lat))

        return scaled_coords

    # 원본 그림과 생성된 경로 유사도 평가
    def calculate_route_similarity(
        self,
        original_drawing: List[[LonLat]],
        generated_route: List[Dict[str, float]],
    ) -> float:
        """
        Args:
            original_drawing: 원본 그림 좌표 리스트 [(lon, lat), ...]
            generated_route: 생성된 경로 좌표 리스트 [{"lat": ..., "lon": ...}, ...]

        Returns:
            유사도 점수 (낮을수록 유사함, 평균 거리 미터 단위)
        """
        if not original_drawing or not generated_route:
            return float('inf')

        # 생성된 경로를 (lon, lat) 튜플로 변환
        route_coords = [(pt["lng"], pt["lat"]) for pt in generated_route] # 카카오 응답 형식

        # 원본 그림을 세그먼트로 분할
        original_segments = []
        for i in range(len(original_drawing) - 1):
            original_segments.append((original_drawing[i], original_drawing[i + 1]))

        # 각 원본 세그먼트에 대해 가장 가까운 경로 점 찾기
        total_distance = 0.0
        segment_count = 0

        for i in range(len(original_segments) - 1):
            s = original_drawing[i]
            e = original_drawing[i + 1]
            min_distance = float('inf')

            # 원본 세그먼트의 중간점들 샘플링
            for k in range(self.n_samples + 1):
                t = k / self.n_samples
                # 세그먼트 위의 점
                lon = s[0] + t * (e[0] - s[0])
                lat = s[1] + t * (e[1] - s[1])
                orig_point = (lon, lat)

                # 생성된 경로에서 가장 가까운 점 찾기
                min_point_dist = float('inf')
                for route_point in route_coords:
                    dist = haversine_distance(orig_point, route_point)
                    if dist < min_point_dist:
                        min_point_dist = dist

                if min_point_dist < min_distance:
                    min_distance = min_point_dist

            total_distance += min_distance
            segment_count += 1

        # 평균 거리 반환
        if segment_count == 0:
            return float('inf')

        return total_distance / segment_count

# 사용 예시
if __name__ == "__main__":
    # 네트워크 가져오기
    fetcher = RoadNetworkFetcher(timeout=30)
    start_point = (37.5007, 127.0369) # 역삼역

    graph = fetcher.fetch_pedestrian_network_from_point(
        center_point=start_point,
        distance=2000,
        network_type='walk',
        simplify=False,
    )

    print(f"네트워크: {graph.number_of_nodes()}개 노드, {graph.number_of_edges()}개 엣지")

    # GPS Art Router 생성
    router = GPSArtRouter()

    # 예시: 그림 좌표 (사용자가 그린 그림)
    drawing_coords = [
        (127.0369, 37.5007),  # 출발지
        (127.0370, 37.5010),
        (127.0375, 37.5015),
        (127.0380, 37.5020),
        (127.0369, 37.5007),  # 다시 출발지로
    ]

    # 목표 거리로 스케일링
    target_distance = 5000 # 5km
    scaled_coords = router.scale_drawing_coordinates(
        drawing_coords,
        start_point=(127.0369, 37.5007),
        target_distance=target_distance
    )

    # 세그먼트로 변환
    segments = []
    for i in range(len(scaled_coords) - 1):
        segments.append((scaled_coords[i], scaled_coords[i + 1]))

    # 경로 생성
    paths = router.find_paths(
        start_point=(127.0369, 37.5007),
        drawing_segments=segments,
        max_paths=2,
    )

    # 각 경로의 정보 출력
    for i, path in enumerate(paths, 1):
        path_info = fetcher.get_path_info(graph, path)
        print(f"\n경로 {i}:")
        print(f"  거리: {path_info['distance_km']:.2f}km")
        print(f"  노드 수: {path_info['node_count']}")