# ============================================
# app/api/v1/routes.py - 경로 API 라우터
# ============================================
# 경로 생성, 옵션 조회, 저장/삭제 등 경로 관련 API를 제공합니다.
# AI 기반 경로 생성 및 안전도 평가 기능을 포함합니다.
# ============================================
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, Path, status, BackgroundTasks, Body
from sqlalchemy.orm import Session
from datetime import datetime
from pydantic import BaseModel, Field
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
    RouteOptionSchema, RoutePointSchema,
    SaveCustomDrawingRequest, SaveCustomDrawingResponse, SaveCustomDrawingResponseWrapper
)
from app.schemas.common import CommonResponse
from app.core.exceptions import NotFoundException, ValidationException
from app.gps_art.generate_routes import generate_routes
from app.models.route import Route, RouteOption, RouteShape

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
# 커스텀 그림 경로 저장
# ============================================
@router.post(
    "/custom-drawing",
    response_model=SaveCustomDrawingResponseWrapper,
    status_code=status.HTTP_201_CREATED,
    summary="커스텀 그림 경로 저장",
    description="""
    사용자가 직접 그린 경로를 SVG Path 형태로 저장합니다.
    
    **저장 정보:**
    - SVG Path 데이터
    - 시작 위치 (위도, 경도)
    - 예상 거리
    - 경로 이름
    
    **반환 데이터:**
    - route_id: 생성된 경로 ID
    - 저장된 경로 정보
    """
)
def save_custom_drawing(
    request: SaveCustomDrawingRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """커스텀 그림 경로 저장 엔드포인트"""
    
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
            custom_svg_path=request.svg_path,  # SVG Path 데이터 저장 (컬럼명 수정)
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
                svg_path=route.custom_svg_path,  # 컬럼명 수정
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
    route_id_from_body = body.get("route_id")
    shape_id = body.get("shape_id")
    target_km = float(body.get("target_distance_km", 5.0))
    enable_rotation = body.get("enable_rotation", True)
    rotation_angles = body.get("rotation_angles")

    # 커스텀: route_id 있음 -> save_custom_drawing으로 만든 Route 활용
    if route_id_from_body:
        route = db.query(Route).filter(
            Route.id == route_id_from_body,
            Route.user_id == current_user.id,
        ).first()
        if not route:
            raise ValidationException(
                message="해당 경로를 찾을 수 없습니다.",
                field="route_id"
            )
        if not route.custom_svg_path:
            raise ValidationException(
                message="해당 경로에 SVG 데이터가 없습니다.",
                field="route_id",
            )
        start_lat = float(route.start_latitude)
        start_lon = float(route.start_longitude)
        svg_path = route.custom_svg_path
        mode = "custom"
        result = generate_routes(
            start_lat=start_lat,
            start_lon=start_lon,
            svg_path=svg_path,
            target_distance_km=target_km,
            mode=mode,
            shape_id=None,
            enable_rotation=enable_rotation,
            rotation_angles=rotation_angles,
        )
        route_id = route.id

    # 프리셋: shape_id 있음 -> get_shape_templates의 shape_id로 도형 사용
    elif shape_id:
        shape = db.query(RouteShape).filter(
            RouteShape.id == shape_id,
            RouteShape.is_active == True,
        ).first()
        if not shape:
            raise ValidationException(
                message="존재하지 않는 도형입니다.",
                field="shape_id",
            )
        svg_path = (shape.svg_url or "").strip() or (body.get("svg_path") or "").strip()
        if not svg_path:
            raise ValidationException(
                message="해당 도형에 SVG 경로가 없습니다.",
                field="shape_id",
            )
        # DB에 없었으면 body에서 받은 값으로 svg_url 저장 (다음부터 DB 사용)
        if not (shape.svg_url or "").strip():
            shape.svg_url = svg_path
            db.commit()
        start = body.get("start", {})
        start_lat = float(start.get("lat", 37.5))
        start_lon = float(start.get("lng", 127.0))
        result = generate_routes(
            start_lat=start_lat,
            start_lon=start_lon,
            svg_path=svg_path,
            target_distance_km=target_km,
            mode="shape",
            shape_id=shape_id,
            enable_rotation=enable_rotation,
            rotation_angles=rotation_angles,
        )
        route = Route(
            user_id=current_user.id,
            shape_id=shape_id,
            name=f"{shape.name} 경로",
            type="preset",
            mode=body.get("mode") or "none",
            start_latitude=start_lat,
            start_longitude=start_lon,
            custom_svg_path=None,
            status="active",
        )
        db.add(route)
        db.flush()
        route_id = route.id

    # 그 외: route_id 없이 커스텀(바로 생성) -> Route 새로 만들고 Option 3건 생성
    else:
        svg_path = body.get("svg_path") or ""
        if not svg_path:
            raise ValidationException(
                message="커스텀 그리기 시 svg_path 또는 route_id가 필요합니다.",
                field="svg_path",
            )
        start = body.get("start", {})
        start_lat = float(start.get("lat", 37.5))
        start_lon = float(start.get("lng", 127.0))
        result = generate_routes(
            start_lat=start_lat,
            start_lon=start_lon,
            svg_path=svg_path,
            target_distance_km=target_km,
            mode="custom",
            shape_id=None,
            enable_rotation=enable_rotation,
            rotation_angles=rotation_angles,
        )
        route = Route(
            user_id=current_user.id,
            shape_id=None,
            name=body.get("name") or "커스텀 경로",
            type="custom",
            mode=body.get("mode") or "none",
            start_latitude=start_lat,
            start_longitude=start_lon,
            custom_svg_path=svg_path,
            status="active",
        )
        db.add(route)
        db.flush()
        route_id = route.id
    
    # 공통: RouteOption 3건 생성
    option_names = ["1순위 (가장 유사)", "2순위", "3순위"]
    tags = [None, "추천", "BEST"]
    option_ids = []

    # 거리 순으로 difficulty 부여 (짧은→짧은 코스, 중간→보통, 긴→긴 코스)
    routes_list = result["routes"]
    distances_with_idx = [(i, float(r.get("distance_km", 0))) for i, r in enumerate(routes_list)]
    distances_with_idx.sort(key=lambda x: x[1])
    difficulty_by_idx = {
        distances_with_idx[0][0]: "짧은 코스",
        distances_with_idx[1][0]: "보통",
        distances_with_idx[2][0]: "긴 코스",
    }

    for i, r in enumerate(result["routes"]):
        coords = r.get("coordinates", [])
        distance_km = float(r.get("distance_km", 0))
        difficulty = difficulty_by_idx[i]
        opt = RouteOption(
            route_id=route_id,
            option_number=i + 1,
            name=option_names[i],
            distance=distance_km,
            estimated_time=max(1, int(round(distance_km * 7))),
            difficulty=difficulty,
            tag=tags[i], # 나중에 수정해야함
            coordinates=coords,
            safety_score=90 - i * 3,
            elevation=0,
            lighting_score=0,
            sidewalk_score=0,
        )
        db.add(opt)
        db.flush()
        option_ids.append(opt.id)

