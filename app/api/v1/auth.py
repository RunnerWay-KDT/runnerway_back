# ============================================
# app/api/v1/auth.py - 인증 API 라우터
# ============================================
# 회원가입, 로그인, 로그아웃, 토큰 갱신 등 인증 관련 API를 제공합니다.
# ============================================

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.services.auth_service import AuthService
from app.schemas.auth import (
    SignupRequest, LoginRequest, KakaoLoginRequest,
    RefreshTokenRequest, LogoutRequest,
    AuthResponse, TokenRefreshResponse, LogoutResponse
)


# APIRouter 인스턴스 생성
# prefix: 모든 엔드포인트 앞에 붙는 경로
# tags: Swagger UI에서 그룹화할 태그
router = APIRouter(prefix="/auth", tags=["Authentication"])


# ============================================
# 회원가입 API
# ============================================
@router.post(
    "/signup",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="회원가입",
    description="""
    새로운 사용자를 등록합니다.
    
    **요청 조건:**
    - 이메일: 유효한 이메일 형식, 중복 불가
    - 비밀번호: 최소 6자 이상
    - 이름: 최소 1자 이상
    
    **응답:**
    - 회원가입 성공 시 자동 로그인 처리
    - 액세스 토큰과 리프레시 토큰 발급
    """
)
def signup(
    request: SignupRequest,
    db: Session = Depends(get_db)
):
    """
    회원가입 엔드포인트
    
    [신입 개발자를 위한 팁]
    - @router.post(): POST 요청을 처리하는 데코레이터
    - response_model: 응답 데이터의 형식을 지정 (자동 검증)
    - status_code: 성공 시 반환할 HTTP 상태 코드
    - Depends(get_db): 데이터베이스 세션 주입
    """
    # AuthService 인스턴스 생성 (DB 세션 전달)
    auth_service = AuthService(db)
    
    # 회원가입 처리
    auth_data = auth_service.signup(request)
    
    # 응답 반환
    return AuthResponse(
        success=True,
        data=auth_data,
        message="회원가입이 완료되었습니다"
    )


# ============================================
# 이메일 로그인 API
# ============================================
@router.post(
    "/login",
    response_model=AuthResponse,
    summary="이메일 로그인",
    description="""
    이메일과 비밀번호로 로그인합니다.
    
    **응답:**
    - 로그인 성공 시 사용자 정보와 토큰 반환
    - 실패 시 401 에러
    """
)
def login(
    request: LoginRequest,
    db: Session = Depends(get_db)
):
    """이메일 로그인 엔드포인트"""
    auth_service = AuthService(db)
    auth_data = auth_service.login(request)
    
    return AuthResponse(
        success=True,
        data=auth_data,
        message="로그인되었습니다"
    )


# ============================================
# 카카오 소셜 로그인 API
# ============================================
@router.post(
    "/social/kakao",
    response_model=AuthResponse,
    summary="카카오 소셜 로그인",
    description="""
    카카오 액세스 토큰으로 로그인합니다.
    
    **흐름:**
    1. 프론트엔드에서 카카오 SDK로 로그인
    2. 카카오 액세스 토큰과 프로필 정보를 백엔드로 전송
    3. 백엔드에서 토큰 검증 후 회원가입/로그인 처리
    
    **응답:**
    - is_new_user: 신규 가입 여부
    - 신규 가입 시 자동으로 계정 생성
    """
)
async def kakao_login(
    request: KakaoLoginRequest,
    db: Session = Depends(get_db)
):
    """
    카카오 소셜 로그인 엔드포인트
    
    [신입 개발자를 위한 팁]
    - async def: 비동기 함수 (외부 API 호출이 있어서 비동기로 처리)
    - 카카오 API 호출은 시간이 걸리므로 비동기로 처리하여
      서버가 다른 요청도 동시에 처리할 수 있게 함
    """
    auth_service = AuthService(db)
    auth_data, is_new_user = await auth_service.kakao_login(request)
    
    # is_new_user 정보 추가
    auth_data.is_new_user = is_new_user
    
    return AuthResponse(
        success=True,
        data=auth_data,
        message="로그인되었습니다"
    )


# ============================================
# 토큰 갱신 API
# ============================================
@router.post(
    "/refresh",
    response_model=TokenRefreshResponse,
    summary="액세스 토큰 갱신",
    description="""
    리프레시 토큰으로 새로운 액세스 토큰을 발급받습니다.
    
    **사용 시점:**
    - 액세스 토큰 만료 시 (1시간)
    - 401 에러 발생 시 자동으로 호출
    
    **주의사항:**
    - 리프레시 토큰도 만료되면 재로그인 필요
    """
)
def refresh_token(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """토큰 갱신 엔드포인트"""
    auth_service = AuthService(db)
    new_access_token, expires_in = auth_service.refresh_access_token(request.refresh_token)
    
    return TokenRefreshResponse(
        success=True,
        data={
            "access_token": new_access_token,
            "expires_in": expires_in
        },
        message="토큰이 갱신되었습니다"
    )


# ============================================
# 로그아웃 API
# ============================================
@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="로그아웃",
    description="""
    현재 세션을 종료합니다.
    
    **처리 내용:**
    - 서버에서 리프레시 토큰 무효화
    - 클라이언트에서 로컬 토큰 삭제 필요
    """
)
def logout(
    request: LogoutRequest = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    로그아웃 엔드포인트
    
    [신입 개발자를 위한 팁]
    - Depends(get_current_user): 인증이 필요한 엔드포인트
    - current_user: 현재 로그인한 사용자 객체가 자동으로 주입됨
    """
    auth_service = AuthService(db)
    refresh_token = request.refresh_token if request else None
    auth_service.logout(current_user.id, refresh_token)
    
    return LogoutResponse(
        success=True,
        message="로그아웃되었습니다"
    )
