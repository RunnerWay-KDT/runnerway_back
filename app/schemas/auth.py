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
    - name: 사용자 이름 (1자 이상)
    
    [신입 개발자를 위한 팁]
    - EmailStr: Pydantic이 자동으로 이메일 형식 검증
    - Field(): 필드의 제약조건을 설정
    - min_length: 최소 길이 제한
    """
    email: EmailStr = Field(..., description="이메일 주소")
    password: str = Field(..., min_length=6, description="비밀번호 (6자 이상)")
    name: str = Field(..., min_length=1, max_length=100, description="사용자 이름")
    
    class Config:
        # API 문서에 표시될 예시 데이터
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


class KakaoProfile(BaseModel):
    """
    카카오 프로필 정보 스키마
    
    카카오 SDK에서 받은 사용자 프로필 정보입니다.
    """
    id: str = Field(..., description="카카오 사용자 ID")
    email: Optional[str] = Field(None, description="이메일 (동의한 경우)")
    nickname: str = Field(..., description="닉네임")
    profile_image: Optional[str] = Field(None, description="프로필 이미지 URL")


class KakaoLoginRequest(BaseModel):
    """
    카카오 소셜 로그인 요청 스키마
    
    [신입 개발자를 위한 팁]
    - 프론트엔드에서 카카오 SDK로 로그인 후
    - access_token과 profile 정보를 백엔드로 전송
    - 백엔드에서 토큰 검증 후 회원가입/로그인 처리
    """
    provider: str = Field("kakao", description="소셜 로그인 제공자")
    access_token: str = Field(..., description="카카오 SDK에서 받은 액세스 토큰")
    profile: KakaoProfile = Field(..., description="카카오 프로필 정보")
    
    class Config:
        json_schema_extra = {
            "example": {
                "provider": "kakao",
                "access_token": "카카오_액세스_토큰",
                "profile": {
                    "id": "1234567890",
                    "email": "user@kakao.com",
                    "nickname": "카카오사용자",
                    "profile_image": "https://k.kakaocdn.net/..."
                }
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
    completed_routes: int = Field(0, description="완료한 경로 수")
    
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
    avatar: Optional[str] = Field(None, description="프로필 이미지 URL")
    provider: Optional[str] = Field(None, description="소셜 로그인 제공자")
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
    is_new_user: Optional[bool] = Field(None, description="신규 가입 여부 (소셜 로그인)")


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
