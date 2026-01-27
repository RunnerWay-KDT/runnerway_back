# ============================================
# app/schemas/user.py - 사용자 관련 스키마
# ============================================
# 사용자 프로필, 설정, 통계 관련 요청/응답 스키마를 정의합니다.
# ============================================

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr


# ============================================
# 공통 스키마
# ============================================

class BadgeSchema(BaseModel):
    """배지 스키마"""
    id: str
    name: str
    description: Optional[str] = None
    icon: str
    unlocked_at: Optional[datetime] = None
    category: Optional[str] = None
    
    class Config:
        from_attributes = True


class UserStatsDetailSchema(BaseModel):
    """사용자 통계 상세 스키마"""
    total_distance: float = 0  # km
    total_workouts: int = 0
    completed_routes: int = 0
    total_calories: int = 0  # kcal
    total_duration: int = 0  # 초
    average_pace: Optional[str] = None
    longest_run: Optional[float] = None  # km
    
    class Config:
        from_attributes = True


class UserPreferencesSchema(BaseModel):
    """사용자 선호 설정 스키마"""
    voice_guide: bool = True
    dark_mode: bool = True
    unit: str = "km"


# ============================================
# 요청 스키마
# ============================================

class UserProfileUpdateRequest(BaseModel):
    """
    프로필 수정 요청 스키마
    
    [신입 개발자를 위한 팁]
    - 모든 필드가 Optional: 변경하고 싶은 필드만 전송
    - None인 필드는 변경하지 않음 (부분 업데이트)
    """
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="이름")
    avatar: Optional[str] = Field(None, description="프로필 이미지 URL 또는 Base64")
    preferences: Optional[UserPreferencesSchema] = Field(None, description="사용자 설정")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "새로운이름",
                "preferences": {
                    "voice_guide": True,
                    "unit": "km"
                }
            }
        }


class UserDeleteRequest(BaseModel):
    """회원 탈퇴 요청 스키마"""
    password: Optional[str] = Field(None, description="비밀번호 (일반 로그인 사용자)")
    reason: Optional[str] = Field(None, max_length=500, description="탈퇴 사유")


# ============================================
# 응답 스키마
# ============================================

class UserProfileResponse(BaseModel):
    """
    사용자 프로필 응답 스키마
    
    GET /api/v1/users/me 응답에 사용됩니다.
    """
    id: str
    email: str
    name: str
    avatar: Optional[str] = None
    provider: Optional[str] = None
    stats: UserStatsDetailSchema
    badges: List[BadgeSchema] = []
    preferences: Optional[UserPreferencesSchema] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class UserProfileResponseWrapper(BaseModel):
    """사용자 프로필 응답 래퍼"""
    success: bool = True
    data: UserProfileResponse
    message: Optional[str] = None


class UserUpdateResponse(BaseModel):
    """프로필 수정 응답 스키마"""
    id: str
    name: str
    avatar: Optional[str] = None
    preferences: Optional[UserPreferencesSchema] = None
    updated_at: datetime


class UserUpdateResponseWrapper(BaseModel):
    """프로필 수정 응답 래퍼"""
    success: bool = True
    data: UserUpdateResponse
    message: str = "프로필이 업데이트되었습니다"


class UserDeleteResponse(BaseModel):
    """회원 탈퇴 응답 스키마"""
    success: bool = True
    message: str = "회원 탈퇴가 완료되었습니다"
    data: Optional[dict] = None


# ============================================
# 설정 관련 스키마
# ============================================

class UserSettingsSchema(BaseModel):
    """
    사용자 설정 스키마
    
    앱 설정, 알림 설정, 안전 설정을 포함합니다.
    """
    # 앱 설정
    dark_mode: bool = True
    language: str = "ko"
    
    # 알림 설정
    push_enabled: bool = True
    workout_reminder: bool = True
    goal_achievement: bool = True
    community_activity: bool = False
    
    # 운동 설정
    sound_effect: bool = True
    vibration: bool = True
    voice_guide: bool = True
    auto_lap: bool = False
    
    # 안전 설정
    night_safety_mode: bool = True
    auto_night_mode: bool = True
    share_location: bool = False
    sos_button: bool = True
    
    class Config:
        from_attributes = True


class EmergencyContactSchema(BaseModel):
    """긴급 연락처 스키마"""
    id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=50)
    phone: str = Field(..., min_length=10, max_length=20)
    
    class Config:
        from_attributes = True


class SafetySettingsSchema(BaseModel):
    """
    안전 설정 스키마
    
    야간 안전 모드, 긴급 연락처 등을 포함합니다.
    """
    night_safety_mode: bool = True
    auto_night_mode: bool = True
    share_location: bool = False
    sos_button: bool = True
    emergency_contacts: List[EmergencyContactSchema] = []


class SafetySettingsUpdateRequest(BaseModel):
    """안전 설정 수정 요청 스키마"""
    night_safety_mode: Optional[bool] = None
    auto_night_mode: Optional[bool] = None
    share_location: Optional[bool] = None
    sos_button: Optional[bool] = None
    emergency_contacts: Optional[List[EmergencyContactSchema]] = None


class SafetySettingsResponse(BaseModel):
    """안전 설정 응답 스키마"""
    success: bool = True
    data: SafetySettingsSchema
    message: Optional[str] = None
