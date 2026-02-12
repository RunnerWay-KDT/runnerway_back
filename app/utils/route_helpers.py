# ============================================
# app/utils/route_helpers.py - 경로 분석 유틸리티
# ============================================

from typing import List, Dict
import math
import networkx as nx
import logging

logger = logging.getLogger(__name__)


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
            diff = float(node_v['elevation']) - float(node_u['elevation'])
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
        
        if edge_data is not None:
            # MultiGraph: {0: {'grade': 0.02, ...}} 형식 처리
            if isinstance(edge_data, dict) and 'grade' not in edge_data:
                first_key = next(iter(edge_data), None)
                if first_key is not None and isinstance(edge_data[first_key], dict):
                    edge_data = edge_data[first_key]
            if isinstance(edge_data, dict) and 'grade' in edge_data:
                grade = abs(float(edge_data['grade'])) * 100  # 백분율로 변환
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

def calculate_gps_art_metrics(G: nx.Graph, path: list) -> dict:
    """
    그림 경로(GPS Art)를 위한 고도 데이터 및 난이도 계산 함수
    
    Args:
        G: NetworkX 그래프 (반드시 고도 데이터 'elevation'이 노드 속성에 있어야 함)
        path: 노드 ID 리스트
        
    Returns:
        DB 'route_options' 테이블 저장용 딕셔너리
        (difficulty, max_elevation_diff, total_ascent, total_descent, 
         total_elevation_change, average_grade, max_grade)
    """
    total_ascent = 0.0
    total_descent = 0.0
    total_elevation_change = 0.0
    grades = []
    elevations = []
    
    # 1. 경로 순회하며 고도 데이터 수집
    for i in range(len(path) - 1):
        u, v = path[i], path[i+1]
        node_u = G.nodes[u]
        node_v = G.nodes[v]
        
        if 'elevation' in node_u and 'elevation' in node_v:
            elev_u = float(node_u['elevation'])
            elev_v = float(node_v['elevation'])
            
            if i == 0:
                elevations.append(elev_u)
            elevations.append(elev_v)
            
            diff = elev_v - elev_u
            total_elevation_change += abs(diff) # 총 변화량 (절대값 누적)
            
            if diff > 0:
                total_ascent += diff # 오르막
            else:
                total_descent += abs(diff) # 내리막
            
            # 엣지 경사도 확인
            edge_data = G.get_edge_data(u, v)
            if edge_data:
                # MultiGraph 처리
                if isinstance(edge_data, dict) and 'grade' not in edge_data:
                    first_key = next(iter(edge_data), None)
                    if first_key is not None:
                        edge_data = edge_data[first_key]
                
                if isinstance(edge_data, dict) and 'grade' in edge_data:
                    grades.append(abs(float(edge_data['grade'])))

    # 2. 통계치 계산 및 예외 처리 (DB 컬럼 범위 초과 방지)
    avg_grade = (sum(grades) / len(grades)) * 100 if grades else 0
    if avg_grade > 99.99: avg_grade = 99.99

    max_grade = max(grades) * 100 if grades else 0
    if max_grade > 99.99: max_grade = 99.99

    max_elev_diff = (max(elevations) - min(elevations)) if elevations else 0

    # 3. 난이도 자동 판별 (그림 경로는 이름이 없으므로 경사도 기준)
    # 3% 미만: 쉬움 / 3%~7%: 보통 / 7% 이상: 도전
    if avg_grade < 3.0:
        difficulty = "쉬움"
    elif avg_grade < 7.0:
        difficulty = "보통"
    else:
        difficulty = "도전"

    logger.info(f"🎨 GPS Art Metrics: ascent={total_ascent}, avg_grade={avg_grade}%, difficulty={difficulty}")

    return {
        "difficulty": difficulty,
        "max_elevation_diff": int(max_elev_diff),
        "total_ascent": round(total_ascent, 2),
        "total_descent": round(total_descent, 2),
        "total_elevation_change": round(total_elevation_change, 2),
        "average_grade": round(avg_grade, 2),
        "max_grade": round(max_grade, 2)
    }

