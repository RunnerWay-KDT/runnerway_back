# ============================================
# app/api/v1/users.py - 사용자 API 라우터
# ============================================
# 사용자 프로필, 설정, 통계, 운동 기록 등 사용자 관련 API를 제공합니다.
# ============================================

from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from datetime import datetime

from app.db.database import get_db
from app.api.deps import get_current_user
from app.models.user import User, UserStats
from app.models.workout import Workout
from app.models.route import SavedRoute, Route
from app.schemas.user import (
    UserProfileResponse, UserProfileResponseWrapper,
    UserProfileUpdateRequest, UserUpdateResponse, UserUpdateResponseWrapper,
    UserDeleteRequest, UserDeleteResponse,
    UserStatsDetailSchema, UserPreferencesSchema
)
from app.schemas.settings import (
    UserSettingsSchema, UpdateUserSettingsRequest,
    UserSettingsResponseWrapper, UserSettingsUpdateResponseWrapper
)
from app.schemas.workout import (
    WorkoutSummarySchema, WorkoutListResponse, WorkoutListResponseWrapper
)
from app.schemas.route import SavedRouteSchema
from app.schemas.common import PaginationInfo


router = APIRouter(prefix="/users", tags=["Users"])


# ============================================
# 내 프로필 조회
# ============================================
@router.get(
    "/me",
    response_model=UserProfileResponseWrapper,
    summary="내 프로필 조회",
    description="""
    현재 로그인한 사용자의 프로필 정보를 조회합니다.
    
    **포함 정보:**
    - 기본 정보 (이메일, 이름, 아바타)
    - 통계 정보 (총 거리, 운동 횟수 등)
    - 사용자 설정
    """
)
def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """내 프로필 조회 엔드포인트"""
    
    # 북마크한 경로 수 계산
    saved_routes_count = db.query(SavedRoute).filter(
        SavedRoute.user_id == current_user.id
    ).count()
    
    # 통계 정보
    stats = UserStatsDetailSchema(
        total_distance=float(current_user.stats.total_distance) if current_user.stats else 0,
        total_workouts=current_user.stats.total_workouts if current_user.stats else 0,
        saved_routes_count=saved_routes_count
    )
    
    # 설정 정보
    preferences = None
    if current_user.settings:
        preferences = UserPreferencesSchema(
            night_safety_mode=current_user.settings.night_safety_mode,
            auto_night_mode=current_user.settings.auto_night_mode
        )
    
    # 응답 데이터 생성
    profile_data = UserProfileResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        avatar_url=current_user.avatar_url,
        stats=stats,
        preferences=preferences,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at
    )
    
    return UserProfileResponseWrapper(
        success=True,
        data=profile_data
    )


