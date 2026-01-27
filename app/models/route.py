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
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    
    # shape_id: 도형 식별자 (heart, star, coffee, smile, dog, cat)
    shape_id = Column(String(50), unique=True, nullable=False)
    
    name = Column(String(50), nullable=False)           # 도형 이름 (하트, 별 등)
    icon_name = Column(String(50), nullable=False)      # 아이콘 이름
    category = Column(String(20), nullable=False)       # 카테고리 (shape, animal)
    
    estimated_distance = Column(DECIMAL(5, 2), nullable=True)  # 예상 거리 (km)
    svg_template = Column(Text, nullable=True)          # SVG 템플릿 경로 데이터
    
    is_active = Column(Boolean, default=True)           # 활성화 여부
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # 이 도형을 사용한 경로들
    routes = relationship("Route", back_populates="shape")


class Route(Base):
    """
    경로 테이블 (routes)
    
    사용자가 생성한 경로 정보를 저장합니다.
    프리셋 도형 또는 커스텀 그리기로 생성된 경로 모두 이 테이블에 저장됩니다.
    
    [신입 개발자를 위한 팁]
    - type: 'preset' (미리 정의된 도형) 또는 'custom' (사용자 직접 그리기)
    - mode: 'running' (러닝) 또는 'walking' (산책)
    """
    __tablename__ = "routes"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    
    # 도형 정보 (프리셋인 경우에만)
    shape_id = Column(String(36), ForeignKey("route_shapes.id"), nullable=True)
    
    name = Column(String(100), nullable=False)          # 경로 이름
    type = Column(String(20), nullable=False)           # preset / custom
    mode = Column(String(20), nullable=False)           # running / walking
    
    # ========== 위치 정보 ==========
    start_latitude = Column(DECIMAL(10, 7), nullable=False)   # 시작점 위도
    start_longitude = Column(DECIMAL(10, 7), nullable=False)  # 시작점 경도
    location_address = Column(String(255), nullable=True)     # 주소
    location_district = Column(String(50), nullable=True)     # 지역명 (여의도, 강남 등)
    
    # ========== 커스텀 경로 데이터 (type='custom'인 경우) ==========
    custom_svg_path = Column(Text, nullable=True)       # SVG Path 데이터
    custom_points = Column(JSON, nullable=True)         # 좌표 배열 [{x, y}]
    
    # ========== 운동 설정 ==========
    # 러닝 설정
    condition = Column(String(20), nullable=True)       # recovery/fat-burn/challenge
    
    # 산책 설정
    intensity = Column(String(20), nullable=True)       # light/moderate/brisk
    target_duration = Column(Integer, nullable=True)    # 목표 시간 (분)
    
    # 안전 모드
    safety_mode = Column(Boolean, default=False)
    
    # 상태
    status = Column(String(20), nullable=False, default="active")  # active/deleted
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # ========== 관계 정의 ==========
    shape = relationship("RouteShape", back_populates="routes")
    options = relationship("RouteOption", back_populates="route", lazy="select")
    waypoints = relationship("RouteWaypoint", back_populates="route", lazy="select")
    saved_by = relationship("SavedRoute", back_populates="route", lazy="select")


class RouteOption(Base):
    """
    경로 옵션 테이블 (route_options)
    
    하나의 경로에 대해 3가지 옵션(짧은/중간/긴 코스)을 저장합니다.
    각 옵션은 거리, 예상 시간, 난이도, 안전도 등이 다릅니다.
    """
    __tablename__ = "route_options"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    route_id = Column(String(36), ForeignKey("routes.id"), nullable=False)
    
    option_number = Column(Integer, nullable=False)     # 옵션 번호 (1, 2, 3)
    name = Column(String(100), nullable=False)          # 옵션 이름 (하트 경로 A 등)
    
    distance = Column(DECIMAL(5, 2), nullable=False)    # 거리 (km)
    estimated_time = Column(Integer, nullable=False)    # 예상 소요 시간 (분)
    difficulty = Column(String(20), nullable=False)     # 쉬움/보통/도전
    tag = Column(String(20), nullable=True)             # 추천/BEST/null
    
    # 경로 좌표 배열 [{lat, lng}]
    coordinates = Column(JSON, nullable=False)
    
    # ========== 점수/특성 ==========
    safety_score = Column(Integer, default=0)           # 안전도 (0-100)
    elevation = Column(Integer, default=0)              # 고도차 (m)
    lighting_score = Column(Integer, default=0)         # 조명 점수 (0-100)
    sidewalk_score = Column(Integer, default=0)         # 인도 비율 (0-100)
    convenience_count = Column(Integer, default=0)      # 주변 편의시설 수
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # 복합 유니크 제약조건 (같은 경로에 같은 번호의 옵션 중복 불가)
    __table_args__ = (
        UniqueConstraint('route_id', 'option_number', name='unique_route_option'),
    )
    
    # 관계 정의
    route = relationship("Route", back_populates="options")
    nearby_places = relationship("NearbyPlace", back_populates="route_option", lazy="select")


