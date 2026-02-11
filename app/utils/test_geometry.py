"""
geometry.py 모듈의 단위 테스트
자기 교차 감지 알고리즘의 동작을 검증합니다.
"""

import unittest
from app.utils.geometry import ccw, segments_intersect, has_self_intersection


class TestCCWAlgorithm(unittest.TestCase):
    """CCW 알고리즘 테스트"""
    
    def test_ccw_counterclockwise(self):
        """반시계방향 테스트"""
        A = (0, 0)
        B = (1, 0)
        C = (0, 1)
        result = ccw(A, B, C)
        self.assertGreater(result, 0, "반시계방향이어야 합니다")
    
    def test_ccw_clockwise(self):
        """시계방향 테스트"""
        A = (0, 0)
        B = (0, 1)
        C = (1, 0)
        result = ccw(A, B, C)
        self.assertLess(result, 0, "시계방향이어야 합니다")
    
    def test_ccw_collinear(self):
        """일직선상 테스트"""
        A = (0, 0)
        B = (1, 0)
        C = (2, 0)
        result = ccw(A, B, C)
        self.assertEqual(result, 0, "일직선상이어야 합니다")


class TestSegmentIntersection(unittest.TestCase):
    """선분 교차 테스트"""
    
    def test_intersecting_segments(self):
        """교차하는 선분"""
        # X자 형태
        seg1 = ((0, 0), (2, 2))
        seg2 = ((0, 2), (2, 0))
        self.assertTrue(segments_intersect(seg1, seg2), "두 선분이 교차해야 합니다")
    
    def test_non_intersecting_parallel(self):
        """평행하고 교차하지 않는 선분"""
        seg1 = ((0, 0), (2, 0))
        seg2 = ((0, 1), (2, 1))
        self.assertFalse(segments_intersect(seg1, seg2), "평행 선분은 교차하지 않아야 합니다")
    
    def test_non_intersecting_distant(self):
        """멀리 떨어진 선분"""
        seg1 = ((0, 0), (1, 0))
        seg2 = ((10, 10), (11, 11))
        self.assertFalse(segments_intersect(seg1, seg2), "멀리 떨어진 선분은 교차하지 않아야 합니다")
    
    def test_touching_endpoints(self):
        """끝점이 닿는 경우 (자연스러운 연결)"""
        seg1 = ((0, 0), (1, 1))
        seg2 = ((1, 1), (2, 0))
        self.assertFalse(segments_intersect(seg1, seg2), "끝점이 닿는 경우는 교차로 보지 않아야 합니다")
    
    def test_t_intersection(self):
        """T자 교차"""
        seg1 = ((0, 0), (2, 0))
        seg2 = ((1, -1), (1, 1))
        self.assertTrue(segments_intersect(seg1, seg2), "T자로 교차해야 합니다")


class TestSelfIntersection(unittest.TestCase):
    """경로 자기 교차 테스트"""
    
    def test_figure_eight_path(self):
        """8자 형태 경로 (교차함)"""
        path = [
            {"lat": 0.0, "lng": 0.0},
            {"lat": 1.0, "lng": 1.0},
            {"lat": 1.0, "lng": 0.0},
            {"lat": 0.0, "lng": 1.0},
            {"lat": 0.0, "lng": 0.0}
        ]
        self.assertTrue(has_self_intersection(path), "8자 경로는 교차해야 합니다")
    
    def test_simple_square_path(self):
        """단순 사각형 경로 (교차 안 함)"""
        path = [
            {"lat": 0.0, "lng": 0.0},
            {"lat": 0.0, "lng": 1.0},
            {"lat": 1.0, "lng": 1.0},
            {"lat": 1.0, "lng": 0.0},
            {"lat": 0.0, "lng": 0.0}
        ]
        self.assertFalse(has_self_intersection(path), "단순 사각형은 교차하지 않아야 합니다")
    
    def test_simple_circle_path(self):
        """원형 경로 (교차 안 함)"""
        import math
        path = []
        for i in range(8):
            angle = 2 * math.pi * i / 8
            path.append({
                "lat": math.cos(angle),
                "lng": math.sin(angle)
            })
        path.append({"lat": 1.0, "lng": 0.0})  # 시작점으로 돌아옴
        self.assertFalse(has_self_intersection(path), "원형 경로는 교차하지 않아야 합니다")
    
    def test_straight_line(self):
        """일직선 경로 (교차 불가능)"""
        path = [
            {"lat": 0.0, "lng": 0.0},
            {"lat": 1.0, "lng": 0.0},
            {"lat": 2.0, "lng": 0.0}
        ]
        self.assertFalse(has_self_intersection(path), "일직선은 교차할 수 없습니다")
    
    def test_too_short_path(self):
        """너무 짧은 경로 (교차 불가능)"""
        path = [
            {"lat": 0.0, "lng": 0.0},
            {"lat": 1.0, "lng": 0.0}
        ]
        self.assertFalse(has_self_intersection(path), "선분이 하나뿐이면 교차할 수 없습니다")
    
    def test_complex_intersecting_path(self):
        """복잡한 교차 경로"""
        # 별 모양 (중앙에서 교차)
        path = [
            {"lat": 0.0, "lng": 1.0},   # 상단
            {"lat": 1.0, "lng": -0.5},  # 우하단
            {"lat": -1.0, "lng": 0.3},  # 좌측
            {"lat": 1.0, "lng": 0.3},   # 우측
            {"lat": -1.0, "lng": -0.5}, # 좌하단
            {"lat": 0.0, "lng": 1.0}    # 시작점으로
        ]
        self.assertTrue(has_self_intersection(path), "별 모양은 교차해야 합니다")
    
    def test_u_turn_path(self):
        """U턴 경로 (교차 안 함)"""
        path = [
            {"lat": 0.0, "lng": 0.0},
            {"lat": 0.0, "lng": 1.0},
            {"lat": 1.0, "lng": 1.0},
            {"lat": 1.0, "lng": 0.0}
        ]
        self.assertFalse(has_self_intersection(path), "U턴은 교차하지 않아야 합니다")


if __name__ == '__main__':
    unittest.main()
