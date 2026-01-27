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
    SignupRequest, LoginRequest, KakaoLoginRequest,
    UserSchema, UserStatsSchema, TokensSchema, AuthResponseData
)
from app.core.security import (
    get_password_hash, verify_password,
    create_access_token, create_refresh_token, verify_refresh_token
)
from app.core.exceptions import (
    EmailAlreadyExistsException, InvalidCredentialsException,
    UserNotFoundException, InvalidTokenException, SocialAuthFailedException
)
from app.services.kakao_service import kakao_service
from app.config import settings


class AuthService:
    """
    인증 서비스 클래스
    
    회원가입, 로그인, 토큰 관리 등 인증 관련 기능을 제공합니다.
    
    [신입 개발자를 위한 팁]
    - 서비스 클래스는 비즈니스 로직을 담당합니다.
    - 데이터베이스 세션(db)을 파라미터로 받아 사용합니다.
    - 예외는 core/exceptions.py에 정의된 것을 사용합니다.
    """
    
    def __init__(self, db: Session):
        """
        인증 서비스 초기화
        
        Args:
            db: SQLAlchemy 데이터베이스 세션
        """
        self.db = db
    
    # ============================================
    # 사용자 조회 메서드
    # ============================================
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """
        이메일로 사용자 조회
        
        Args:
            email: 조회할 이메일
            
        Returns:
            User 객체 또는 None (없으면)
        """
        return self.db.query(User).filter(
            User.email == email,
            User.deleted_at.is_(None)  # 탈퇴하지 않은 사용자만
        ).first()
    
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """
        ID로 사용자 조회
        
        Args:
            user_id: 조회할 사용자 ID
            
        Returns:
            User 객체 또는 None
        """
        return self.db.query(User).filter(
            User.id == user_id,
            User.deleted_at.is_(None)
        ).first()
    
    def get_user_by_provider_id(self, provider: str, provider_id: str) -> Optional[User]:
        """
        소셜 로그인 제공자 ID로 사용자 조회
        
        Args:
            provider: 소셜 로그인 제공자 (kakao 등)
            provider_id: 제공자의 사용자 ID
            
        Returns:
            User 객체 또는 None
        """
        return self.db.query(User).filter(
            User.provider == provider,
            User.provider_id == provider_id,
            User.deleted_at.is_(None)
        ).first()
    
    # ============================================
    # 회원가입
    # ============================================
    
    def signup(self, request: SignupRequest) -> AuthResponseData:
        """
        일반 회원가입
        
        새로운 사용자를 생성하고 토큰을 발급합니다.
        
        Args:
            request: 회원가입 요청 데이터
            
        Returns:
            AuthResponseData: 사용자 정보와 토큰
            
        Raises:
            EmailAlreadyExistsException: 이메일이 이미 존재하는 경우
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
        self.db.flush()  # ID를 얻기 위해 flush (commit은 아직 안함)
        
        # 4. 사용자 통계 초기화
        user_stats = UserStats(user_id=user.id)
        self.db.add(user_stats)
        
        # 5. 사용자 설정 초기화
        user_settings = UserSettings(user_id=user.id)
        self.db.add(user_settings)
        
        # 6. 커밋 (모든 변경사항 저장)
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
        
        Args:
            request: 로그인 요청 데이터
            
        Returns:
            AuthResponseData: 사용자 정보와 토큰
            
        Raises:
            InvalidCredentialsException: 이메일 또는 비밀번호가 틀린 경우
        """
        # 1. 사용자 조회
        user = self.get_user_by_email(request.email)
        if not user:
            raise InvalidCredentialsException()
        
        # 2. 비밀번호 확인 (소셜 로그인 사용자는 비밀번호가 없음)
        if not user.password_hash:
            raise InvalidCredentialsException()
        
        if not verify_password(request.password, user.password_hash):
            raise InvalidCredentialsException()
        
        # 3. 토큰 생성
        tokens = self._create_tokens(user)
        
        # 4. 응답 데이터 생성
        return self._create_auth_response(user, tokens)
    
    # ============================================
    # 카카오 소셜 로그인
    # ============================================
    
    async def kakao_login(self, request: KakaoLoginRequest) -> Tuple[AuthResponseData, bool]:
        """
        카카오 소셜 로그인
        
        카카오 액세스 토큰을 검증하고 로그인/회원가입을 처리합니다.
        
        Args:
            request: 카카오 로그인 요청 데이터
            
        Returns:
            Tuple[AuthResponseData, bool]: (응답 데이터, 신규 가입 여부)
            
        Raises:
            SocialAuthFailedException: 카카오 인증 실패 시
        """
        # 1. 카카오 토큰 검증 및 프로필 조회
        profile_data = {
            "id": request.profile.id,
            "email": request.profile.email,
            "nickname": request.profile.nickname,
            "profile_image": request.profile.profile_image
        }
        
        kakao_profile = await kakao_service.validate_and_get_profile(
            access_token=request.access_token,
            provided_profile=profile_data
        )
        
        # 2. 기존 사용자 확인 (카카오 ID로)
        user = self.get_user_by_provider_id("kakao", kakao_profile["kakao_id"])
        is_new_user = False
        
        if not user:
            # 2-1. 이메일로 기존 사용자 확인
            if kakao_profile.get("email"):
                user = self.get_user_by_email(kakao_profile["email"])
            
            if user:
                # 기존 사용자에 카카오 연동
                user.provider = "kakao"
                user.provider_id = kakao_profile["kakao_id"]
                if kakao_profile.get("profile_image") and not user.avatar:
                    user.avatar = kakao_profile["profile_image"]
                self.db.commit()
            else:
                # 신규 사용자 생성
                user = self._create_kakao_user(kakao_profile)
                is_new_user = True
        else:
            # 기존 카카오 사용자 - 프로필 업데이트
            if kakao_profile.get("profile_image"):
                user.avatar = kakao_profile["profile_image"]
            user.updated_at = datetime.utcnow()
            self.db.commit()
        
        # 3. 토큰 생성
        tokens = self._create_tokens(user)
        
        # 4. 응답 데이터 생성
        auth_response = self._create_auth_response(user, tokens)
        
        return auth_response, is_new_user
    
    def _create_kakao_user(self, kakao_profile: dict) -> User:
        """
        카카오 사용자 생성 (내부 메서드)
        
        Args:
            kakao_profile: 카카오 프로필 정보
            
        Returns:
            User: 생성된 사용자 객체
        """
        # 이메일이 없는 경우 임시 이메일 생성
        email = kakao_profile.get("email")
        if not email:
            email = f"kakao_{kakao_profile['kakao_id']}@runnerway.app"
        
        user = User(
            email=email,
            name=kakao_profile["nickname"],
            avatar=kakao_profile.get("profile_image"),
            provider="kakao",
            provider_id=kakao_profile["kakao_id"]
        )
        self.db.add(user)
        self.db.flush()
        
        # 통계 초기화
        user_stats = UserStats(user_id=user.id)
        self.db.add(user_stats)
        
        # 설정 초기화
        user_settings = UserSettings(user_id=user.id)
        self.db.add(user_settings)
        
        self.db.commit()
        self.db.refresh(user)
        
        return user
    
    # ============================================
    # 토큰 관련 메서드
    # ============================================
    
    def _create_tokens(self, user: User) -> TokensSchema:
        """
        JWT 토큰 생성 (내부 메서드)
        
        액세스 토큰과 리프레시 토큰을 생성하고 DB에 저장합니다.
        
        Args:
            user: 사용자 객체
            
        Returns:
            TokensSchema: 생성된 토큰 정보
        """
        # 토큰 페이로드 (토큰에 담을 데이터)
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
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60  # 초 단위
        )
    
    def refresh_access_token(self, refresh_token_str: str) -> Tuple[str, int]:
        """
        액세스 토큰 갱신
        
        리프레시 토큰을 검증하고 새로운 액세스 토큰을 발급합니다.
        
        Args:
            refresh_token_str: 리프레시 토큰 문자열
            
        Returns:
            Tuple[str, int]: (새 액세스 토큰, 만료 시간(초))
            
        Raises:
            InvalidTokenException: 토큰이 유효하지 않은 경우
        """
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
        expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        
        return new_access_token, expires_in
    
    def logout(self, user_id: str, refresh_token_str: Optional[str] = None):
        """
        로그아웃
        
        리프레시 토큰을 무효화합니다.
        
        Args:
            user_id: 사용자 ID
            refresh_token_str: 리프레시 토큰 (선택)
        """
        if refresh_token_str:
            # 특정 토큰만 무효화
            db_token = self.db.query(RefreshToken).filter(
                RefreshToken.token == refresh_token_str,
                RefreshToken.user_id == user_id
            ).first()
            
            if db_token:
                db_token.revoked_at = datetime.utcnow()
        else:
            # 해당 사용자의 모든 토큰 무효화
            self.db.query(RefreshToken).filter(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None)
            ).update({"revoked_at": datetime.utcnow()})
        
        self.db.commit()
    
    # ============================================
    # 헬퍼 메서드
    # ============================================
    
    def _create_auth_response(self, user: User, tokens: TokensSchema) -> AuthResponseData:
        """
        인증 응답 데이터 생성 (내부 메서드)
        
        Args:
            user: 사용자 객체
            tokens: 토큰 정보
            
        Returns:
            AuthResponseData: 응답 데이터
        """
        # 통계 정보 생성
        stats = UserStatsSchema(
            total_distance=float(user.stats.total_distance) if user.stats else 0,
            total_workouts=user.stats.total_workouts if user.stats else 0,
            completed_routes=user.stats.completed_routes if user.stats else 0
        )
        
        # 사용자 정보 생성
        user_schema = UserSchema(
            id=user.id,
            email=user.email,
            name=user.name,
            avatar=user.avatar,
            provider=user.provider,
            stats=stats,
            created_at=user.created_at
        )
        
        return AuthResponseData(
            user=user_schema,
            tokens=tokens
        )
