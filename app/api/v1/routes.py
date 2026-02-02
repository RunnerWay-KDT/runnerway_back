# ============================================
# app/api/v1/routes.py - 경로 API 라우터
# ============================================
# 경로 생성, 옵션 조회, 저장/삭제 등 경로 관련 API를 제공합니다.
# AI 기반 경로 생성 및 안전도 평가 기능을 포함합니다.
# ============================================

from typing import Optional
from fastapi import APIRouter, Depends, Query, Path, status, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime
import uuid

from app.db.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.route import Route, RouteOption, SavedRoute, RouteGenerationTask, RouteShape
from app.schemas.route import (
    RouteGenerateRequest, RouteGenerateResponse, RouteGenerateResponseWrapper,
    RouteOptionsResponse, RouteOptionsResponseWrapper,
    RouteDetailResponse, RouteDetailResponseWrapper,
    RouteSaveRequest, RouteSaveResponse,
    RouteSaveRequest, RouteSaveResponse,
    RouteOptionSchema, RoutePointSchema,
    RouteRecommendRequest, RouteRecommendResponse
)
from app.schemas.common import CommonResponse
from app.core.exceptions import NotFoundException, ValidationException
import osmnx as ox
import networkx as nx
import openai
import logging
import random
import math
import time
import os
from dotenv import load_dotenv

# 로깅 설정
logger = logging.getLogger(__name__)

# OSMnx 설정
ox.settings.use_cache = True
ox.settings.log_console = False

