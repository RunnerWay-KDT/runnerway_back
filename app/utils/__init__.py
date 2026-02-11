"""
유틸리티 모듈
기하학 계산 등 공통 유틸리티 함수를 제공합니다.
"""

from .geometry import has_self_intersection, segments_intersect, ccw

__all__ = ['has_self_intersection', 'segments_intersect', 'ccw']
