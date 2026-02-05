# ============================================
# app/main.py - FastAPI 애플리케이션 시작점
# ============================================
# 이 파일은 FastAPI 서버의 진입점(Entry Point)입니다.
# 서버를 시작하면 이 파일이 가장 먼저 실행됩니다.
# ============================================

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 설정 불러오기
from app.config import settings
# API 라우터 불러오기
from app.api.v1.router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    애플리케이션 생명주기 관리
    
    FastAPI가 시작하고 종료할 때 실행되는 코드를 정의합니다.
    
    [신입 개발자를 위한 팁]
    - yield 전: 서버 시작 시 실행되는 코드 (초기화)
    - yield 후: 서버 종료 시 실행되는 코드 (정리)
    - asynccontextmanager는 비동기 컨텍스트 매니저를 만들어줍니다.
    """
    # ========== 서버 시작 시 실행 ==========
    print("러너웨이 서버를 시작합니다...")
    print(f"환경: {settings.ENVIRONMENT}")
    print(f"디버그 모드: {settings.DEBUG}")
    
    yield  # 여기서 서버가 실행됩니다
    
    # ========== 서버 종료 시 실행 ==========
    print("러너웨이 서버를 종료합니다...")


# ============================================
# FastAPI 애플리케이션 인스턴스 생성
# ============================================
app = FastAPI(
    # 앱 제목 (API 문서에 표시됨)
    title="러너웨이 API",
    
    # 앱 설명 (API 문서에 표시됨)
    description="""
    ## 🏃‍♂️ 러너웨이 - 나만의 그림 경로로 러닝을 시작하세요!
    
    ### 주요 기능
    - 🔐 **인증**: 카카오 소셜 로그인
    - 👤 **사용자**: 프로필 관리, 통계 조회
    - 🗺️ **경로**: AI 기반 도형 경로 생성
    - 🏃 **운동**: 실시간 GPS 기반 운동 추적
    - 👥 **커뮤니티**: 운동 결과 공유 및 소셜 기능
    """,
    
    # API 버전
    version="1.0.0",
    
    # 생명주기 관리자
    lifespan=lifespan,
    
    # API 문서 URL (기본: /docs)
    docs_url="/docs",
    
    # ReDoc 문서 URL (기본: /redoc)
    redoc_url="/redoc",
    
    # OpenAPI 스키마 URL
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json"
)


# ============================================
# CORS (Cross-Origin Resource Sharing) 설정
# ============================================
# CORS는 다른 도메인에서 API를 호출할 수 있게 해주는 보안 기능입니다.
# 프론트엔드(React Native/Expo)에서 백엔드 API를 호출하려면 필수입니다.
#
# [신입 개발자를 위한 팁]
# - allow_origins: 허용할 프론트엔드 도메인 목록
# - allow_credentials: 쿠키 전송 허용 여부
# - allow_methods: 허용할 HTTP 메서드 (GET, POST 등)
# - allow_headers: 허용할 HTTP 헤더
# ============================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,  # 허용할 도메인
    allow_credentials=True,                     # 쿠키 허용
    allow_methods=["*"],                        # 모든 HTTP 메서드 허용
    allow_headers=["*"],                        # 모든 헤더 허용
)


# ============================================
# API 라우터 등록
# ============================================
# 모든 API 엔드포인트는 /api/v1 경로 아래에 위치합니다.
# 예: /api/v1/auth/login, /api/v1/users/me 등
# ============================================
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


# ============================================
# 루트 엔드포인트 (서버 상태 확인용)
# ============================================
@app.get("/", tags=["Health Check"])
async def root():
    """
    서버 상태 확인 엔드포인트
    
    서버가 정상적으로 실행 중인지 확인할 때 사용합니다.
    브라우저에서 http://localhost:8000/ 으로 접속하면 확인 가능합니다.
    
    [신입 개발자를 위한 팁]
    - @app.get("/")는 HTTP GET 요청을 처리하는 데코레이터입니다.
    - tags=["Health Check"]는 API 문서에서 그룹화하기 위한 태그입니다.
    - async 함수는 비동기 함수로, 여러 요청을 동시에 처리할 수 있습니다.
    """
    return {
        "status": "ok",
        "message": "러너웨이 API 서버가 실행 중입니다!",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health", tags=["Health Check"])
async def health_check():
    """
    상세 헬스체크 엔드포인트
    
    서버의 상세 상태를 확인합니다.
    주로 로드밸런서나 모니터링 시스템에서 사용합니다.
    """
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "debug": settings.DEBUG
    }


# ============================================
# 직접 실행 시 (python app/main.py)
# ============================================
# 보통은 uvicorn 명령어로 실행하지만,
# 디버깅 목적으로 직접 실행할 수도 있습니다.
# ============================================
if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",  # 앱 경로 (모듈:변수)
        host="0.0.0.0",  # 모든 IP에서 접속 허용
        port=8000,        # 포트 번호
        reload=True,       # 코드 변경 시 자동 재시작
        reload_excludes=["venv/*"]  # venv 폴더는 제외
    )
