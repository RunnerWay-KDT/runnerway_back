# ============================================
# app/services/auth_service.py - 인증 서비스
# ============================================
# 회원가입, 로그인, 토큰 관리 등 인증 관련 비즈니스 로직을 처리합니다.
# ============================================

from datetime import datetime, timedelta
from typing import Optional, Tuple
from sqlalchemy.orm import Session

from app.models.user import User, UserStats, UserSettings, RefreshToken
from app.schemas.auth import (
    SignupRequest, LoginRequest,
    UserSchema, UserStatsSchema, TokensSchema, AuthResponseData
)
from app.core.security import (
    get_password_hash, verify_password,
    create_access_token, create_refresh_token, verify_refresh_token
)
from app.core.exceptions import (
    EmailAlreadyExistsException, InvalidCredentialsException,
    UserNotFoundException, InvalidTokenException
)
from app.config import settings


class AuthService:
    """
    인증 서비스 클래스
    
    회원가입, 로그인, 토큰 관리 등 인증 관련 기능을 제공합니다.
    """
    
    def __init__(self, db: Session):
        """인증 서비스 초기화"""
        self.db = db
    
    # ============================================
    # 사용자 조회 메서드
    # ============================================
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """이메일로 사용자 조회"""
        return self.db.query(User).filter(
            User.email == email,
            User.deleted_at.is_(None)
        ).first()
    
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """ID로 사용자 조회"""
        return self.db.query(User).filter(
            User.id == user_id,
            User.deleted_at.is_(None)
        ).first()
    
    # ============================================
    # 회원가입
    # ============================================
    
    def signup(self, request: SignupRequest) -> AuthResponseData:
        """
        일반 회원가입
        
        새로운 사용자를 생성하고 토큰을 발급합니다.
        """
        # 1. 이메일 중복 확인
        existing_user = self.get_user_by_email(request.email)
        if existing_user:
            raise EmailAlreadyExistsException()
        
        # 2. 비밀번호 해싱
        hashed_password = get_password_hash(request.password)
        
        # 3. 사용자 생성
        user = User(
            email=request.email,
            password_hash=hashed_password,
            name=request.name
        )
        self.db.add(user)
        self.db.flush()
        
        # 4. 사용자 통계 초기화
        user_stats = UserStats(user_id=user.id)
        self.db.add(user_stats)
        
        # 5. 사용자 설정 초기화
        user_settings = UserSettings(user_id=user.id)
        self.db.add(user_settings)
        
        # 6. 커밋
        self.db.commit()
        self.db.refresh(user)
        
        # 7. 토큰 생성 및 저장
        tokens = self._create_tokens(user)
        
        # 8. 응답 데이터 생성
        return self._create_auth_response(user, tokens)
    
    # ============================================
    # 이메일 로그인
    # ============================================
    
    def login(self, request: LoginRequest) -> AuthResponseData:
        """
        이메일 로그인
        
        이메일과 비밀번호로 로그인합니다.
        """
        # 1. 사용자 조회
        user = self.get_user_by_email(request.email)
        if not user:
            raise InvalidCredentialsException()
        
        # 2. 비밀번호 확인
        if not user.password_hash:
            raise InvalidCredentialsException()
        
        if not verify_password(request.password, user.password_hash):
            raise InvalidCredentialsException()
        
        # 3. 토큰 생성
        tokens = self._create_tokens(user)
        
        # 4. 응답 데이터 생성
        return self._create_auth_response(user, tokens)
    
    # ============================================
    # 토큰 관련 메서드
    # ============================================
    
    def _create_tokens(self, user: User) -> TokensSchema:
        """JWT 토큰 생성 (내부 메서드)"""
        token_data = {"sub": user.id}
        
        # 액세스 토큰 생성
        access_token = create_access_token(token_data)
        
        # 리프레시 토큰 생성
        refresh_token_str = create_refresh_token(token_data)
        
        # 리프레시 토큰 DB에 저장
        expires_at = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        refresh_token = RefreshToken(
            user_id=user.id,
            token=refresh_token_str,
            expires_at=expires_at
        )
        self.db.add(refresh_token)
        self.db.commit()
        
        return TokensSchema(
            access_token=access_token,
            refresh_token=refresh_token_str,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
        )
    
    def refresh_access_token(self, refresh_token_str: str) -> Tuple[str, int]:
        """액세스 토큰 갱신"""
        # 1. JWT 토큰 검증
        user_id = verify_refresh_token(refresh_token_str)
        if not user_id:
            raise InvalidTokenException()
        
        # 2. DB에서 토큰 조회
        db_token = self.db.query(RefreshToken).filter(
            RefreshToken.token == refresh_token_str,
            RefreshToken.revoked_at.is_(None)
        ).first()
        
        if not db_token or not db_token.is_valid:
            raise InvalidTokenException()
        
        # 3. 사용자 확인
        user = self.get_user_by_id(user_id)
        if not user:
            raise UserNotFoundException()
        
        # 4. 새 액세스 토큰 생성
        new_access_token = create_access_token({"sub": user.id})
        expires_in = settings.ACCESS_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
        
        return new_access_token, expires_in
    
    def logout(self, user_id: str, refresh_token_str: Optional[str] = None):
        """로그아웃 - 리프레시 토큰 무효화"""
        if refresh_token_str:
            db_token = self.db.query(RefreshToken).filter(
                RefreshToken.token == refresh_token_str,
                RefreshToken.user_id == user_id
            ).first()
            
            if db_token:
                db_token.revoked_at = datetime.utcnow()
        else:
            self.db.query(RefreshToken).filter(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None)
            ).update({"revoked_at": datetime.utcnow()})
        
        self.db.commit()
    
    # ============================================
    # 헬퍼 메서드
    # ============================================
    
    def _create_auth_response(self, user: User, tokens: TokensSchema) -> AuthResponseData:
        """인증 응답 데이터 생성 (내부 메서드)"""
        # 북마크한 경로 수 계산
        from app.models.route import SavedRoute
        saved_routes_count = self.db.query(SavedRoute).filter(
            SavedRoute.user_id == user.id
        ).count()
        
        # 통계 정보 생성
        stats = UserStatsSchema(
            total_distance=float(user.stats.total_distance) if user.stats else 0,
            total_workouts=user.stats.total_workouts if user.stats else 0,
            saved_routes_count=saved_routes_count
        )
        
        # 사용자 정보 생성
        user_schema = UserSchema(
            id=user.id,
            email=user.email,
            name=user.name,
            avatar_url=user.avatar_url,
            stats=stats,
            created_at=user.created_at
        )
        
        return AuthResponseData(
            user=user_schema,
            tokens=tokens
        )
