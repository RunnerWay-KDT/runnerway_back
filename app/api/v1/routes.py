# ============================================
# app/api/v1/routes.py - 경로 API 라우터
# ============================================
# 경로 생성, 옵션 조회, 저장/삭제 등 경로 관련 API를 제공합니다.
# AI 기반 경로 생성 및 안전도 평가 기능을 포함합니다.
# ============================================
<<<<<<< HEAD

from typing import Optional
from fastapi import APIRouter, Depends, Query, Path, status, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session, joinedload
=======
from operator import ge
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, Path, status, BackgroundTasks, Body
from sqlalchemy.orm import Session
>>>>>>> main
from datetime import datetime
from pydantic import BaseModel, Field
import uuid
import logging

from app.db.database import get_db, SessionLocal
from app.api.deps import get_current_user
from app.models.user import User
from app.models.route import Route, RouteOption, SavedRoute, RouteGenerationTask, RouteShape, generate_uuid
from app.schemas.route import (
    RouteGenerateRequest, RouteGenerateResponse, RouteGenerateResponseWrapper,
    RouteOptionsResponse, RouteOptionsResponseWrapper,
    RouteDetailResponse, RouteDetailResponseWrapper,
    RouteSaveRequest, RouteSaveResponse,
<<<<<<< HEAD
    RouteSaveRequest, RouteSaveResponse,
    RouteOptionSchema, RoutePointSchema,
    RouteRecommendRequest, RouteRecommendResponse,
    ElevationPrefetchRequest
)
from app.schemas.common import CommonResponse
from app.core.exceptions import NotFoundException, ValidationException, ExternalAPIException
import osmnx as ox
import networkx as nx
import logging
import random
import math
import time
import os

# 로깅 설정
logger = logging.getLogger(__name__)

# OSMnx 설정
ox.settings.use_cache = True
ox.settings.log_console = False

=======
    RouteOptionSchema, RoutePointSchema, RouteScoresSchema, ShapeInfoSchema,
    SaveCustomDrawingRequest, SaveCustomDrawingResponse, SaveCustomDrawingResponseWrapper
)
from app.schemas.common import CommonResponse
from app.core.exceptions import NotFoundException, ValidationException
from app.gps_art.generate_routes import generate_routes
from app.models.route import Route, RouteOption, RouteShape
from app.services.gps_art_service import generate_gps_art_impl
>>>>>>> main

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/routes", tags=["Routes"])