# OpenAI 설정
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")


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
    task_id = str(uuid.uuid4())
    
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
    background_tasks.add_task(
        generate_route_background,
        task_id=task_id,
        db=db
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
        "route_id": task.route_id
    }
    
    # 완료된 경우 경로 정보 포함
    if task.status == "completed" and task.route_id:
        response_data["route_id"] = task.route_id
    
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
    route_id: int = Path(..., description="경로 ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """경로 옵션 조회 엔드포인트"""
    
    # 경로 조회
    route = db.query(Route).filter(
        Route.id == route_id,
        Route.user_id == current_user.id
    ).first()
    
    if not route:
        raise NotFoundException(
            resource="Route",
            resource_id=route_id
        )
    
    # 옵션 목록 조회
    options = db.query(RouteOption).filter(
        RouteOption.route_id == route_id
    ).all()
    
    option_list = []
    for opt in options:
        option_list.append(RouteOptionSchema(
            id=opt.id,
            type=opt.option_type,
            distance=float(opt.distance),
            estimated_time=opt.estimated_time,
            safety_score=opt.safety_score,
            elevation_gain=opt.elevation_gain,
            path_preview=opt.path_data.get("coordinates", [])[:10] if opt.path_data else []
        ))
    
    return RouteOptionsResponseWrapper(
        success=True,
        data=RouteOptionsResponse(
            route_id=route.id,
            shape={
                "id": route.shape.id if route.shape else None,
                "name": route.shape.name if route.shape else None,
                "icon": route.shape.icon_name if route.shape else None
            },
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
async def recommend_route(request: RouteRecommendRequest):
    """
    AI 기반 경로 추천 엔드포인트
    (거리/시간 정확도 개선)
    """
    from app.services.road_network import RoadNetworkFetcher
    
    user_location = (request.lat, request.lng)
    
    # 1. 목표 거리 설정 (컨디션 기반 또는 GPT)
    target_dist_km = request.target_distance_km
    
    # 0. 프롬프트 기반 난이도/거리 설정 (GPT 제거 -> 키워드 매칭)
    # Frontend sends constructed prompts like "목적: 회복 러닝..."
    if request.prompt:
        p = request.prompt.lower()
        if "recovery" in p or "회복" in p or "easy" in p:
            if not target_dist_km: target_dist_km = random.uniform(2.0, 3.0) 
            condition = "recovery"
        elif "fat" in p or "지방" in p or "burn" in p:
            # 지방 연소 난이도 하향 조정 (3.5 ~ 4.5km)
            if not target_dist_km: target_dist_km = random.uniform(3.5, 4.5)
            condition = "fat-burn"
        elif "challenge" in p or "기록" in p or "hard" in p:
            if not target_dist_km: target_dist_km = random.uniform(7.0, 10.0) 
            condition = "challenge"
        else:
            condition = "normal"

    # 거리가 여전히 없으면 기본값 (Fallback)
    if not target_dist_km or target_dist_km == 0.0:
        target_dist_km = 3.0

    logger.info(f"Processing request: {user_location}, distance: {target_dist_km}km")
    
    candidates = []

    try:
        # 1. RoadNetworkFetcher 초기화 및 그래프 다운로드
        fetcher = RoadNetworkFetcher()
        
        # radius_meter 계산 (여유있게 설정하되 너무 크면 타임아웃 발생)
        # 10km 코스(반경 5km)의 경우 데이터가 매우 큼. 
        # 안전 계수를 1.5 -> 1.1로 줄여서 데이터 양 최적화
        radius_meter = (target_dist_km / 2) * 1000 * 1.1
        if radius_meter < 1500: radius_meter = 1500
        
        # 5km 이상 반경(즉 10km 코스)일 경우 타임아웃 방지를 위해 약간 더 축소하거나 경고
        if radius_meter > 5000:
            radius_meter = 5000 # Max cap per request for performance safety
        
        logger.info(f"Fetching network with radius {radius_meter}m using RoadNetworkFetcher...")
        import asyncio
        # OSMnx 호출은 CPU 및 I/O 집약적인 동기 함수이므로 쓰레드 풀에서 실행
        G = await asyncio.to_thread(
            fetcher.fetch_pedestrian_network_from_point,
            center_point=user_location,
            distance=radius_meter
        )
        
        # ----------------------------
        # 경사도 로직 추가 (VWorld API 비동기 연동)
        # ----------------------------
        from app.config import settings
        # 1. 고도 추가 (비동기 병렬 호출)
        await fetcher.add_elevation_to_nodes_async(G, api_key=settings.VWORLD_API_KEY)
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
        
        logger.info(f"Using weight key: {weight_key} for condition: {condition}")
        # ----------------------------
        
        # 출발지 노드 찾기
        orig_node = ox.distance.nearest_nodes(G, user_location[1], user_location[0])
        
        # 3. 3방향 (0도, 120도, 240도) 반환점 찾기
        offset = random.uniform(0, 60)
        bearings = [(0 + offset) % 360, (120 + offset) % 360, (240 + offset) % 360] 
        route_names = ["Route A", "Route B", "Route C"]
        
        # 난이도별 거리 계수 (쉬움: 0.85배, 보통: 1.0배, 도전: 1.15배) -> 차이 명확화
        dist_multipliers = [0.85, 1.0, 1.15]
        
        for i, bearing in enumerate(bearings):
            logger.info(f"Generating route {i+1} for bearing {bearing}...")
            
            # 현재 순번의 목표 거리 및 반경 재계산
            current_target_km = target_dist_km * dist_multipliers[i]
            
            # 도로 굴곡도 약 1.3 가정
            tortuosity_factor = 1.3
            current_target_radius_m = (current_target_km * 1000 / 2) / tortuosity_factor
            
            # 해당 방향에 있는 노드들 중 적절한 거리의 노드 찾기
            min_dist = current_target_radius_m * 0.85
            max_dist = current_target_radius_m * 1.15
            
            candidate_nodes = []
             
            for node, data in G.nodes(data=True):
                node_lat = data['lat']
                node_lng = data['lon']
                
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
                 possible_nodes = [
                     n for n, d in G.nodes(data=True) 
                     if min_dist <= ox.distance.great_circle(user_location[0], user_location[1], d['lat'], d['lon']) <= max_dist
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

                # 시간 계산 (평균 러닝 페이스 6분/km)
                pace_min_per_km = 6.0 
                est_time_min = int(real_distance_km * pace_min_per_km)
                if est_time_min == 0: est_time_min = int(current_target_km * 6)
                
                # 좌표 변환
                path_coords = fetcher.path_to_kakao_coordinates(G, full_route)
                stats = fetcher.get_elevation_stats(G, full_route)
                
                candidates.append({
                    "id": i + 1,
                    "name": route_names[i],
                    "distance": f"{real_distance_km:.2f}km",
                    "time": est_time_min,
                    "path": path_coords,
                    "reason": f"획득고도: {stats['total_ascent']}m, 평균경사도: {stats['average_grade']}%",
                    "elevation_stats": stats
                })

            except Exception as e:
                logger.error(f"Route calc failed for route {i}: {str(e)}", exc_info=True)
                continue

    except Exception as e:
        logger.error(f"Error generation route: {str(e)}", exc_info=True)
        # Main logic failed, but we continue to fallback below
    
    # 4. Fallback checking (Always runs, even if exception occurred above)
    if not candidates:
        logger.warning("No candidates generated via graph (or error occurred). Using fallback geometric generation via RoadNetworkFetcher.")
        
        # 3가지 옵션 생성
        fallback_multipliers = [0.85, 1.0, 1.15]
        route_names = ["Route A", "Route B", "Route C"]
        
        for i, mult in enumerate(fallback_multipliers):
            dist_km = target_dist_km * mult
            
            # Use RoadNetworkFetcher for random loop calculation
            # seed=i ensures differentiation between Route A, B, C
            fallback_path = fetcher.generate_random_loop_route(user_location, dist_km, seed=i)
            
            candidates.append({
                "id": i + 1,
                "name": route_names[i],
                "distance": f"{dist_km:.2f}km",
                "time": int(dist_km * 6),
                "path": fallback_path
            })
        
    return {"candidates": candidates}
