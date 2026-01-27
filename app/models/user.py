# ============================================
# app/models/user.py - 사용자 관련 데이터베이스 모델
# ============================================
# 이 파일은 사용자와 관련된 모든 테이블을 정의합니다.
# DB_TABLE_DEFINITION.csv 파일을 기반으로 작성되었습니다.
# ============================================

import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    Column, String, Boolean, Integer, Text, DateTime,
    ForeignKey, DECIMAL, UniqueConstraint
)
from sqlalchemy.orm import relationship

from app.db.database import Base


def generate_uuid() -> str:
    """UUID를 생성하는 헬퍼 함수"""
    return str(uuid.uuid4())


class User(Base):
    """
    사용자 테이블 (users)
    
    앱의 모든 사용자 정보를 저장합니다.
    카카오 소셜 로그인과 일반 로그인 모두 이 테이블을 사용합니다.
    
    [신입 개발자를 위한 팁]
    - __tablename__: 실제 데이터베이스 테이블 이름
    - Column: 테이블의 컬럼(필드)을 정의
    - relationship: 다른 테이블과의 관계를 정의 (JOIN용)
    """
    __tablename__ = "users"
    
    # ========== 기본 필드 ==========
    # id: 사용자 고유 식별자 (UUID 형식)
    # default=generate_uuid: 새 레코드 생성 시 자동으로 UUID 생성
    id = Column(String(36), primary_key=True, default=generate_uuid)
    
    # email: 로그인에 사용되는 이메일
    # unique=True: 중복 이메일 불가
    # index=True: 검색 성능 향상을 위한 인덱스
    email = Column(String(255), unique=True, nullable=False, index=True)
    
    # password_hash: 해시된 비밀번호
    # nullable=True: 소셜 로그인 사용자는 비밀번호가 없음
    password_hash = Column(String(255), nullable=True)
    
    # name: 사용자 이름 (최소 2자)
    name = Column(String(100), nullable=False)
    
    # avatar: 프로필 이미지 URL
    avatar = Column(String(500), nullable=True)
    
    # ========== 소셜 로그인 관련 필드 ==========
    # provider: 소셜 로그인 제공자 (kakao, google 등)
    # None이면 일반 이메일 로그인 사용자
    provider = Column(String(20), nullable=True)
    
    # provider_id: 소셜 로그인 제공자의 사용자 ID
    provider_id = Column(String(255), nullable=True)
    
    # ========== 시간 관련 필드 ==========
    # created_at: 가입일시
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # updated_at: 마지막 수정일시
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # deleted_at: 탈퇴일시 (Soft Delete 방식)
    # Soft Delete: 실제로 삭제하지 않고 deleted_at에 날짜를 기록
    deleted_at = Column(DateTime, nullable=True)
    
    # ========== 관계 정의 (ORM에서 JOIN을 쉽게 하기 위함) ==========
    # back_populates: 양방향 관계 설정
    # lazy="joined": 부모 조회 시 자동으로 함께 로드
    # uselist=False: 1:1 관계 (리스트가 아닌 단일 객체)
    
    # 사용자 통계 (1:1 관계)
    stats = relationship("UserStats", back_populates="user", uselist=False, lazy="joined")
    
    # 사용자 설정 (1:1 관계)
    settings = relationship("UserSettings", back_populates="user", uselist=False, lazy="joined")
    
    # 긴급 연락처 (1:N 관계, 최대 3개)
    emergency_contacts = relationship("EmergencyContact", back_populates="user", lazy="select")
    
    # 획득한 배지 (N:M 관계)
    badges = relationship("UserBadge", back_populates="user", lazy="select")
    
    # 리프레시 토큰 (1:N 관계)
    refresh_tokens = relationship("RefreshToken", back_populates="user", lazy="select")
    
    def __repr__(self):
        """객체의 문자열 표현 (디버깅용)"""
        return f"<User(id={self.id}, email={self.email}, name={self.name})>"


class UserStats(Base):
    """
    사용자 통계 테이블 (user_stats)
    
    사용자의 운동 통계를 저장합니다.
    사용자당 하나의 통계 레코드만 존재합니다 (1:1 관계).
    """
    __tablename__ = "user_stats"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    
    # user_id: 사용자 ID (외래 키)
    # ForeignKey: 다른 테이블의 컬럼을 참조
    user_id = Column(String(36), ForeignKey("users.id"), unique=True, nullable=False)
    
    # 통계 필드들 (기본값 0)
    total_distance = Column(DECIMAL(10, 2), default=0)  # 총 운동 거리 (km)
    total_workouts = Column(Integer, default=0)          # 총 운동 횟수
    completed_routes = Column(Integer, default=0)        # 완료한 경로 수
    total_calories = Column(Integer, default=0)          # 총 소모 칼로리 (kcal)
    total_duration = Column(Integer, default=0)          # 총 운동 시간 (초)
    
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 사용자와의 관계
    user = relationship("User", back_populates="stats")
    
    def __repr__(self):
        return f"<UserStats(user_id={self.user_id}, total_distance={self.total_distance})>"


