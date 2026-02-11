"""
SVG Path 단순화 유틸리티

OpenCV를 사용하여 SVG path의 좌표를 단순화합니다.
더글라스-포이커(Douglas-Peucker) 알고리즘을 사용하여 시각적 품질을 유지하면서 
좌표 개수를 줄입니다.
"""

import re
import numpy as np
import cv2
from typing import List, Tuple


def parse_svg_path(svg_path: str) -> List[Tuple[float, float]]:
    """
    SVG path 문자열을 좌표 리스트로 파싱
    
    Args:
        svg_path: SVG path 문자열 (예: "M 10 20 L 30 40 L 50 60")
    
    Returns:
        좌표 튜플 리스트 [(x1, y1), (x2, y2), ...]
    """
    # M, L, C 등의 명령어와 숫자 추출
    # 숫자는 정수 또는 소수점, 음수 가능
    numbers = re.findall(r'-?\d+\.?\d*', svg_path)
    
    if len(numbers) < 2:
        return []
    
    # 좌표 쌍으로 변환
    points = []
    for i in range(0, len(numbers) - 1, 2):
        x = float(numbers[i])
        y = float(numbers[i + 1])
        points.append((x, y))
    
    return points


def simplify_svg_path(svg_path: str, epsilon: float = 2.0) -> str:
    """
    OpenCV의 Douglas-Peucker 알고리즘을 사용하여 SVG path 단순화
    
    Args:
        svg_path: 원본 SVG path 문자열
        epsilon: 단순화 정도 (작을수록 원본에 가까움, 클수록 많이 단순화)
                 기본값 2.0은 2픽셀 이내의 오차를 허용
    
    Returns:
        단순화된 SVG path 문자열
    """
    if not svg_path or not svg_path.strip():
        return svg_path
    
    # SVG path를 좌표 리스트로 변환
    points = parse_svg_path(svg_path)
    
    if len(points) < 3:
        # 점이 2개 이하면 단순화 불필요
        return svg_path
    
    # numpy 배열로 변환 (OpenCV 입력 형식)
    points_array = np.array(points, dtype=np.float32)
    
    # Douglas-Peucker 알고리즘 적용
    # approxPolyDP: 다각형 근사 함수
    # epsilon: 원본 곡선과 근사 곡선 사이의 최대 거리
    # closed: False (열린 곡선)
    simplified = cv2.approxPolyDP(points_array, epsilon, closed=False)
    
    # 단순화된 좌표를 SVG path 형식으로 변환
    if len(simplified) == 0:
        return svg_path
    
    # SVG path 문자열 생성
    path_parts = []
    first_point = None
    
    for i, point in enumerate(simplified):
        x, y = point[0]
        if i == 0:
            first_point = (x, y)
            path_parts.append(f"M {x:.2f} {y:.2f}")
        else:
            path_parts.append(f"L {x:.2f} {y:.2f}")
    
    # 경로를 닫기 위해 첫 번째 점을 마지막에 추가 (Z 대신 명시적으로)
    if first_point and len(simplified) > 2:
        last_point = simplified[-1][0]
        # 마지막 점이 첫 번째 점과 다르면 첫 번째 점 추가
        if abs(last_point[0] - first_point[0]) > 0.01 or abs(last_point[1] - first_point[1]) > 0.01:
            path_parts.append(f"L {first_point[0]:.2f} {first_point[1]:.2f}")
    
    simplified_path = " ".join(path_parts)
    
    return simplified_path


def get_simplification_stats(original_path: str, simplified_path: str) -> dict:
    """
    단순화 전후 통계 정보 반환
    
    Args:
        original_path: 원본 SVG path
        simplified_path: 단순화된 SVG path
    
    Returns:
        통계 정보 딕셔너리
    """
    original_points = parse_svg_path(original_path)
    simplified_points = parse_svg_path(simplified_path)
    
    original_count = len(original_points)
    simplified_count = len(simplified_points)
    
    if original_count == 0:
        reduction_rate = 0
    else:
        reduction_rate = (1 - simplified_count / original_count) * 100
    
    return {
        "original_points": original_count,
        "simplified_points": simplified_count,
        "reduction_rate": round(reduction_rate, 2),
        "original_length": len(original_path),
        "simplified_length": len(simplified_path),
    }


# 테스트용 예제
if __name__ == "__main__":
    # 예제 SVG path (닫힌 도형)
    test_path = "M 10 10 L 20 15 L 30 20 L 40 25 L 50 30 L 55 40 L 50 50 L 40 55 L 30 50 L 20 45 L 15 35 L 10 25"
    
    print("원본 path:", test_path)
    print(f"원본 포인트 수: {len(parse_svg_path(test_path))}")
    
    # epsilon 값에 따른 단순화
    for eps in [1.0, 2.0, 5.0]:
        simplified = simplify_svg_path(test_path, epsilon=eps)
        stats = get_simplification_stats(test_path, simplified)
        
        print(f"\n[epsilon={eps}]")
        print(f"단순화된 path: {simplified}")
        print(f"통계: {stats}")
        
        # 첫 점과 마지막 점이 같은지 확인
        points = parse_svg_path(simplified)
        if len(points) > 1:
            first = points[0]
            last = points[-1]
            is_closed = abs(first[0] - last[0]) < 0.1 and abs(first[1] - last[1]) < 0.1
            print(f"경로 닫힘: {is_closed} (첫점: {first}, 마지막점: {last})")
