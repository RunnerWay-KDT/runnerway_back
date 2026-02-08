# ============================================
# app/models/route.py - 경로 관련 데이터베이스 모델
# ============================================
# 이 파일은 경로 생성, 저장, 추천과 관련된 모든 테이블을 정의합니다.
# ============================================

import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, Integer, Text, DateTime,
    ForeignKey, DECIMAL, JSON, Date, UniqueConstraint
)
from sqlalchemy.orm import relationship

from app.db.database import Base


def generate_uuid() -> str:
    """UUID를 생성하는 헬퍼 함수"""
    return str(uuid.uuid4())


class RouteShape(Base):
    """
    경로 도형 프리셋 테이블 (route_shapes)
    
    미리 정의된 도형 템플릿을 저장합니다.
    예: 하트, 별, 커피, 스마일, 강아지, 고양이 등
    """
    __tablename__ = "route_shapes"
    __table_args__ = {'comment': '템플릿 저장경로'}
    
    id = Column(String(36), primary_key=True, default=generate_uuid, comment='UUID')
    name = Column(String(50), nullable=False, comment='도형 이름 (하트, 별 등)')
    icon_name = Column(String(50), nullable=False, comment='아이콘 이름')
    category = Column(String(20), nullable=False, comment='카테고리 (shape, animal)')
    estimated_distance = Column(DECIMAL(5, 2), nullable=True, comment='예상 거리 (km)')
    svg_path = Column(Text, nullable=True, comment='SVG url')
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # 이 도형을 사용한 경로들
    routes = relationship("Route", back_populates="shape")


class Route(Base):
    """
    경로 테이블 (routes)
    
    사용자가 생성한 경로 정보를 저장합니다.
    프리셋 도형 또는 커스텀 그리기로 생성된 경로 모두 이 테이블에 저장됩니다.
    
    [신입 개발자를 위한 팁]
    - type: 'preset' (미리 정의된 도형), 'custom' (사용자 직접 그리기), 'none' (도형 그리기 아님)
    - mode: 'running' (러닝), 'walking' (산책), 'none' (도형 그리기)
    """
    __tablename__ = "routes"
    
    id = Column(String(36), primary_key=True, default=generate_uuid, comment='UUID')
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, comment='생성자 ID')
    shape_id = Column(String(36), ForeignKey("route_shapes.id"), nullable=True, comment='프리셋 도형 ID (null=커스텀)')
    
    name = Column(String(100), nullable=False, comment='경로 이름')
    type = Column(String(20), nullable=True, comment='preset / custom / none(null아님!)은 도형그리기 아님')
    mode = Column(String(20), nullable=True, comment='running / walking / none(null아님!)은 도형그리기임')
    
    # ========== 위치 정보 ==========
    start_latitude = Column(DECIMAL(10, 7), nullable=False, comment='시작점 위도')
    start_longitude = Column(DECIMAL(10, 7), nullable=False, comment='시작점 경도')
    
    # ========== 커스텀 경로 데이터 ==========
    svg_path = Column(Text, nullable=True, comment='SVG Path 데이터 (커스텀인 경우)')
    
    # ========== 운동 설정 ==========
    # 러닝 설정
    condition = Column(String(20), nullable=True, comment='recovery/fat-burn/challenge (러닝)')
    
    # 산책 설정
    intensity = Column(String(20), nullable=True, comment='light/moderate/brisk (산책)')
    target_duration = Column(Integer, nullable=True, comment='목표 시간 (분, 산책)')
    
    # 안전 모드
    safety_mode = Column(Boolean, default=False, comment='안전 우선 모드')
    
    # 상태
    status = Column(String(20), nullable=False, default="active", comment='active/deleted')
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # ========== 관계 정의 ==========
    shape = relationship("RouteShape", back_populates="routes")
    options = relationship("RouteOption", back_populates="route", lazy="select")
    saved_by = relationship("SavedRoute", back_populates="route", lazy="select")


class RouteOption(Base):
    """
    경로 옵션 테이블 (route_options)
    
    하나의 경로에 대해 3가지 옵션(짧은/중간/긴 코스)을 저장합니다.
    각 옵션은 거리, 예상 시간, 난이도, 안전도 등이 다릅니다.
    """
    __tablename__ = "route_options"
    
    id = Column(String(36), primary_key=True, default=generate_uuid, comment='UUID')
    route_id = Column(String(36), ForeignKey("routes.id"), nullable=False, comment='경로 ID')
    
    option_number = Column(Integer, nullable=False, comment='옵션 번호 (1, 2, 3)')
    name = Column(String(100), nullable=False, comment='옵션 이름 (하트 경로 A 등)')
    
    distance = Column(DECIMAL(5, 2), nullable=False, comment='거리 (km)')
    estimated_time = Column(Integer, nullable=False, comment='예상 소요 시간 (분)')
    difficulty = Column(String(20), nullable=False, comment='쉬움/보통/도전')
    tag = Column(String(20), nullable=True, comment='추천/BEST/null')
    
    # 경로 좌표 배열 [{lat, lng}]
    coordinates = Column(JSON, nullable=False, comment='[{lat, lng}] 배열')
    
    # ========== 점수/특성 ==========
    safety_score = Column(Integer, default=0, comment='안전도 (0-100)')
    max_elevation_diff = Column(Integer, default=0, comment='고도차 (m)')
    lighting_score = Column(Integer, default=0, comment='조명 점수 (0-100)')
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # 관계 정의
    route = relationship("Route", back_populates="options")


