"""
기하학 계산 유틸리티
경로의 자기 교차 감지를 위한 선분 교차 알고리즘을 제공합니다.
"""

import logging
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)


def ccw(A: Tuple[float, float], B: Tuple[float, float], C: Tuple[float, float]) -> float:
    """
    Counter-Clockwise 알고리즘으로 세 점의 방향성을 판단합니다.
    
    벡터 외적(Cross Product)을 계산하여:
    - 양수: 반시계방향 (CCW)
    - 0: 일직선상
    - 음수: 시계방향 (CW)
    
    Args:
        A: 첫 번째 점 (lat, lng)
        B: 두 번째 점 (lat, lng)
        C: 세 번째 점 (lat, lng)
    
    Returns:
        float: 외적 값
    """
    return (B[0] - A[0]) * (C[1] - A[1]) - (B[1] - A[1]) * (C[0] - A[0])


def segments_intersect(
    seg1: Tuple[Tuple[float, float], Tuple[float, float]],
    seg2: Tuple[Tuple[float, float], Tuple[float, float]],
    tolerance: float = 0.0001
) -> bool:
    """
    두 선분이 교차하는지 판단합니다.
    
    CCW 알고리즘을 사용하여 선분 교차를 판정합니다.
    두 선분이 서로를 가로지르는 경우에만 True를 반환합니다.
    
    Args:
        seg1: 첫 번째 선분 ((A_lat, A_lng), (B_lat, B_lng))
        seg2: 두 번째 선분 ((C_lat, C_lng), (D_lat, D_lng))
        tolerance: 부동소수점 오차 허용 범위
    
    Returns:
        bool: 두 선분이 교차하면 True, 아니면 False
    
    Examples:
        >>> seg1 = ((0, 0), (2, 2))
        >>> seg2 = ((0, 2), (2, 0))
        >>> segments_intersect(seg1, seg2)
        True
        
        >>> seg1 = ((0, 0), (1, 0))
        >>> seg2 = ((2, 0), (3, 0))
        >>> segments_intersect(seg1, seg2)
        False
    """
    A, B = seg1
    C, D = seg2
    
    # 선분 끝점이 겹치는 경우는 교차로 보지 않음 (자연스러운 연결)
    if A == C or A == D or B == C or B == D:
        return False
    
    # CCW 값 계산
    ccw1 = ccw(A, B, C)
    ccw2 = ccw(A, B, D)
    ccw3 = ccw(C, D, A)
    ccw4 = ccw(C, D, B)
    
    # 두 선분이 교차하려면: 
    # - 선분1을 기준으로 C와 D가 양쪽에 위치
    # - 선분2를 기준으로 A와 B가 양쪽에 위치
    if ccw1 * ccw2 < 0 and ccw3 * ccw4 < 0:
        return True
    
    return False


def has_self_intersection(
    path_coords: List[Dict[str, float]],
    tolerance: float = 0.0001
) -> bool:
    """
    경로가 자기 자신과 교차하는지 확인합니다.
    
    경로의 모든 선분 쌍을 검사하여 하나라도 교차하면 True를 반환합니다.
    인접한 선분끼리는 자연스럽게 연결되므로 검사하지 않습니다.
    
    Args:
        path_coords: 경로 좌표 리스트 [{"lat": float, "lng": float}, ...]
        tolerance: 부동소수점 오차 허용 범위
    
    Returns:
        bool: 자기 교차가 있으면 True, 없으면 False
    
    Examples:
        >>> # 8자 형태 경로 (교차함)
        >>> path = [
        ...     {"lat": 0, "lng": 0},
        ...     {"lat": 1, "lng": 1},
        ...     {"lat": 1, "lng": 0},
        ...     {"lat": 0, "lng": 1}
        ... ]
        >>> has_self_intersection(path)
        True
        
        >>> # 단순 사각형 경로 (교차 안 함)
        >>> path = [
        ...     {"lat": 0, "lng": 0},
        ...     {"lat": 0, "lng": 1},
        ...     {"lat": 1, "lng": 1},
        ...     {"lat": 1, "lng": 0}
        ... ]
        >>> has_self_intersection(path)
        False
    """
    if not path_coords or len(path_coords) < 4:
        # 선분이 2개 미만이면 교차 불가능
        return False
    
    n = len(path_coords)
    
    # 모든 선분 쌍을 검사
    for i in range(n - 1):
        seg1_start = (path_coords[i]['lat'], path_coords[i]['lng'])
        seg1_end = (path_coords[i + 1]['lat'], path_coords[i + 1]['lng'])
        seg1 = (seg1_start, seg1_end)
        
        # i번째 선분과 (i+2)번째 이후 선분들을 비교
        # (i+1)번째는 인접 선분이므로 스킵
        for j in range(i + 2, n - 1):
            seg2_start = (path_coords[j]['lat'], path_coords[j]['lng'])
            seg2_end = (path_coords[j + 1]['lat'], path_coords[j + 1]['lng'])
            seg2 = (seg2_start, seg2_end)
            
            if segments_intersect(seg1, seg2, tolerance):
                logger.debug(
                    f"Self-intersection detected between segment {i}-{i+1} "
                    f"and segment {j}-{j+1}"
                )
                return True
    
    return False


def calculate_path_bbox(path_coords: List[Dict[str, float]]) -> Dict[str, float]:
    """
    경로의 Bounding Box를 계산합니다.
    
    Args:
        path_coords: 경로 좌표 리스트
    
    Returns:
        dict: {"min_lat": float, "max_lat": float, "min_lng": float, "max_lng": float}
    """
    if not path_coords:
        return {"min_lat": 0, "max_lat": 0, "min_lng": 0, "max_lng": 0}
    
    lats = [coord['lat'] for coord in path_coords]
    lngs = [coord['lng'] for coord in path_coords]
    
    return {
        "min_lat": min(lats),
        "max_lat": max(lats),
        "min_lng": min(lngs),
        "max_lng": max(lngs)
    }
