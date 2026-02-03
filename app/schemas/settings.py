# ============================================
# app/schemas/settings.py - 설정 관련 스키마
# ============================================
# 사용자 설정 관련 요청/응답 스키마를 정의합니다.
# ============================================

from typing import Optional
from pydantic import BaseModel, Field


class UserSettingsSchema(BaseModel):
    """사용자 설정 응답 스키마"""
    
    # 안전 설정
    night_safety_mode: bool = Field(..., description="야간 안전 모드")
    auto_night_mode: bool = Field(..., description="자동 야간 모드 (18시-06시)")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "night_safety_mode": True,
                "auto_night_mode": True
            }
        }


class UpdateUserSettingsRequest(BaseModel):
    """사용자 설정 업데이트 요청 스키마"""
    
    # 안전 설정
    night_safety_mode: Optional[bool] = Field(None, description="야간 안전 모드")
    auto_night_mode: Optional[bool] = Field(None, description="자동 야간 모드")
    
    class Config:
        json_schema_extra = {
            "example": {
                "night_safety_mode": True,
                "auto_night_mode": False
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