# ============================================
# 경로 생성 요청 (비동기)
# ============================================
@router.post(
    "/generate",
    response_model=RouteGenerateResponseWrapper,
    status_code=status.HTTP_202_ACCEPTED,
    summary="경로 생성 요청",
    description="""
    경로 생성을 요청합니다.
    
    **비동기 처리:** 
    - 요청 즉시 task_id를 반환
    - 클라이언트는 task_id로 상태 폴링
    
    **필수 파라미터:**
    - start_location: 시작 위치 좌표 (경도, 위도)
    - distance: 목표 거리 (km)
    - shape_id: 모양 템플릿 ID
    
    **선택 파라미터:**
    - waypoints: 경유지 (최대 3개)
    - avoid_steep: 급경사 회피 여부
    - prefer_shaded: 그늘길 선호 여부
    """
)
def request_route_generation(
    request: RouteGenerateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """경로 생성 요청 엔드포인트"""
    
    # RouteShape 유효성 검증
    shape = db.query(RouteShape).filter(RouteShape.id == request.shape_id).first()
    if not shape:
        raise ValidationException(
            message="존재하지 않는 모양입니다",
            field="shape_id"
        )
    
    # Task ID 생성
    task_id = generate_uuid()
    
    # 경로 생성 Task 저장
    route_task = RouteGenerationTask(
        id=task_id,
        user_id=current_user.id,
        shape_id=request.shape_id,
        start_lat=request.start_location.lat,
        start_lng=request.start_location.lng,
        target_distance=request.distance,
        waypoints=request.waypoints.model_dump() if request.waypoints else None,
        options={
            "avoid_steep": request.avoid_steep,
            "prefer_shaded": request.prefer_shaded
        },
        status="pending"
    )
    db.add(route_task)
    db.commit()
    
    # 백그라운드에서 경로 생성 실행
    # 백그라운드에서 경로 생성 실행
    # 2024-02-06 Fix: 동기 래퍼 함수를 사용하여 비동기 함수 실행 및 DB 세션 안전하게 관리
    from app.services.background_tasks import run_generate_route_background
    
    background_tasks.add_task(
        run_generate_route_background,
        task_id=task_id,
        user_id=current_user.id,
        request_data={
            'lat': request.start_location.lat,
            'lng': request.start_location.lng,
            'target_time_min': None, # 거리 기반이므로 시간은 None
            'target_distance_km': request.distance,
            'prompt': request.avoid_steep and "안전" or "" # 예시
        }
    )
    
    return RouteGenerateResponseWrapper(
        success=True,
        data=RouteGenerateResponse(
            task_id=task_id,
            status="pending",
            estimated_time=5
        ),
        message="경로 생성이 요청되었습니다"
    )


async def generate_route_background(task_id: str, db: Session):
    """
    백그라운드에서 경로 생성을 수행합니다.
    
    TODO: 실제 구현 시 다음 로직 추가 필요:
    1. 카카오 맵 API 또는 네이버 지도 API 호출
    2. AI 기반 경로 최적화
    3. 안전도 점수 계산
    4. 3개 옵션 생성
    """
    try:
        # Task 상태 업데이트: processing
        task = db.query(RouteGenerationTask).filter(
            RouteGenerationTask.id == task_id
        ).first()
        
        if not task:
            return
        
        task.status = "processing"
        task.started_at = datetime.utcnow()
        db.commit()
        
        # TODO: 실제 경로 생성 로직 구현
        # 현재는 모의 데이터로 처리
        
        # Route 생성
        route = Route(
            user_id=task.user_id,
            shape_id=task.shape_id,
            location_lat=task.start_lat,
            location_lng=task.start_lng,
            target_distance=task.target_distance,
            status="completed"
        )
        db.add(route)
        db.commit()
        
        # RouteOption 3개 생성 (모의 데이터)
        for i, option_type in enumerate(["balanced", "safety", "scenic"]):
            option = RouteOption(
                route_id=route.id,
                option_type=option_type,
                distance=task.target_distance + (i * 0.1),  # 약간씩 다른 거리
                estimated_time=int(task.target_distance * 10),  # 분 단위
                safety_score=90 - (i * 5),  # 안전도 점수
                elevation_gain=50 + (i * 10),  # 고도 상승
                path_data={
                    "coordinates": [],  # TODO: 실제 좌표 데이터
                    "waypoints": []
                }
            )
            db.add(option)
        
        # Task 완료 상태 업데이트
        task.status = "completed"
        task.route_id = route.id
        task.completed_at = datetime.utcnow()
        db.commit()
        
    except Exception as e:
        # 에러 발생 시 Task 상태 업데이트
        task = db.query(RouteGenerationTask).filter(
            RouteGenerationTask.id == task_id
        ).first()
        if task:
            task.status = "failed"
            task.error_message = str(e)
            db.commit()


# ============================================
# 경로 생성 상태 조회
# ============================================
@router.get(
    "/generate/{task_id}",
    summary="경로 생성 상태 조회",
    description="""
    경로 생성 요청의 현재 상태를 조회합니다.
    
    **상태 값:**
    - pending: 대기 중
    - processing: 생성 중
    - completed: 완료
    - failed: 실패
    """
)
def get_route_generation_status(
    task_id: str = Path(..., description="Task ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """경로 생성 상태 조회 엔드포인트"""
    
    task = db.query(RouteGenerationTask).filter(
        RouteGenerationTask.id == task_id,
        RouteGenerationTask.user_id == current_user.id
    ).first()
    
    if not task:
        raise NotFoundException(
            resource="RouteGenerationTask",
            resource_id=task_id
        )
    
    # 응답 데이터
    response_data = {
        "task_id": task.id,
        "status": task.status,
        "route_id": task.route_id,
        "progress": getattr(task, "progress", 0) or 0,
        "current_step": getattr(task, "current_step", None),
        "estimated_remaining": getattr(task, "estimated_remaining", None), 
    }

     # 완료된 경우 경로 정보 포함
    if task.status == "completed" and task.route_id:
        response_data["route_id"] = task.route_id
        opts = db.query(RouteOption).filter(RouteOption.route_id == task.route_id).all()
        response_data["option_ids"] = [str(o.id) for o in opts]

    # 실패한 경우 에러 메시지 포함
    if task.status == "failed":
        response_data["error"] = task.error_message
    
    return {
        "success": True,
        "data": response_data
    }


# ============================================
# 경로 옵션 조회
# ============================================
@router.get(
    "/{route_id}/options",
    response_model=RouteOptionsResponseWrapper,
    summary="경로 옵션 조회",
    description="""
    생성된 경로의 옵션들을 조회합니다.
    
    **반환 옵션:**
    - balanced: 균형 잡힌 경로
    - safety: 안전 최우선 경로
    - scenic: 경치 좋은 경로
    """
)
def get_route_options(
    route_id: str = Path(..., description="경로 ID (UUID)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """경로 옵션 조회 엔드포인트"""
    
<<<<<<< HEAD
    # 경로 조회 (옵션과 함께 로드 -> N+1 문제 해결)
    route = db.query(Route).options(joinedload(Route.options)).filter(
=======
    # 경로 조회 (Route.id는 UUID 문자열)
    route = db.query(Route).filter(
>>>>>>> main
        Route.id == route_id,
        Route.user_id == current_user.id
    ).first()
    
    if not route:
        raise NotFoundException(
            resource="Route",
            resource_id=route_id
        )
    
    # 옵션 목록 (이미 로드됨)
    options = route.options
    
    option_list = []
    for opt in options:
        coords = opt.coordinates if isinstance(opt.coordinates, list) else []
        coord_schema = [{"lat": float(c.get("lat", 0)), "lng": float(c.get("lng", 0))} for c in coords]
        option_list.append(RouteOptionSchema(
            id=str(opt.id),
            option_number=opt.option_number,
            name=opt.name,
            distance=float(opt.distance),
            estimated_time=opt.estimated_time,
            difficulty=opt.difficulty or "보통",
            tag=opt.tag,
            coordinates=coord_schema,
            scores=RouteScoresSchema(
                safety=getattr(opt, "safety_score", 0) or 0,
                elevation=getattr(opt, "max_elevation_diff", 0) or 0,
                lighting=getattr(opt, "lighting_score", 0) or 0,
                sidewalk=getattr(opt, "sidewalk_score", 0) or 0,
            ),
        ))
    
    shape_info = None
    if route.shape:
        shape_info = ShapeInfoSchema(
            id=route.shape.id,
            name=route.shape.name,
            icon_name=route.shape.icon_name or "",
            category=getattr(route.shape, "category", "") or "",
            is_custom=False,
        )
    
    return RouteOptionsResponseWrapper(
        success=True,
        data=RouteOptionsResponse(
            route_id=str(route.id),
            shape_info=shape_info,
            options=option_list
        )
    )


# ============================================
# 경로 상세 조회
# ============================================
@router.get(
    "/{route_id}/options/{option_id}",
    response_model=RouteDetailResponseWrapper,
    summary="경로 상세 조회",
    description="""
    특정 경로 옵션의 상세 정보를 조회합니다.
    
    **포함 정보:**
    - 전체 경로 좌표
    - 고도 프로필
    - 안전 정보 (CCTV, 가로등 위치)
    - 주변 편의시설
    """
)
def get_route_detail(
    route_id: int = Path(..., description="경로 ID"),
    option_id: int = Path(..., description="옵션 ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """경로 상세 조회 엔드포인트"""
    
    # 옵션 조회
    option = db.query(RouteOption).filter(
        RouteOption.id == option_id,
        RouteOption.route_id == route_id
    ).first()
    
    if not option:
        raise NotFoundException(
            resource="RouteOption",
            resource_id=option_id
        )
    
    route = option.route
    
    # 경로 좌표 변환
    path_points = []
    if option.path_data and option.path_data.get("coordinates"):
        for coord in option.path_data["coordinates"]:
            path_points.append(RoutePointSchema(
                lat=coord.get("lat", 0),
                lng=coord.get("lng", 0),
                elevation=coord.get("elevation")
            ))
    
    return RouteDetailResponseWrapper(
        success=True,
        data=RouteDetailResponse(
            id=option.id,
            route_id=route.id,
            type=option.option_type,
            name=route.name or f"{route.shape.name if route.shape else ''} 경로",
            distance=float(option.distance),
            estimated_time=option.estimated_time,
            safety_score=option.safety_score,
            elevation_gain=option.elevation_gain,
            path=path_points,
            safety_features={
                "cctv_count": 0,  # TODO: 실제 데이터 조회
                "streetlight_coverage": 0,
                "emergency_points": []
            },
            amenities={
                "restrooms": [],  # TODO: 주변 편의시설 조회
                "water_fountains": [],
                "convenience_stores": []
            }
        )
    )


# ============================================
# 경로 저장 (북마크)
# ============================================
@router.post(
    "/{route_id}/save",
    response_model=CommonResponse,
    summary="경로 저장",
    description="경로를 저장(북마크)합니다."
)
def save_route(
    route_id: int = Path(..., description="경로 ID"),
    request: RouteSaveRequest = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """경로 저장 엔드포인트"""
    
    # 경로 존재 확인
    route = db.query(Route).filter(Route.id == route_id).first()
    if not route:
        raise NotFoundException(
            resource="Route",
            resource_id=route_id
        )
    
    # 이미 저장했는지 확인
    existing = db.query(SavedRoute).filter(
        SavedRoute.user_id == current_user.id,
        SavedRoute.route_id == route_id
    ).first()
    
    if existing:
        raise ValidationException(
            message="이미 저장한 경로입니다",
            field="route_id"
        )
    
    # 저장
    saved_route = SavedRoute(
        user_id=current_user.id,
        route_id=route_id,
        custom_name=request.custom_name if request else None,
        note=request.note if request else None
    )
    db.add(saved_route)
    db.commit()
    
    return CommonResponse(
        success=True,
        message="경로가 저장되었습니다",
        data={"saved_route_id": saved_route.id}
    )


# ============================================
# 경로 저장 취소
# ============================================
@router.delete(
    "/{route_id}/save",
    response_model=CommonResponse,
    summary="경로 저장 취소",
    description="저장한 경로를 삭제합니다."
)
def unsave_route(
    route_id: int = Path(..., description="경로 ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """경로 저장 취소 엔드포인트"""
    
    saved_route = db.query(SavedRoute).filter(
        SavedRoute.user_id == current_user.id,
        SavedRoute.route_id == route_id
    ).first()
    
    if not saved_route:
        raise NotFoundException(
            resource="SavedRoute",
            resource_id=route_id
        )
    
    db.delete(saved_route)
    db.commit()
    
    return CommonResponse(
        success=True,
        message="저장이 취소되었습니다"
    )


# ============================================
# 모양 템플릿 목록 조회
# ============================================
@router.get(
    "/shapes",
    summary="모양 템플릿 목록",
    description="""
    사용 가능한 경로 모양 템플릿 목록을 조회합니다.
    
    **기본 제공 모양:**
    - circle: 원형
    - heart: 하트
    - star: 별
    - square: 사각형
    """
)
def get_shape_templates(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """모양 템플릿 목록 조회 엔드포인트"""
    
    shapes = db.query(RouteShape).filter(
        RouteShape.is_active == True
    ).all()
    
    shape_list = []
    for shape in shapes:
        shape_list.append({
            "id": shape.id,
            "shape_id": shape.shape_id,
            "name": shape.name,
            "icon_name": shape.icon_name,
            "description": shape.description,
            "preview_image": shape.preview_image
        })
    
    return {
        "success": True,
        "data": {"shapes": shape_list},
        "message": "모양 템플릿 조회 성공"
    }


# ============================================
# 경유지 추천
# ============================================
@router.post(
    "/waypoints/recommend",
    summary="경유지 추천",
    description="""
    현재 위치 기반으로 경유지를 추천합니다.
    
    **추천 기준:**
    - 안전도 (CCTV, 가로등)
    - 경치
    - 편의시설 접근성
    """
)
def recommend_waypoints(
    lat: float = Query(..., description="현재 위도"),
    lng: float = Query(..., description="현재 경도"),
    radius: float = Query(1.0, description="검색 반경 (km)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """경유지 추천 엔드포인트"""
    
    # TODO: 실제 경유지 추천 로직 구현
    # 현재는 모의 데이터 반환
    
    recommended = [
        {
            "id": 1,
            "name": "근처 공원",
            "lat": lat + 0.005,
            "lng": lng + 0.005,
            "type": "park",
            "safety_score": 85,
            "description": "산책하기 좋은 공원입니다"
        },
        {
            "id": 2,
            "name": "한강 둔치",
            "lat": lat - 0.003,
            "lng": lng + 0.007,
            "type": "riverside",
            "safety_score": 90,
            "description": "경치가 좋은 한강 둔치입니다"
        }
    ]
    
    return {
        "success": True,
        "data": {"waypoints": recommended},
        "message": "경유지 추천 완료"
    }


# ============================================
# 경로 추천 (Server.py 로직 이관)
# ============================================
@router.post(
    "/recommend",
    response_model=RouteRecommendResponse,
    summary="AI 경로 추천",
    description="GPT와 OSMnx를 사용하여 사용자 맞춤형 경로를 추천합니다."
)
async def recommend_route(
    request: RouteRecommendRequest,
    db: Session = Depends(get_db)  # DB 세션 주입
):
    """
    AI 기반 경로 추천 엔드포인트
    (거리/시간 정확도 개선)
    """
    from app.services.road_network import RoadNetworkFetcher
    
    user_location = (request.lat, request.lng)
    
    # 1. 목표 거리 설정 (컨디션 기반 또는 GPT)
    target_dist_km = request.target_distance_km
    
    # 0. 프롬프트 기반 컨디션 설정 (거리는 설정하지 않음!)
    # Frontend sends constructed prompts like "목적: 회복 러닝..."
    condition = "normal"  # 기본값
    if request.prompt:
        p = request.prompt.lower()
        if "recovery" in p or "회복" in p or "easy" in p:
            condition = "recovery"
        elif "fat" in p or "지방" in p or "burn" in p:
            condition = "fat-burn"
        elif "challenge" in p or "기록" in p or "hard" in p:
            condition = "challenge"

    logger.info(f"Processing request: {user_location}, condition: {condition}")
    
    candidates = []

    try:
        # 1. RoadNetworkFetcher 초기화
        fetcher = RoadNetworkFetcher()
        
        # 2. 먼저 페이스 계산하여 target_dist_km 결정
        # 컨디션별 페이스 설정 (분/km)
        if condition == "recovery":
            pace_min_per_km = 10.0
        elif condition == "challenge":
            pace_min_per_km = 7.0
        else:  # normal (지방연소)
            pace_min_per_km = 9.0
        
        # 목표 시간 vs 목표 거리 우선순위
        if request.target_time_min and request.target_time_min > 0:
            target_time_min = request.target_time_min
            target_dist_km = target_time_min / pace_min_per_km
            logger.info(f"[TIME-BASED] 목표 시간 {target_time_min}분 → 거리 {target_dist_km:.2f}km")
        elif target_dist_km and target_dist_km > 0:
            target_time_min = target_dist_km * pace_min_per_km
            logger.info(f"[DISTANCE-BASED] 목표 거리 {target_dist_km}km → 시간 {target_time_min}분")
        else:
            target_time_min = 30.0
            target_dist_km = target_time_min / pace_min_per_km
            logger.info(f"[DEFAULT] 기본 시간 30분 → 거리 {target_dist_km:.2f}km")
        
        # 3. 이제 거리가 결정되었으므로 radius_meter 계산
        radius_meter = (target_dist_km / 2) * 1000 * 1.1
        if radius_meter < 1500: radius_meter = 1500
        if radius_meter > 8000:
            logger.warning(f"Capping radius at 8000m (target: {target_dist_km:.1f}km)")
            radius_meter = 8000
        
        logger.info(f"Fetching network with radius {radius_meter}m...")
        import asyncio
        # OSMnx 호출은 CPU 및 I/O 집약적인 동기 함수이므로 쓰레드 풀에서 실행
        G = await asyncio.to_thread(
            fetcher.fetch_pedestrian_network_from_point,
            center_point=user_location,
            distance=radius_meter
        )
        
        # ----------------------------
        # 경사도 로직 추가 (비동기 연동)
        # ----------------------------
        # 1. 고도 추가 (비동기 병렬 호출)
        await fetcher.add_elevation_to_nodes_async(G, db=db)
        # 2. 경사도 및 가중치 계산
        fetcher.calculate_edge_grades_and_weights(G)
        
        # 난이도에 따른 가중치 키 선택
        weight_key = 'length'
        if condition == "recovery":
            weight_key = 'weight_easy'
        elif condition == "challenge":
            weight_key = 'weight_hard'
        else:
            weight_key = 'length'
        
        # (페이스 계산은 이미 윗부분에서 완료됨)
        logger.info(f"Using weight key: {weight_key}, pace: {pace_min_per_km}분/km, target_time: {target_time_min}분, target_distance: {target_dist_km:.2f}km for condition: {condition}")
        # ----------------------------
        
        # 출발지 노드 찾기
        orig_node = ox.distance.nearest_nodes(G, user_location[1], user_location[0])
        
        # 3. 여러 후보 경로 생성 (고도차 기반 선택을 위해)
        num_candidates = 6  # 6개 후보 생성
        candidate_routes = []
        
        for i in range(num_candidates):
            # 랜덤한 방향으로 반환점 찾기 (각도는 크게 중요하지 않음)
            bearing = random.uniform(0, 360)
            logger.info(f"Generating candidate route {i+1}/{num_candidates} for bearing {bearing:.1f}°...")
            
            # 현재 순번의 목표 거리 (약간의 변화 추가)
            distance_variation = random.uniform(0.9, 1.1)
            current_target_km = target_dist_km * distance_variation
            
            # 도로 굴곡도 약 1.3 가정
            tortuosity_factor = 1.3
            current_target_radius_m = (current_target_km * 1000 / 2) / tortuosity_factor
            
            # 해당 방향에 있는 노드들 중 적절한 거리의 노드 찾기
            min_dist = current_target_radius_m * 0.85
            max_dist = current_target_radius_m * 1.15
            
            candidate_nodes = []
             
            for node, data in G.nodes(data=True):
                # Decimal 타입을 float로 변환 (numpy 호환성)
                node_lat = float(data['lat'])
                node_lng = float(data['lon'])
                
                # 거리 계산
                dist = ox.distance.great_circle(user_location[0], user_location[1], node_lat, node_lng)
                
                if min_dist <= dist <= max_dist:
                     # 방위각 계산
                     y = math.sin(math.radians(node_lng - user_location[1])) * math.cos(math.radians(node_lat))
                     x = math.cos(math.radians(user_location[0])) * math.sin(math.radians(node_lat)) - \
                         math.sin(math.radians(user_location[0])) * math.cos(math.radians(node_lat)) * \
                         math.cos(math.radians(node_lng - user_location[1]))
                     calc_bearing = math.degrees(math.atan2(y, x))
                     calc_bearing = (calc_bearing + 360) % 360
                     
                     angle_diff = abs(calc_bearing - bearing)
                     angle_diff = min(angle_diff, 360 - angle_diff)
                     
                     if angle_diff < 40: # 각도 조건 강화
                         candidate_nodes.append((node, angle_diff, dist))
            
            # 가장 각도가 잘 맞는 노드 선택
            if candidate_nodes:
                candidate_nodes.sort(key=lambda x: x[1]) # 각도 차이 적은 순
                dest_node = candidate_nodes[0][0]
                actual_dist_straight = candidate_nodes[0][2]
            else:
                 # 실패 시 랜덤 선택 (거리 조건만 만족하는)
                 # 타입 변환 보장하여 에러 방지
                 user_lat_float = float(user_location[0])
                 user_lng_float = float(user_location[1])
                 
                 possible_nodes = [
                     n for n, d in G.nodes(data=True) 
                     if min_dist <= ox.distance.great_circle(
                         user_lat_float, user_lng_float,
                         float(d['lat']), float(d['lon'])
                     ) <= max_dist
                 ]
                 if possible_nodes:
                     dest_node = random.choice(possible_nodes)
                 else:
                     continue 

            # 경로 계산 (왕복)
            try:
                # weight=weight_key를 사용하여 실제 거리 기반 또는 난이도 기반 최단 경로 탐색
                route_to = nx.shortest_path(G, orig_node, dest_node, weight=weight_key)
                
                # 오는 길 (가는 길 피해서)
                # 엣지 가중치 페널티 부여
                # 무방향 그래프(Graph)이므로 G[u][v]는 딕셔너리 ({'length': ...})
                edges_to_penalize = []
                
                try:
                    for u, v in zip(route_to[:-1], route_to[1:]):
                         if G.has_edge(u, v):
                             edge_data = G[u][v]
                             # 만약 MultiGraph라면 key가 있음, Graph라면 바로 속성
                             if isinstance(edge_data, dict) and weight_key in edge_data:
                                 edges_to_penalize.append((u, v, edge_data[weight_key]))
                                 edge_data[weight_key] *= 10 # 10배 패널티
                             else:
                                 # MultiGraph 호환성
                                 for key in edge_data:
                                     if isinstance(edge_data[key], dict) and weight_key in edge_data[key]:
                                         edges_to_penalize.append((u, v, key, edge_data[key][weight_key]))
                                         edge_data[key][weight_key] *= 10
                    
                    route_from = nx.shortest_path(G, dest_node, orig_node, weight=weight_key)
                    
                except nx.NetworkXNoPath:
                     route_from = route_to[::-1]
                finally:
                    # 패널티 복구
                    for item in edges_to_penalize:
                         if len(item) == 3:
                             u, v, original_val = item
                             G[u][v][weight_key] = original_val
                         elif len(item) == 4:
                             u, v, key, original_val = item
                             G[u][v][key][weight_key] = original_val

                if not route_from:
                    route_from = route_to[::-1]

                full_route = route_to + route_from[1:]
                
                # 실제 데이터 계산
                real_distance_m = fetcher.calculate_path_distance(G, full_route)
                real_distance_km = real_distance_m / 1000.0
                
                # 만약 계산된 거리가 너무 작으면(데이터 오류 등), 목표 거리를 대신 사용 (Fallback)
                if real_distance_km < 0.1:
                    logger.warning(f"Calculated distance too small ({real_distance_km}km). Using target {current_target_km}km instead.")
                    real_distance_km = current_target_km

                # 시간 계산 (컨디션별 페이스 적용)
                est_time_min = int(real_distance_km * pace_min_per_km)
                if est_time_min == 0: est_time_min = int(current_target_km * pace_min_per_km)
                
                # 좌표 변환
                path_coords = fetcher.path_to_kakao_coordinates(G, full_route)
                stats = fetcher.get_elevation_stats(G, full_route)
                
                # 절대값 고도차 누적합 계산 (핵심!)
                total_elev_change = fetcher.calculate_total_elevation_change(G, full_route)
                
                # 후보 경로 리스트에 저장 (나중에 정렬)
                candidate_routes.append({
                    'id': i + 1,
                    'route': full_route,
                    'elevation_change': total_elev_change,  # 절대값 누적합
                    'distance_km': real_distance_km,
                    'time': est_time_min,
                    'coords': path_coords,
                    'stats': stats
                })
                
                logger.info(f"Candidate {i+1}: {real_distance_km:.2f}km, 고도변화: {total_elev_change:.0f}m")

            except Exception as e:
                logger.error(f"Route calc failed for candidate {i+1}: {str(e)}", exc_info=True)
                continue
        
        # 4. 고도차 순위로 정렬 (낮음 → 높음)
        if len(candidate_routes) < 1:
            logger.error(f"No valid candidates generated. Target distance: {target_dist_km}km, Radius: {radius_meter}m")
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "NO_ROUTES_FOUND",
                    "message": f"해당 지역에서 {target_dist_km:.1f}km 경로를 생성할 수 없습니다. 목표 시간을 줄이거나 다른 위치를 선택해주세요.",
                    "suggestions": [
                        f"현재 목표: {target_time_min}분 → 추천: {target_time_min // 2}분 이하",
                        "또는 다른 시작 위치를 선택해주세요"
                    ]
                }
            )
        
        if len(candidate_routes) < 3:
            logger.warning(f"Only {len(candidate_routes)} candidates generated. Proceeding anyway...")
        
        candidate_routes.sort(key=lambda x: x['elevation_change'])
        
        # 5. 가장 낮음/중간/가장 높음 선택 (차이 극대화)
        selected_count = min(3, len(candidate_routes))
        if selected_count == 3:
            # 가장 낮음, 정중앙, 가장 높음
            selected_indices = [0, len(candidate_routes) // 2, len(candidate_routes) - 1]
        elif selected_count == 2:
            selected_indices = [0, len(candidate_routes) - 1]  # 낮음, 높음
        else:
            selected_indices = [0]  # 하나만
        
        route_names = ["평지 경로", "균형 경로", "업다운 경로"]
        
        for idx_position, route_idx in enumerate(selected_indices):
            route_data = candidate_routes[route_idx]
            candidates.append({
                "id": idx_position + 1,
                "name": route_names[idx_position],
                "distance": f"{route_data['distance_km']:.2f}km",
                "time": route_data['time'],
                "path": route_data['coords'],
                "reason": f"총 고도변화: {route_data['elevation_change']:.0f}m, 획득고도: {route_data['stats']['total_ascent']:.0f}m",
                "elevation_stats": route_data['stats']
            })

    except Exception as e:
        logger.error(f"Error generating route: {str(e)}", exc_info=True)
        raise ExternalAPIException(f"경로 생성에 실패했습니다: {str(e)}")
    
    # 4. 후보 경로가 없으면 에러 반환
    if not candidates:
        logger.error("No route candidates generated. Check OSMnx network or path finding logic.")
        raise ExternalAPIException(
            "경로를 생성할 수 없습니다. 해당 위치에서 적절한 도로 네트워크를 찾을 수 없습니다."
        )
        
    return {"candidates": candidates}


# ============================================
# 고도 데이터 프리페칭 (Pre-fetching)
# ============================================
@router.post(
    "/prefetch-elevation",
    response_model=CommonResponse,
    summary="고도 데이터 미리 수집",
    description="사용자가 위치를 설정했을 때 주변 고도 데이터를 백그라운드에서 미리 수집하여 캐싱합니다."
)
async def prefetch_elevation(
    request: ElevationPrefetchRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    사용자가 경로 설정을 완료하기 전에 미리 데이터를 채움
    """
    logger.info(f"Prefetching elevation for ({request.lat}, {request.lng}) with radius {request.radius}m")
    
    # 실제 수집 로직은 백그라운드 태스크로 넘겨서 사용자 응답 지연 방지
    background_tasks.add_task(
        run_elevation_prefetch,
        request.lat,
        request.lng,
        request.radius,
        db
    )
    
    return {
        "success": True,
        "message": "고도 데이터 프리페칭을 시작했습니다 (백그라운드)"
    }


async def run_elevation_prefetch(lat: float, lng: float, radius: float, db: Session = None):
    """백그라운드에서 실행되는 실제 수집 로직"""
    from app.services.road_network import RoadNetworkFetcher
    from app.db.database import SessionLocal  # 새로운 세션 생성용
    import asyncio
    
    # 백그라운드 작업은 별도의 DB 세션을 사용하는 것이 안전함
    # 의존성 주입된 db가 이미 닫혔을 수 있기 때문
    local_db = SessionLocal()
    
    try:
        fetcher = RoadNetworkFetcher()
        # 1. 주변 도로 네트워크 가져오기
        G = await asyncio.to_thread(
            fetcher.fetch_pedestrian_network_from_point,
            center_point=(lat, lng),
            distance=radius
        )
        
        # 2. 고도 수집 및 DB 저장 호출
        # 독립 세션(local_db) 전달
        await fetcher.add_elevation_to_nodes_async(G, db=local_db)
        
        logger.info(f"Background prefetch completed for ({lat}, {lng})")
        
    except Exception as e:
        logger.error(f"Error during background elevation prefetch: {e}")
    finally:
        # 사용 완료한 세션 닫기
        local_db.close()


# ============================================
# 비동기 경로 생성 (진행률 바)
# ============================================
@router.post(
    "/recommend-async",
    summary="AI 경로 추천 (비동기, 진행률 바)",
    description="""
    GPT와 OSMnx를 사용하여 사용자 맞춤형 경로를 추천합니다.
    
    **비동기 처리:**
    1. Task를 생성하고 task_id를 즉시 반환
    2. 백그라운드에서 경로 생성 실행
    3. /routes/tasks/{task_id} API로 진행률 확인
    4. 완료되면 /routes/tasks/{task_id}/result로 결과 조회
    """
)
async def recommend_route_async(
    request: RouteRecommendRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    비동기 경로 추천 엔드포인트 (진행률 바 지원)
    
    try:
        print(f"📝 [경로저장] 요청 데이터: name={request.name}, location=({request.location.latitude}, {request.location.longitude})")
        print(f"📝 [경로저장] SVG Path 길이: {len(request.svg_path)} characters")
        
        # Route 생성
        route = Route(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            name=request.name,
            type="custom",  # 커스텀 그리기
            mode="none",    # 도형 그리기 (운동 모드 없음)
            start_latitude=request.location.latitude,
            start_longitude=request.location.longitude,
            svg_path=request.svg_path,  # SVG Path 데이터 저장 (컬럼명 수정)
            status="active"
        )
        
        print(f"✅ [경로저장] Route 객체 생성 완료: id={route.id}")
        
        db.add(route)
        print(f"✅ [경로저장] DB에 추가 완료, commit 시도 중...")
        
        db.commit()
        print(f"✅ [경로저장] Commit 성공!")
        
        db.refresh(route)
        print(f"✅ [경로저장] Refresh 완료")
        
        return SaveCustomDrawingResponseWrapper(
            success=True,
            data=SaveCustomDrawingResponse(
                route_id=route.id,
                name=route.name,
                svg_path=route.svg_path,  # 컬럼명 수정
                estimated_distance=request.estimated_distance,
                created_at=route.created_at
            ),
            message="커스텀 경로가 성공적으로 저장되었습니다"
        )
        
    except Exception as e:
        print(f"❌ [경로저장] 에러 발생: {type(e).__name__}")
        print(f"❌ [경로저장] 에러 메시지: {str(e)}")
        import traceback
        print(f"❌ [경로저장] 스택 트레이스:\n{traceback.format_exc()}")
        
        db.rollback()
        raise ValidationException(
            message=f"경로 저장 중 오류가 발생했습니다: {str(e)}",
            field="route"
        )

# ============================================
# GPS 아트 경로 생성 (save_custom_drawing / get_shape_templates 활용)
# ============================================
@router.post(
    "/generate-gps-art",
    summary="GPS 아트 경로 생성",
    description="""
    - 커스텀: route_id 있으면 sav_custom_drawing으로 저장된 Route 사용, Option 3건만 추가
    - 프리셋: get_shape_templates의 shape_id로 RouteShape 조회 후 Route 1건 + Option 3건 생성.
    """,
)
def generate_gps_art(
    body: dict = Body(..., example={
        "route_id": "기존 Route UUID (커스텀 저장 후)",
        "shape_id": None,
        "target_distance_km": 5.0,
        "start": {"lat": 37.5, "lng": 127.0},
        "enable_rotation": True,
        "rotation_angle": None,
    }),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return generate_gps_art_impl(body=body, user_id=current_user.id, db=db)

# GPS 아트 경로 생성 (비동기)
@router.post(
    "/generate-gps-art-async",
    status_code=status.HTTP_202_ACCEPTED,
    summary="GPS 아트 경로 생성 (비동기)",
)
def generate_gps_art_async(
    body: dict = Body(...),
    background_tasks: BackgroundTasks = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task_id = str(uuid.uuid4())
    task = RouteGenerationTask(
        id=task_id,
        user_id=current_user.id,
        status="processing",
        progress=0,
        current_step="processing",
        estimated_remaining=90,
        request_data=body,
    )
    db.add(task)
    db.commit()

    background_tasks.add_task(_generate_gps_art_background, task_id)

    return {"success": True, "data": {"task_id": task_id}}

# 백그라운드 작업: GPS 아트 경로 생성
def _generate_gps_art_background(task_id: str):
    db = SessionLocal()
    try:
        task = db.query(RouteGenerationTask).filter(RouteGenerationTask.id == task_id).first()
        if not task:
            return

        # 중간중간 progress 업데이트 가능
        task.progress = 5
        task.current_step = "pending"
        task.estimated_remaining = 90
        db.commit()

        def update_progress(percent: int, step: str):
            # progress 업데이트 함수
            t = db.query(RouteGenerationTask).filter(RouteGenerationTask.id == task_id).first()
            if not t:
                logger.warning("[GPS 아트 경로 생성] 백그라운드 작업 중 태스크 조회 실패", task_id)
                return
            t.progress = max(t.progress or 0, min(percent, 99))
            t.current_step = step
            # 대충 남은 시간도 비례해서 줄여주는 예시 (선택 사항)
            if t.estimated_remaining is not None and t.estimated_remaining > 0:
                # 아주 단순한 예: 남은 퍼센트 기반 추정
                t.estimated_remaining = max(1, int(t.estimated_remaining * (100 - percent) / 100))
            db.commit()

        logger.info("[GPS 아트 경로 생성] 백그라운드 작업 시작", task_id)
        # 중간 단계: generate_gps_art_impl 호출 시 콜백 전달
        result = generate_gps_art_impl(
            body=task.request_data, 
            user_id=task.user_id, 
            db=db,
            on_progress=update_progress, # 진행 상태 콜백 전달
        )

        logger.info("[GPS 아트 경로 생성] 백그라운드 작업 완료", task_id)

        task.status = "completed"
        task.progress = 100
        task.current_step = "completed"
        task.estimated_remaining = 0
        task.route_id = result["route_id"]
        task.completed_at = datetime.now()
        db.commit()
    except Exception as e:
        db.rollback()
        task = db.query(RouteGenerationTask).filter(RouteGenerationTask.id == task_id).first()
        if task:
            task.status = "failed"
            task.error_message = str(e)[:500]
            task.completed_at = datetime.now()
            db.commit()
    finally:
        db.close()
    
        