# ============================================
# app/api/deps.py - API 의존성
# ============================================
# FastAPI의 Dependency Injection에서 사용하는 공통 의존성을 정의합니다.
# ============================================

from typing import Generator, Optional
from fastapi import Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.core.security import verify_access_token
from app.core.exceptions import UnauthorizedException, UserNotFoundException
from app.models.user import User


# HTTP Bearer 인증 스킴 (Swagger UI에서 인증 버튼 표시)
security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    현재 로그인한 사용자를 반환하는 의존성 함수
    
    Authorization 헤더에서 JWT 토큰을 추출하고 검증합니다.
    
    [신입 개발자를 위한 팁]
    - Depends(): FastAPI의 의존성 주입 시스템
    - 이 함수를 라우터 파라미터에 추가하면 자동으로 인증 체크
    - 인증 실패 시 401 에러가 자동으로 반환됨
    
    사용 예시:
        @router.get("/me")
        def get_my_profile(
            current_user: User = Depends(get_current_user)
        ):
            return current_user
    
    Args:
        credentials: HTTP Bearer 인증 정보
        db: 데이터베이스 세션
        
    Returns:
        User: 현재 로그인한 사용자 객체
        
    Raises:
        UnauthorizedException: 인증 토큰이 없거나 유효하지 않은 경우
        UserNotFoundException: 토큰은 유효하지만 사용자가 존재하지 않는 경우
    """
    # 1. 토큰 존재 확인
    if not credentials:
        raise UnauthorizedException()
    
    token = credentials.credentials
    
    # 2. 토큰 검증
    user_id = verify_access_token(token)
    if not user_id:
        raise UnauthorizedException(
            message="유효하지 않은 토큰입니다",
            error_code="INVALID_TOKEN"
        )
    
    # 3. 사용자 조회
    user = db.query(User).filter(
        User.id == user_id,
        User.deleted_at.is_(None)
    ).first()
    
    if not user:
        raise UserNotFoundException()
    
    return user


def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    현재 사용자를 반환 (선택적 인증)
    
    인증이 필수가 아닌 엔드포인트에서 사용합니다.
    토큰이 없거나 유효하지 않아도 에러를 발생시키지 않고 None을 반환합니다.
    
    사용 예시:
        @router.get("/posts")
        def get_posts(
            current_user: Optional[User] = Depends(get_current_user_optional)
        ):
            # 로그인한 경우와 아닌 경우 다르게 처리
            if current_user:
                # 내가 좋아요 눌렀는지 등 추가 정보 포함
                pass
    
    Args:
        credentials: HTTP Bearer 인증 정보 (선택)
        db: 데이터베이스 세션
        
    Returns:
        Optional[User]: 사용자 객체 또는 None
    """
    if not credentials:
        return None
    
    try:
        return get_current_user(credentials, db)
    except (UnauthorizedException, UserNotFoundException):
        return None


# ============================================
# 편의 타입 별칭
# ============================================

# DB 세션 의존성 타입 별칭
DatabaseSession = Session

# 현재 사용자 의존성 타입 별칭  
CurrentUser = User