class SavedRoute(Base):
    """
    저장된 경로 테이블 (saved_routes)
    
    사용자가 북마크한 경로를 저장합니다.
    """
    __tablename__ = "saved_routes"
    
    id = Column(String(36), primary_key=True, default=generate_uuid, comment='UUID')
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, comment='저장한 사용자 ID')
    route_id = Column(String(36), ForeignKey("routes.id"), nullable=False, comment='경로 ID')
    
    saved_at = Column(DateTime, nullable=False, default=datetime.utcnow, comment='저장 일시')
    
    # 복합 유니크 제약조건 (같은 경로 중복 저장 불가)
    __table_args__ = (
        UniqueConstraint('user_id', 'route_id', name='unique_saved_route'),
    )
    
    # 관계 정의
    route = relationship("Route", back_populates="saved_by")


class RouteGenerationTask(Base):
    """
    경로 생성 작업 테이블 (route_generation_tasks)
    
    AI 경로 생성은 시간이 걸리므로 비동기로 처리합니다.
    이 테이블은 생성 작업의 상태와 진행률을 추적합니다.
    """
    __tablename__ = "route_generation_tasks"
    
    id = Column(String(36), primary_key=True, default=generate_uuid, comment='UUID, task_id로 사용')
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, comment='요청한 사용자 ID')
    
    # 작업 상태
    status = Column(String(20), nullable=False, default="processing", comment='processing/completed/failed')
    progress = Column(Integer, default=0, comment='진행률 (0-100)')
    current_step = Column(String(100), nullable=True, comment='현재 단계 설명')
    estimated_remaining = Column(Integer, nullable=True, comment='예상 남은 시간 (초)')
    
    # 요청 데이터 (전체 저장)
    request_data = Column(JSON, nullable=False, comment='경로 생성 요청 전체 데이터')
    
    # 결과 (완료 시)
    route_id = Column(String(36), ForeignKey("routes.id"), nullable=True, comment='생성된 경로 ID (완료 시)')
    error_message = Column(String(500), nullable=True, comment='에러 메시지 (실패 시)')
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True, comment='완료/실패 시간')


class Place(Base):
    """
    장소 테이블 (places)
    
    카페, 편의점, 공원 등 경유지로 추천할 수 있는 장소를 저장합니다.
    """
    __tablename__ = "places"
    
    id = Column(String(36), primary_key=True, default=generate_uuid, comment='UUID')
    
    name = Column(String(100), nullable=False, comment='장소 이름')
    category = Column(String(30), nullable=False, comment='cafe/convenience/park/photo/restroom/fountain/cctv')
    
    latitude = Column(DECIMAL(10, 7), nullable=False, comment='위도')
    longitude = Column(DECIMAL(10, 7), nullable=False, comment='경도')
    address = Column(String(255), nullable=True, comment='주소')
    
    rating = Column(DECIMAL(2, 1), nullable=True, comment='평점 (0.0-5.0)')
    review_count = Column(Integer, default=0, comment='리뷰 수')
    
    icon = Column(String(50), nullable=True, comment='아이콘 이름 (coffee, store, trees 등)')
    color = Column(String(10), nullable=True, comment='색상 코드 (#f59e0b)')
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class RecommendedRoute(Base):
    """
    추천 경로 테이블 (recommended_routes)
    
    홈 화면에 표시할 추천 경로를 관리합니다.
    """
    __tablename__ = "recommended_routes"
    
    id = Column(String(36), primary_key=True, default=generate_uuid, comment='UUID')
    route_id = Column(String(36), ForeignKey("routes.id"), nullable=False, comment='경로 ID')
    
    # 추천 대상 지역
    target_latitude = Column(DECIMAL(10, 7), nullable=True, comment='타겟 위도')
    target_longitude = Column(DECIMAL(10, 7), nullable=True, comment='타겟 경도')
    radius_km = Column(DECIMAL(5, 2), nullable=True, comment='추천 반경 (km)')
    
    rating = Column(DECIMAL(2, 1), nullable=True, comment='평점')
    runner_count = Column(Integer, default=0, comment='이용자 수')
    reason = Column(String(255), nullable=True, comment='추천 이유')
    priority = Column(Integer, default=0, comment='추천 우선순위')
    
    is_active = Column(Boolean, default=True)
    start_date = Column(Date, nullable=True, comment='추천 시작일')
    end_date = Column(Date, nullable=True, comment='추천 종료일')
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
