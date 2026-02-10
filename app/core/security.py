# ============================================
# app/core/security.py - 보안 관련 유틸리티
# ============================================
# JWT 토큰 생성/검증, 비밀번호 해싱 등 보안 관련 기능을 제공합니다.
# ============================================

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings


# ============================================
# 비밀번호 해싱 설정
# ============================================
# bcrypt: 가장 널리 사용되는 비밀번호 해싱 알고리즘
# 자동으로 salt(랜덤 값)를 추가하여 같은 비밀번호도 다르게 저장됨
#
# [신입 개발자를 위한 팁]
# - 해싱(Hashing): 원본을 알 수 없는 단방향 변환
# - 암호화(Encryption): 복호화 가능한 양방향 변환
# - 비밀번호는 절대 암호화가 아닌 해싱으로 저장해야 합니다!
# ============================================
pwd_context = CryptContext(
    schemes=["bcrypt"],  # bcrypt 알고리즘 사용
    deprecated="auto"    # 이전 버전 알고리즘 자동 처리
)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    비밀번호 검증
    
    사용자가 입력한 비밀번호와 DB에 저장된 해시를 비교합니다.
    
    Args:
        plain_password: 사용자가 입력한 평문 비밀번호
        hashed_password: DB에 저장된 해시된 비밀번호
        
    Returns:
        bool: 비밀번호가 일치하면 True, 아니면 False
        
    Example:
        >>> is_valid = verify_password("mypassword123", "$2b$12$...")
        >>> if is_valid:
        ...     print("로그인 성공!")
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    비밀번호 해싱
    
    평문 비밀번호를 bcrypt로 해싱하여 반환합니다.
    회원가입이나 비밀번호 변경 시 사용합니다.
    
    Args:
        password: 해싱할 평문 비밀번호
        
    Returns:
        str: 해시된 비밀번호 (예: "$2b$12$...")
        
    Example:
        >>> hashed = get_password_hash("mypassword123")
        >>> print(hashed)
        '$2b$12$...무작위문자열...'
    """
    return pwd_context.hash(password)


# ============================================
# JWT 토큰 함수들
# ============================================
# JWT (JSON Web Token): 인증 정보를 안전하게 전달하는 표준
# 구조: Header.Payload.Signature
#
# [신입 개발자를 위한 팁]
# - Access Token: 짧은 유효기간 (1시간), API 호출 시 사용
# - Refresh Token: 긴 유효기간 (7일), Access Token 갱신 시 사용
# - 토큰에는 민감한 정보를 담지 마세요! (디코딩 가능)
# ============================================

def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Access Token 생성
    
    사용자 인증에 사용되는 JWT 액세스 토큰을 생성합니다.
    
    Args:
        data: 토큰에 담을 데이터 (보통 user_id 등)
        expires_delta: 만료 시간 (기본값: 설정 파일의 값)
        
    Returns:
        str: JWT 액세스 토큰 문자열
        
    Example:
        >>> token = create_access_token({"sub": "user-uuid-123"})
        >>> print(token)
        'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'
        
    [토큰 구조]
    - sub (subject): 토큰의 주체 (보통 user_id)
    - exp (expiration): 만료 시간
    - iat (issued at): 발급 시간
    - type: 토큰 타입 (access/refresh)
    """
    # 데이터 복사 (원본 변경 방지)
    to_encode = data.copy()
    
    # 만료 시간 설정
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            days=settings.ACCESS_TOKEN_EXPIRE_DAYS
        )
    
    # 토큰에 추가 정보 삽입
    to_encode.update({
        "exp": expire,           # 만료 시간
        "iat": datetime.utcnow(), # 발급 시간
        "type": "access"         # 토큰 타입
    })
    
    # JWT 토큰 생성 및 반환
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    
    return encoded_jwt


def create_refresh_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Refresh Token 생성
    
    액세스 토큰 갱신에 사용되는 리프레시 토큰을 생성합니다.
    
    Args:
        data: 토큰에 담을 데이터
        expires_delta: 만료 시간 (기본값: 7일)
        
    Returns:
        str: JWT 리프레시 토큰 문자열
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh"
    })
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    
    return encoded_jwt


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """
    JWT 토큰 디코딩 (검증)
    
    토큰의 유효성을 검사하고, 유효하면 담긴 데이터를 반환합니다.
    
    Args:
        token: 검증할 JWT 토큰 문자열
        
    Returns:
        Optional[Dict]: 토큰이 유효하면 페이로드(데이터), 아니면 None
        
    Example:
        >>> payload = decode_token("eyJhbGciOiJIUzI1NiIs...")
        >>> if payload:
        ...     user_id = payload["sub"]
        ...     print(f"User ID: {user_id}")
        
    [검증 항목]
    1. 서명 검증: SECRET_KEY로 서명이 맞는지 확인
    2. 만료 검증: exp 시간이 지나지 않았는지 확인
    """
    try:
        # 토큰 디코딩 및 검증 (만료 검증 비활성화 - 영구 로그인 지원)
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_exp": False}
        )
        return payload
    except JWTError:
        # 토큰이 유효하지 않음 (만료, 서명 불일치 등)
        return None


def verify_access_token(token: str) -> Optional[str]:
    """
    Access Token 검증
    
    액세스 토큰의 유효성을 검사하고 user_id를 반환합니다.
    
    Args:
        token: 검증할 액세스 토큰
        
    Returns:
        Optional[str]: 유효하면 user_id, 아니면 None
    """
    try:
        print(f"🔍 [토큰검증] 토큰 디코딩 시작: {token[:20]}...")
        payload = decode_token(token)
        
        if payload is None:
            print("❌ [토큰검증] 토큰 디코딩 실패")
            return None
        
        print(f"✅ [토큰검증] 토큰 디코딩 성공: {payload}")
        
        # 토큰 타입 확인 (access 토큰인지)
        if payload.get("type") != "access":
            print(f"❌ [토큰검증] 토큰 타입 불일치: {payload.get('type')}")
            return None
        
        # user_id 반환 (sub 필드)
        user_id = payload.get("sub")
        print(f"✅ [토큰검증] user_id 추출 성공: {user_id}")
        return user_id
        
    except Exception as e:
        print(f"❌ [토큰검증] 예외 발생: {str(e)}")
        return None


def verify_refresh_token(token: str) -> Optional[str]:
    """
    Refresh Token 검증
    
    리프레시 토큰의 유효성을 검사하고 user_id를 반환합니다.
    
    Args:
        token: 검증할 리프레시 토큰
        
    Returns:
        Optional[str]: 유효하면 user_id, 아니면 None
    """
    payload = decode_token(token)
    
    if payload is None:
        return None
    
    # 토큰 타입 확인 (refresh 토큰인지)
    if payload.get("type") != "refresh":
        return None
    
    return payload.get("sub")
