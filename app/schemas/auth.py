# ============================================
# app/schemas/auth.py - 인증 관련 스키마
# ============================================
# 로그인, 회원가입, 토큰 관련 요청/응답 스키마를 정의합니다.
# ============================================

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, validator


# ============================================
# 요청 스키마 (Request Schemas)
# ============================================

class SignupRequest(BaseModel):
    """
    회원가입 요청 스키마
    
    [필드 설명]
    - email: 이메일 (로그인 ID로 사용)
    - password: 비밀번호 (6자 이상)
    - name: 사용자 이름 (2자 이상)
    """
    email: EmailStr = Field(..., description="이메일 주소")
    password: str = Field(..., min_length=6, description="비밀번호 (6자 이상)")
    name: str = Field(..., min_length=2, max_length=100, description="사용자 이름 (최소 2자)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "password123",
                "name": "홍길동"
            }
        }


class LoginRequest(BaseModel):
    """
    이메일 로그인 요청 스키마
    """
    email: EmailStr = Field(..., description="이메일 주소")
    password: str = Field(..., description="비밀번호")
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "password123"
            }
        }


class RefreshTokenRequest(BaseModel):
    """
    토큰 갱신 요청 스키마
    """
    refresh_token: str = Field(..., description="리프레시 토큰")


class LogoutRequest(BaseModel):
    """
    로그아웃 요청 스키마
    """
    refresh_token: Optional[str] = Field(None, description="리프레시 토큰 (선택)")
    device_id: Optional[str] = Field(None, description="디바이스 ID (선택)")


# ============================================
# 응답 스키마 (Response Schemas)
# ============================================

class UserStatsSchema(BaseModel):
    """
    사용자 통계 스키마
    """
    total_distance: float = Field(0, description="총 운동 거리 (km)")
    total_workouts: int = Field(0, description="총 운동 횟수")
    saved_routes_count: int = Field(0, description="북마크한 경로 수")
    
    class Config:
        from_attributes = True


class UserSchema(BaseModel):
    """
    사용자 정보 스키마
    
    API 응답에서 사용자 정보를 반환할 때 사용합니다.
    """
    id: str = Field(..., description="사용자 ID")
    email: str = Field(..., description="이메일")
    name: str = Field(..., description="이름")
    avatar_url: Optional[str] = Field(None, description="프로필 이미지 URL")
    stats: Optional[UserStatsSchema] = Field(None, description="사용자 통계")
    created_at: Optional[datetime] = Field(None, description="가입일")
    
    class Config:
        from_attributes = True


class TokensSchema(BaseModel):
    """
    JWT 토큰 스키마
    """
    access_token: str = Field(..., description="액세스 토큰")
    refresh_token: str = Field(..., description="리프레시 토큰")
    token_type: str = Field("bearer", description="토큰 타입")
    expires_in: int = Field(..., description="만료 시간 (초)")


class AuthResponseData(BaseModel):
    """
    인증 응답 데이터 스키마
    
    로그인/회원가입 성공 시 반환되는 데이터입니다.
    """
    user: UserSchema
    tokens: TokensSchema
    is_new_user: Optional[bool] = Field(None, description="신규 가입 여부")


class AuthResponse(BaseModel):
    """
    인증 응답 스키마
    """
    success: bool = True
    data: AuthResponseData
    message: str


class TokenRefreshResponseData(BaseModel):
    """
    토큰 갱신 응답 데이터 스키마
    """
    access_token: str
    expires_in: int


class TokenRefreshResponse(BaseModel):
    """
    토큰 갱신 응답 스키마
    """
    success: bool = True
    data: TokenRefreshResponseData
    message: str = "토큰이 갱신되었습니다"


class LogoutResponse(BaseModel):
    """
    로그아웃 응답 스키마
    """
    success: bool = True
    message: str = "로그아웃되었습니다"
    data: Optional[dict] = None
