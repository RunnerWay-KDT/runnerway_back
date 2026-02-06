# ============================================
# app/services/__init__.py
# ============================================
# 비즈니스 로직 서비스 패키지 초기화
# ============================================

"""
서비스 모듈

비즈니스 로직을 담당하는 서비스들을 제공합니다.

[신입 개발자를 위한 팁]
- 서비스 레이어는 API 엔드포인트(라우터)와 데이터베이스(모델) 사이에서
  실제 비즈니스 로직을 처리합니다.
- 라우터는 요청/응답만 처리하고, 실제 로직은 서비스에서 처리합니다.
- 이렇게 분리하면 코드 재사용성과 테스트 용이성이 높아집니다.

[아키텍처 흐름]
요청 → 라우터(API) → 서비스(비즈니스 로직) → 모델(DB) → 응답
"""

from app.services.kakao_service import KakaoService
from app.services.auth_service import AuthService
from app.services.route_service import RouteService
from app.services.workout_service import WorkoutService
from app.services.community_service import CommunityService
from app.services.gps_art_service import generate_gps_art_impl


__all__ = [
    "KakaoService",
    "AuthService",
    "RouteService",
    "WorkoutService",
    "CommunityService",
    "generate_gps_art_impl",
]
