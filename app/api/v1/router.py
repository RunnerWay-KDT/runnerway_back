# ============================================
# app/api/v1/router.py - API v1 메인 라우터
# ============================================
# 모든 API v1 라우터를 통합하는 메인 라우터입니다.
# 각 도메인별 라우터를 하나로 묶어서 main.py에서 사용합니다.
# ============================================

from fastapi import APIRouter

# 각 도메인별 라우터 import
from app.api.v1.auth import router as auth_router
from app.api.v1.users import router as users_router
from app.api.v1.routes import router as routes_router
from app.api.v1.workouts import router as workouts_router
from app.api.v1.community import router as community_router


# ============================================
# 메인 라우터 생성
# ============================================
# 모든 v1 API의 공통 prefix를 설정합니다.
# 최종 URL은 /api/v1/{도메인}/{엔드포인트} 형태가 됩니다.
# ============================================
api_router = APIRouter()


# ============================================
# 라우터 등록
# ============================================
# 각 도메인별 라우터를 메인 라우터에 등록합니다.
# 
# 예시:
# - /api/v1/auth/... -> 인증 관련 API
# - /api/v1/users/... -> 사용자 관련 API
# - /api/v1/routes/... -> 경로 관련 API
# - /api/v1/workouts/... -> 운동 관련 API
# - /api/v1/community/... -> 커뮤니티 관련 API
# ============================================

# 인증 관련 API (회원가입, 로그인, 토큰 갱신 등)
api_router.include_router(
    auth_router,
    tags=["Authentication"]  # Swagger UI에서 그룹화
)

# 사용자 관련 API (프로필, 설정, 통계 등)
api_router.include_router(
    users_router,
    tags=["Users"]
)

# 경로 관련 API (경로 생성, 조회, 저장 등)
api_router.include_router(
    routes_router,
    tags=["Routes"]
)

# 운동 관련 API (운동 시작, 트래킹, 완료 등)
api_router.include_router(
    workouts_router,
    tags=["Workouts"]
)

# 커뮤니티 관련 API (피드, 게시글, 댓글 등)
api_router.include_router(
    community_router,
    tags=["Community"]
)


# ============================================
# 추가 예정 라우터
# ============================================
# 향후 기능 확장 시 아래 라우터들을 추가할 수 있습니다:
#
# - notifications_router: 알림 관련 API
# - admin_router: 관리자 전용 API
# - analytics_router: 분석/통계 API
# - payments_router: 결제 관련 API (프리미엄 기능 시)
# ============================================