class UserSettings(Base):
    """
    사용자 설정 테이블 (user_settings)
    
    앱 설정, 알림 설정, 안전 설정 등을 저장합니다.
    """
    __tablename__ = "user_settings"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), unique=True, nullable=False)
    
    # ========== 앱 설정 ==========
    dark_mode = Column(Boolean, default=True)           # 다크 모드
    language = Column(String(10), default="ko")         # 언어 설정
    
    # ========== 알림 설정 ==========
    push_enabled = Column(Boolean, default=True)        # 푸시 알림 활성화
    workout_reminder = Column(Boolean, default=True)    # 운동 시작 알림
    goal_achievement = Column(Boolean, default=True)    # 목표 달성 알림
    community_activity = Column(Boolean, default=False) # 커뮤니티 활동 알림
    
    # ========== 운동 설정 ==========
    sound_effect = Column(Boolean, default=True)        # 사운드 효과
    vibration = Column(Boolean, default=True)           # 진동
    voice_guide = Column(Boolean, default=True)         # 음성 안내
    auto_lap = Column(Boolean, default=False)           # 자동 랩
    
    # ========== 안전 설정 ==========
    night_safety_mode = Column(Boolean, default=True)   # 야간 안전 모드
    auto_night_mode = Column(Boolean, default=True)     # 자동 야간 모드
    share_location = Column(Boolean, default=False)     # 위치 공유
    sos_button = Column(Boolean, default=True)          # SOS 버튼
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 사용자와의 관계
    user = relationship("User", back_populates="settings")


class EmergencyContact(Base):
    """
    긴급 연락처 테이블 (emergency_contacts)
    
    사용자의 비상 연락처를 저장합니다.
    한 사용자당 최대 3개까지 저장 가능합니다.
    """
    __tablename__ = "emergency_contacts"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    
    name = Column(String(50), nullable=False)           # 연락처 이름
    phone = Column(String(20), nullable=False)          # 전화번호 (10-15자리)
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # 사용자와의 관계
    user = relationship("User", back_populates="emergency_contacts")


class Badge(Base):
    """
    배지 테이블 (badges)
    
    시스템에서 제공하는 배지 목록입니다.
    배지 획득 조건과 정보를 저장합니다.
    """
    __tablename__ = "badges"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    
    name = Column(String(100), nullable=False)          # 배지 이름
    description = Column(String(255), nullable=True)    # 배지 설명
    icon = Column(String(50), nullable=False)           # 아이콘 이름 (trophy, medal 등)
    
    # 달성 조건
    condition_type = Column(String(50), nullable=False) # 조건 타입 (distance, workouts, streak 등)
    condition_value = Column(Integer, nullable=False)   # 조건 값 (예: 100km, 10회 등)
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # 배지를 획득한 사용자들
    users = relationship("UserBadge", back_populates="badge")


class UserBadge(Base):
    """
    사용자-배지 연결 테이블 (user_badges)
    
    어떤 사용자가 어떤 배지를 언제 획득했는지 저장합니다.
    N:M 관계를 구현하기 위한 중간 테이블입니다.
    """
    __tablename__ = "user_badges"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    badge_id = Column(String(36), ForeignKey("badges.id"), nullable=False)
    
    unlocked_at = Column(DateTime, nullable=False, default=datetime.utcnow)  # 획득 일시
    
    # 복합 유니크 제약조건 (같은 배지를 중복 획득 불가)
    __table_args__ = (
        UniqueConstraint('user_id', 'badge_id', name='unique_user_badge'),
    )
    
    # 관계 정의
    user = relationship("User", back_populates="badges")
    badge = relationship("Badge", back_populates="users")


class RefreshToken(Base):
    """
    리프레시 토큰 테이블 (refresh_tokens)
    
    JWT 인증에서 액세스 토큰 갱신에 사용되는 리프레시 토큰을 저장합니다.
    토큰의 유효성 검사 및 폐기를 위해 DB에 저장합니다.
    
    [신입 개발자를 위한 팁]
    - 액세스 토큰: 짧은 유효기간 (1시간), API 호출에 사용
    - 리프레시 토큰: 긴 유효기간 (7일), 액세스 토큰 갱신에 사용
    - revoked_at이 설정되면 해당 토큰은 더 이상 사용할 수 없음
    """
    __tablename__ = "refresh_tokens"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    
    token = Column(String(500), unique=True, nullable=False)  # 리프레시 토큰 값
    expires_at = Column(DateTime, nullable=False)             # 만료 시간
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    revoked_at = Column(DateTime, nullable=True)              # 폐기 시간 (로그아웃 시)
    
    # 사용자와의 관계
    user = relationship("User", back_populates="refresh_tokens")
    
    @property
    def is_valid(self) -> bool:
        """토큰이 유효한지 확인 (만료되지 않고 폐기되지 않음)"""
        now = datetime.utcnow()
        return self.expires_at > now and self.revoked_at is None
