# ============================================
# app/schemas/settings.py - 설정 관련 스키마
# ============================================
# 사용자 설정 관련 요청/응답 스키마를 정의합니다.
# ============================================

from typing import Optional
from pydantic import BaseModel, Field


class UserSettingsSchema(BaseModel):
    """사용자 설정 응답 스키마"""
    
    # 앱 설정
    dark_mode: bool = Field(..., description="다크 모드")
    language: str = Field(..., description="언어 설정 (ko/en)")
    
    # 알림 설정
    push_enabled: bool = Field(..., description="푸시 알림 활성화")
    workout_reminder: bool = Field(..., description="운동 시작 알림")
    goal_achievement: bool = Field(..., description="목표 달성 알림")
    community_activity: bool = Field(..., description="커뮤니티 활동 알림")
    
    # 운동 설정
    auto_lap: bool = Field(..., description="자동 랩 (1km마다)")
    
    # 안전 설정
    night_safety_mode: bool = Field(..., description="야간 안전 모드")
    auto_night_mode: bool = Field(..., description="자동 야간 모드 (18시-06시)")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "dark_mode": True,
                "language": "ko",
                "push_enabled": True,
                "workout_reminder": True,
                "goal_achievement": True,
                "community_activity": False,
                "auto_lap": False,
                "night_safety_mode": True,
                "auto_night_mode": True
            }
        }


class UpdateUserSettingsRequest(BaseModel):
    """사용자 설정 업데이트 요청 스키마"""
    
    # 앱 설정
    dark_mode: Optional[bool] = Field(None, description="다크 모드")
    language: Optional[str] = Field(None, description="언어 설정 (ko/en)")
    
    # 알림 설정
    push_enabled: Optional[bool] = Field(None, description="푸시 알림 활성화")
    workout_reminder: Optional[bool] = Field(None, description="운동 시작 알림")
    goal_achievement: Optional[bool] = Field(None, description="목표 달성 알림")
    community_activity: Optional[bool] = Field(None, description="커뮤니티 활동 알림")
    
    # 운동 설정
    auto_lap: Optional[bool] = Field(None, description="자동 랩")
    
    # 안전 설정
    night_safety_mode: Optional[bool] = Field(None, description="야간 안전 모드")
    auto_night_mode: Optional[bool] = Field(None, description="자동 야간 모드")
    
    class Config:
        json_schema_extra = {
            "example": {
                "dark_mode": False,
                "push_enabled": True,
                "workout_reminder": False
            }
        }


class UserSettingsResponseWrapper(BaseModel):
    """사용자 설정 응답 래퍼"""
    success: bool = True
    data: UserSettingsSchema
    message: str = "설정 조회 성공"


class UserSettingsUpdateResponseWrapper(BaseModel):
    """사용자 설정 업데이트 응답 래퍼"""
    success: bool = True
    data: UserSettingsSchema
    message: str = "설정이 업데이트되었습니다"