class RouteWaypoint(Base):
    """
    경로 경유지 테이블 (route_waypoints)
    
    산책 모드에서 선택한 경유지(카페, 공원 등)를 저장합니다.
    """
    __tablename__ = "route_waypoints"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    route_id = Column(String(36), ForeignKey("routes.id"), nullable=False)
    place_id = Column(String(36), ForeignKey("places.id"), nullable=False)
    
    order_index = Column(Integer, nullable=False)       # 경유 순서
    estimated_time = Column(String(20), nullable=True)  # 예상 소요 시간 (6분)
    
    # 관계 정의
    route = relationship("Route", back_populates="waypoints")
    place = relationship("Place", back_populates="route_waypoints")


class SavedRoute(Base):
    """
    저장된 경로 테이블 (saved_routes)
    
    사용자가 북마크한 경로를 저장합니다.
    커뮤니티에서 마음에 드는 경로를 저장할 수 있습니다.
    """
    __tablename__ = "saved_routes"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    route_id = Column(String(36), ForeignKey("routes.id"), nullable=False)
    
    saved_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
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
    
    [신입 개발자를 위한 팁]
    - 프론트엔드에서 POST /routes/generate 호출 → task_id 반환
    - 프론트엔드에서 2초마다 GET /routes/generate/{task_id} 호출 → 진행률 확인
    - status가 'completed'가 되면 route_id로 경로 조회
    """
    __tablename__ = "route_generation_tasks"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    
    # 작업 상태
    status = Column(String(20), nullable=False, default="processing")  # processing/completed/failed
    progress = Column(Integer, default=0)               # 진행률 (0-100)
    current_step = Column(String(100), nullable=True)   # 현재 단계 설명
    estimated_remaining = Column(Integer, nullable=True) # 예상 남은 시간 (초)
    
    # 요청 데이터 (전체 저장)
    request_data = Column(JSON, nullable=False)
    
    # 결과 (완료 시)
    route_id = Column(String(36), ForeignKey("routes.id"), nullable=True)
    error_message = Column(String(500), nullable=True)  # 에러 메시지 (실패 시)
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class Place(Base):
    """
    장소 테이블 (places)
    
    카페, 편의점, 공원 등 경유지로 추천할 수 있는 장소를 저장합니다.
    """
    __tablename__ = "places"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    
    name = Column(String(100), nullable=False)          # 장소 이름
    category = Column(String(30), nullable=False)       # cafe/convenience/park/photo/restroom/fountain/cctv
    
    latitude = Column(DECIMAL(10, 7), nullable=False)   # 위도
    longitude = Column(DECIMAL(10, 7), nullable=False)  # 경도
    address = Column(String(255), nullable=True)        # 주소
    
    rating = Column(DECIMAL(2, 1), nullable=True)       # 평점 (0.0-5.0)
    review_count = Column(Integer, default=0)           # 리뷰 수
    
    icon = Column(String(50), nullable=True)            # 아이콘 이름 (coffee, store, trees 등)
    color = Column(String(10), nullable=True)           # 색상 코드 (#f59e0b)
    
    is_active = Column(Boolean, default=True)           # 활성화 여부
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 관계 정의
    route_waypoints = relationship("RouteWaypoint", back_populates="place")
    nearby_route_options = relationship("NearbyPlace", back_populates="place")


class NearbyPlace(Base):
    """
    주변 장소 테이블 (nearby_places)
    
    각 경로 옵션 주변의 편의시설 정보를 저장합니다.
    """
    __tablename__ = "nearby_places"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    route_option_id = Column(String(36), ForeignKey("route_options.id"), nullable=False)
    place_id = Column(String(36), ForeignKey("places.id"), nullable=False)
    
    distance = Column(String(20), nullable=True)        # 경로로부터 거리 (0.2km)
    estimated_time = Column(String(20), nullable=True)  # 도보 소요 시간 (3분)
    
    # 관계 정의
    route_option = relationship("RouteOption", back_populates="nearby_places")
    place = relationship("Place", back_populates="nearby_route_options")


class RecommendedRoute(Base):
    """
    추천 경로 테이블 (recommended_routes)
    
    홈 화면에 표시할 추천 경로를 관리합니다.
    위치, 시간대, 인기도 등에 따라 추천 경로를 선정합니다.
    """
    __tablename__ = "recommended_routes"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    route_id = Column(String(36), ForeignKey("routes.id"), nullable=False)
    
    # 추천 대상 지역
    target_latitude = Column(DECIMAL(10, 7), nullable=True)   # 타겟 위도
    target_longitude = Column(DECIMAL(10, 7), nullable=True)  # 타겟 경도
    radius_km = Column(DECIMAL(5, 2), nullable=True)          # 추천 반경 (km)
    
    rating = Column(DECIMAL(2, 1), nullable=True)       # 평점
    runner_count = Column(Integer, default=0)           # 이용자 수
    reason = Column(String(255), nullable=True)         # 추천 이유
    priority = Column(Integer, default=0)               # 추천 우선순위
    
    is_active = Column(Boolean, default=True)           # 활성화 여부
    start_date = Column(Date, nullable=True)            # 추천 시작일
    end_date = Column(Date, nullable=True)              # 추천 종료일
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
