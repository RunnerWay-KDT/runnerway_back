# ============================================
# app/utils/route_helpers.py - 경로 분석 유틸리티
# ============================================

from typing import List, Dict
import math


def calculate_turn_count(coords: List[Dict[str, float]], angle_threshold: float = 45.0) -> int:
    """
    경로의 방향 전환 횟수를 계산합니다.
    
    Args:
        coords: 경로 좌표 리스트 [{"lat": float, "lng": float}, ...]
        angle_threshold: 방향 전환으로 간주할 최소 각도 (기본 45도)
    
    Returns:
        int: 방향 전환 횟수
    """
    if len(coords) < 3:
        return 0
    
    turn_count = 0
    
    for i in range(1, len(coords) - 1):
        prev_point = coords[i - 1]
        curr_point = coords[i]
        next_point = coords[i + 1]
        
        # 이전 세그먼트와 다음 세그먼트의 방위각 계산
        angle1 = calculate_bearing(prev_point, curr_point)
        angle2 = calculate_bearing(curr_point, next_point)
        
        # 각도 차이 계산 (0-180도 범위로)
        angle_diff = abs(angle2 - angle1)
        if angle_diff > 180:
            angle_diff = 360 - angle_diff
        
        # 임계값 이상이면 방향 전환으로 간주
        if angle_diff >= angle_threshold:
            turn_count += 1
    
    return turn_count


def calculate_bearing(point1: Dict[str, float], point2: Dict[str, float]) -> float:
    """
    두 점 사이의 방위각(bearing)을 계산합니다.
    
    Args:
        point1: 시작점 {"lat": float, "lng": float}
        point2: 끝점 {"lat": float, "lng": float}
    
    Returns:
        float: 방위각 (0-360도)
    """
    lat1 = math.radians(point1['lat'])
    lat2 = math.radians(point2['lat'])
    lng_diff = math.radians(point2['lng'] - point1['lng'])
    
    x = math.sin(lng_diff) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - (
        math.sin(lat1) * math.cos(lat2) * math.cos(lng_diff)
    )
    
    bearing = math.atan2(x, y)
    bearing_degrees = math.degrees(bearing)
    
    # 0-360도 범위로 정규화
    return (bearing_degrees + 360) % 360


def calculate_total_descent(graph, path: List[int]) -> float:
    """
    경로의 총 하강 고도를 계산합니다.
    
    Args:
        graph: NetworkX 그래프
        path: 노드 ID 리스트
    
    Returns:
        float: 총 하강 고도 (m)
    """
    total_descent = 0.0
    
    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]
        node_u = graph.nodes[u]
        node_v = graph.nodes[v]
        
        if 'elevation' in node_u and 'elevation' in node_v:
            diff = node_v['elevation'] - node_u['elevation']
            if diff < 0:  # 하강
                total_descent += abs(diff)
    
    return round(total_descent, 2)


def calculate_max_grade(graph, path: List[int]) -> float:
    """
    경로의 최대 경사도를 계산합니다.
    
    Args:
        graph: NetworkX 그래프
        path: 노드 ID 리스트
    
    Returns:
        float: 최대 경사도 (%)
    """
    max_grade = 0.0
    
    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]
        edge_data = graph.get_edge_data(u, v)
        
        if isinstance(edge_data, dict) and 'grade' in edge_data:
            grade = abs(edge_data['grade']) * 100  # 백분율로 변환
            max_grade = max(max_grade, grade)
    
    return round(max_grade, 2)


def format_pace_string(pace_min_per_km: float) -> str:
    """
    페이스를 문자열로 포맷팅합니다.
    
    Args:
        pace_min_per_km: 페이스 (분/km)
    
    Returns:
        str: 포맷된 페이스 (예: "7:30")
    """
    minutes = int(pace_min_per_km)
    seconds = int((pace_min_per_km % 1) * 60)
    return f"{minutes}:{seconds:02d}"