# ============================================
# 프로필 수정
# ============================================
@router.patch(
    "/me",
    response_model=UserUpdateResponseWrapper,
    summary="프로필 수정",
    description="""
    프로필 정보를 수정합니다.
    
    **수정 가능 항목:**
    - 이름
    - 아바타 이미지 URL
    - 사용자 설정
    
    **부분 업데이트:** 변경할 필드만 전송
    """
)
def update_my_profile(
    request: UserProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """프로필 수정 엔드포인트"""
    
    # 이름 변경
    if request.name is not None:
        current_user.name = request.name
    
    # 아바타 변경
    if request.avatar_url is not None:
        current_user.avatar_url = request.avatar_url
    
    # 설정 변경
    if request.preferences is not None and current_user.settings:
        if request.preferences.night_safety_mode is not None:
            current_user.settings.night_safety_mode = request.preferences.night_safety_mode
        if request.preferences.auto_night_mode is not None:
            current_user.settings.auto_night_mode = request.preferences.auto_night_mode
    
    current_user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(current_user)
    
    # 북마크한 경로 수 계산
    saved_routes_count = db.query(SavedRoute).filter(
        SavedRoute.user_id == current_user.id
    ).count()
    
    # 통계 정보
    stats = UserStatsDetailSchema(
        total_distance=float(current_user.stats.total_distance) if current_user.stats else 0,
        total_workouts=current_user.stats.total_workouts if current_user.stats else 0,
        saved_routes_count=saved_routes_count
    )
    
    # 응답 데이터
    preferences = None
    if current_user.settings:
        preferences = UserPreferencesSchema(
            night_safety_mode=current_user.settings.night_safety_mode,
            auto_night_mode=current_user.settings.auto_night_mode
        )
    
    return UserUpdateResponseWrapper(
        success=True,
        data=UserUpdateResponse(
            id=current_user.id,
            email=current_user.email,
            name=current_user.name,
            avatar_url=current_user.avatar_url,
            provider=None,
            is_active=current_user.deleted_at is None,
            stats=stats,
            preferences=preferences,
            updated_at=current_user.updated_at
        ),
        message="프로필이 업데이트되었습니다"
    )


# ============================================
# 회원 탈퇴
# ============================================
@router.delete(
    "/me",
    response_model=UserDeleteResponse,
    summary="회원 탈퇴",
    description="""
    회원 탈퇴를 처리합니다.
    
    **일반 로그인 사용자:** 비밀번호 확인 필요
    
    **주의:** 
    - Soft Delete로 처리됨
    """
)
def delete_my_account(
    request: UserDeleteRequest = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """회원 탈퇴 엔드포인트"""
    from app.core.security import verify_password
    from app.core.exceptions import ValidationException
    
    # 비밀번호 확인
    if current_user.password_hash:
        if not request or not request.password:
            raise ValidationException(
                message="비밀번호를 입력해주세요",
                field="password"
            )
        
        if not verify_password(request.password, current_user.password_hash):
            raise ValidationException(
                message="비밀번호가 올바르지 않습니다",
                field="password"
            )
    
    # Soft Delete (deleted_at 설정)
    current_user.deleted_at = datetime.utcnow()
    db.commit()
    
    return UserDeleteResponse(
        success=True,
        message="회원 탈퇴가 완료되었습니다",
        data={"deleted_at": current_user.deleted_at.isoformat()}
    )


# ============================================
# 내 운동 기록 조회
# ============================================
@router.get(
    "/me/workouts",
    response_model=WorkoutListResponseWrapper,
    summary="내 운동 기록 조회",
    description="""
    내 운동 기록 목록을 조회합니다.
    
    **정렬 옵션:**
    - date_desc: 최신순 (기본값)
    - distance_desc: 거리순
    - calories_desc: 칼로리순
    
    **필터:**
    - mode: running/walking
    """
)
def get_my_workouts(
    page: int = Query(1, ge=1, description="페이지 번호"),
    limit: int = Query(20, ge=1, le=100, description="페이지당 항목 수"),
    sort: str = Query("date_desc", description="정렬 방식"),
    mode: Optional[str] = Query(None, description="운동 모드 (running/walking)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """내 운동 기록 조회 엔드포인트"""
    
    # 기본 쿼리
    query = db.query(Workout).filter(
        Workout.user_id == current_user.id,
        Workout.status == "completed",
        Workout.deleted_at.is_(None)
    )
    
    # 모드 필터
    if mode:
        query = query.filter(Workout.mode == mode)
    
    # 정렬
    if sort == "distance_desc":
        query = query.order_by(Workout.distance.desc())
    elif sort == "calories_desc":
        query = query.order_by(Workout.calories.desc())
    elif sort == "date_asc":
        query = query.order_by(Workout.completed_at.asc())
    else:  # date_desc (기본값)
        query = query.order_by(Workout.completed_at.desc())
    
    # 전체 개수
    total_count = query.count()
    
    # 페이지네이션
    offset = (page - 1) * limit
    workouts = query.offset(offset).limit(limit).all()
    
    # 응답 데이터 변환
    # 북마크 여부를 한 번에 조회 (N+1 방지)
    from app.models.route import RouteShape
    workout_route_ids = [w.route_id for w in workouts if w.route_id]
    bookmarked_route_ids = set()
    route_info_map = {}  # route_id → {name, svg_path, shape_id}
    shape_map = {}  # shape_id → {shape_id, shape_name, icon_name}
    if workout_route_ids:
        bookmarked = db.query(SavedRoute.route_id).filter(
            SavedRoute.user_id == current_user.id,
            SavedRoute.route_id.in_(workout_route_ids)
        ).all()
        bookmarked_route_ids = {r.route_id for r in bookmarked}
        
        # route별 name, svg_path, shape_id 한 번에 조회 (N+1 방지)
        route_rows = db.query(Route.id, Route.name, Route.svg_path, Route.shape_id).filter(
            Route.id.in_(workout_route_ids)
        ).all()
        route_info_map = {r.id: {"name": r.name, "svg_path": r.svg_path, "shape_id": r.shape_id} for r in route_rows}
        
        # shape 정보 일괄 조회 (N+1 방지)
        shape_ids = list({r.shape_id for r in route_rows if r.shape_id})
        if shape_ids:
            shape_rows = db.query(RouteShape.id, RouteShape.name, RouteShape.icon_name).filter(
                RouteShape.id.in_(shape_ids)
            ).all()
            shape_map = {s.id: {"shape_id": s.id, "shape_name": s.name, "icon_name": s.icon_name} for s in shape_rows}
    
    workout_list = []
    for workout in workouts:
        # routes.name을 우선 사용, 없으면 workouts.route_name 폴백
        route_info = route_info_map.get(workout.route_id, {}) if workout.route_id else {}
        display_name = route_info.get("name") or workout.route_name
        # shape 정보 결정
        shape_data = None
        route_shape_id = route_info.get("shape_id")
        if route_shape_id and route_shape_id in shape_map:
            shape_data = shape_map[route_shape_id]
        workout_list.append(WorkoutSummarySchema(
            id=workout.id,
            route_id=workout.route_id,
            route_name=display_name,
            type=workout.type,
            mode=workout.mode,
            distance=float(workout.distance) if workout.distance else None,
            duration=workout.duration,
            avg_pace=workout.avg_pace,
            calories=workout.calories,
            route_completion=float(workout.route_completion) if workout.route_completion else None,
            is_bookmarked=workout.route_id in bookmarked_route_ids if workout.route_id else False,
            svg_path=route_info.get("svg_path") if workout.route_id else None,
            shape=shape_data,
            started_at=workout.started_at,
            completed_at=workout.completed_at
        ))
    
    # 페이지네이션 정보
    total_pages = (total_count + limit - 1) // limit if total_count > 0 else 1
    pagination = {
        "current_page": page,
        "total_pages": total_pages,
        "total_count": total_count,
        "has_next": page < total_pages,
        "has_prev": page > 1
    }
    
    return WorkoutListResponseWrapper(
        success=True,
        data=WorkoutListResponse(
            workouts=workout_list,
            pagination=pagination
        ),
        message="운동 기록 조회 성공"
    )


# ============================================
# 저장한 경로 조회
# ============================================
@router.get(
    "/me/saved-routes",
    summary="저장한 경로 조회",
    description="""
    북마크한 경로 목록을 조회합니다.
    
    **정렬 옵션:**
    - date_desc: 최신 저장순 (기본)
    - date_asc: 오래된 저장순
    - distance_desc: 거리 먼 순
    - safety_desc: 안전도 높은 순
    """
)
def get_my_saved_routes(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    sort: str = Query("date_desc", description="정렬: date_desc, date_asc, distance_desc, safety_desc"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """저장한 경로 조회 엔드포인트"""
    from app.models.route import RouteShape, RouteOption
    from app.models.user import User as UserModel
    from sqlalchemy.orm import joinedload, selectinload
    
    # joinedload로 Route, RouteShape, RouteOption을 한 번에 로드 (N+1 쿼리 방지)
    query = db.query(SavedRoute).options(
        joinedload(SavedRoute.route)
        .joinedload(Route.shape),
        joinedload(SavedRoute.route)
        .selectinload(Route.options),
    ).filter(
        SavedRoute.user_id == current_user.id
    )
    
    # 정렬
    if sort == "date_asc":
        query = query.order_by(SavedRoute.saved_at.asc())
    else:
        query = query.order_by(SavedRoute.saved_at.desc())
    
    # 전체 개수 (joinedload 전 count용 별도 쿼리)
    total_count = db.query(SavedRoute).filter(
        SavedRoute.user_id == current_user.id
    ).count()
    
    # 페이지네이션
    offset = (page - 1) * limit
    saved_routes = query.offset(offset).limit(limit).all()
    
    # 작성자 ID 일괄 수집 → 단일 쿼리로 조회
    author_ids = list({sr.route.user_id for sr in saved_routes if sr.route})
    authors_map = {}
    if author_ids:
        authors = db.query(UserModel).filter(UserModel.id.in_(author_ids)).all()
        authors_map = {a.id: a.name for a in authors}
    
    # 응답 데이터 변환 (추가 쿼리 없음)
    routes_list = []
    for saved_route in saved_routes:
        route = saved_route.route
        if not route:
            continue
        
        # shape 정보 (이미 joinedload됨)
        shape_data = None
        if route.shape:
            shape_data = {
                "shape_id": route.shape.id,
                "shape_name": route.shape.name,
                "icon_name": route.shape.icon_name,
            }
        
        # 작성자 정보 (일괄 조회된 맵에서 가져옴)
        author_data = {
            "id": route.user_id,
            "name": authors_map.get(route.user_id, "알 수 없음"),
        }
        
        # 옵션에서 거리·안전도 (이미 selectinload됨)
        distance = float(route.options[0].distance) if route.options else 0
        safety_score = route.options[0].safety_score if route.options else 0
        
        routes_list.append({
            "id": saved_route.id,
            "route_id": route.id,
            "route_option_id": saved_route.route_option_id,
            "route_name": route.name,
            "type": route.type,
            "mode": route.mode,
            "distance": distance,
            "safety_score": safety_score,
            "shape": shape_data,
            "svg_path": route.svg_path,
            "author": author_data,
            "location": {
                "latitude": float(route.start_latitude) if route.start_latitude else 0,
                "longitude": float(route.start_longitude) if route.start_longitude else 0,
            },
            "saved_at": saved_route.saved_at.isoformat() if saved_route.saved_at else None,
        })
    
    # distance / safety 정렬은 파이썬 쪽에서 처리
    if sort == "distance_desc":
        routes_list.sort(key=lambda r: r["distance"], reverse=True)
    elif sort == "safety_desc":
        routes_list.sort(key=lambda r: r["safety_score"], reverse=True)
    
    # 페이지네이션 정보
    total_pages = (total_count + limit - 1) // limit if total_count > 0 else 1
    
    return {
        "success": True,
        "data": {
            "routes": routes_list,
            "pagination": {
                "current_page": page,
                "total_pages": total_pages,
                "total_count": total_count,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        },
        "message": "저장한 경로 조회 성공"
    }


# ============================================
# 사용자 설정 조회
# ============================================
@router.get(
    "/me/settings",
    response_model=UserSettingsResponseWrapper,
    summary="사용자 설정 조회",
    description="""
    현재 사용자의 앱 설정을 조회합니다.
    
    **포함 정보:**
    - 앱 설정 (다크모드, 언어)
    - 알림 설정 (푸시, 운동 알림, 목표 달성, 커뮤니티 활동)
    - 운동 설정 (자동 랩, 야간 안전 모드, 자동 야간 모드)
    """
)
def get_my_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """사용자 설정 조회 엔드포인트"""
    from app.models.user import UserSettings
    from app.core.exceptions import NotFoundException
    
    # 설정이 없으면 생성
    if not current_user.settings:
        settings = UserSettings(user_id=current_user.id)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    else:
        settings = current_user.settings
    
    # 응답 데이터
    settings_data = UserSettingsSchema(
        night_safety_mode=settings.night_safety_mode,
        auto_night_mode=settings.auto_night_mode
    )
    
    return UserSettingsResponseWrapper(
        success=True,
        data=settings_data,
        message="설정 조회 성공"
    )


# ============================================
# 사용자 설정 업데이트
# ============================================
@router.patch(
    "/me/settings",
    response_model=UserSettingsUpdateResponseWrapper,
    summary="사용자 설정 업데이트",
    description="""
    사용자의 앱 설정을 업데이트합니다.
    
    **수정 가능 항목:**
    - dark_mode: 다크 모드 활성화 (boolean)
    - night_safety_mode: 야간 안전 모드 (boolean)
    - auto_night_mode: 자동 야간 모드 (boolean)
    
    **부분 업데이트:** 변경할 필드만 전송
    """
)
def update_my_settings(
    request: UpdateUserSettingsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """사용자 설정 업데이트 엔드포인트"""
    from app.models.user import UserSettings
    
    # 설정이 없으면 생성
    if not current_user.settings:
        settings = UserSettings(user_id=current_user.id)
        db.add(settings)
        db.flush()
    else:
        settings = current_user.settings
    
    # 업데이트할 필드만 변경
    update_data = request.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        if hasattr(settings, field):
            setattr(settings, field, value)
    
    db.commit()
    db.refresh(settings)
    
    # 응답 데이터
    settings_data = UserSettingsSchema(
        night_safety_mode=settings.night_safety_mode,
        auto_night_mode=settings.auto_night_mode
    )
    
    return UserSettingsUpdateResponseWrapper(
        success=True,
        data=settings_data,
        message="설정이 업데이트되었습니다"
    )
