# ============================================
# app/services/route_service.py - 경로 서비스
# ============================================
# 경로 생성, 조회, 저장 등 경로 관련 비즈니스 로직을 처리합니다.
# ============================================

from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
import uuid

from app.models.route import Route, RouteOption, SavedRoute, RouteGenerationTask, RouteShape
from app.services.safety_score import (
    compute_safety_score,
    load_cctv_points,
    load_lamp_points,
    DEFAULT_CCTV_CSV,
    DEFAULT_LAMP_CSV,
)
from app.core.exceptions import NotFoundException, ValidationException


class RouteService:
    """
    경로 서비스 클래스
    
    [신입 개발자를 위한 설명]
    경로 관련 모든 비즈니스 로직을 담당합니다.
    - 경로 생성 요청/상태 관리
    - 경로 옵션 조회
    - 경로 저장/삭제
    - 모양 템플릿 관리
    """
    
    def __init__(self, db: Session):
        """
        RouteService 초기화
        
        Args:
            db: 데이터베이스 세션
        """
        self.db = db
    
    
    # ============================================
    # 모양 템플릿 관련
    # ============================================
    
    def get_shapes(self, active_only: bool = True) -> List[RouteShape]:
        """
        모양 템플릿 목록 조회
        
        Args:
            active_only: 활성화된 템플릿만 조회할지 여부
        
        Returns:
            List[RouteShape]: 모양 템플릿 목록
        """
        query = self.db.query(RouteShape)
        
        if active_only:
            query = query.filter(RouteShape.is_active == True)
        
        return query.all()
    
    
    def get_shape_by_id(self, shape_id: int) -> Optional[RouteShape]:
        """
        ID로 모양 템플릿 조회
        
        Args:
            shape_id: 모양 ID
        
        Returns:
            Optional[RouteShape]: 모양 템플릿 (없으면 None)
        """
        return self.db.query(RouteShape).filter(RouteShape.id == shape_id).first()
    
    
    # ============================================
    # 경로 생성 관련
    # ============================================
    
    def create_route_task(
        self,
        user_id: int,
        shape_id: int,
        start_lat: float,
        start_lng: float,
        target_distance: float,
        options: Dict[str, Any] = None
    ) -> RouteGenerationTask:
        """
        경로 생성 Task 생성
        
        비동기로 경로를 생성하기 위한 Task를 생성합니다.
        
        Args:
            user_id: 사용자 ID
            shape_id: 모양 ID
            start_lat: 시작 위도
            start_lng: 시작 경도
            target_distance: 목표 거리 (km)
            options: 추가 옵션 (급경사 회피, 그늘길 선호 등)
        
        Returns:
            RouteGenerationTask: 생성된 Task
        """
        task_id = str(uuid.uuid4())
        
        task = RouteGenerationTask(
            id=task_id,
            user_id=user_id,
            shape_id=shape_id,
            start_lat=start_lat,
            start_lng=start_lng,
            target_distance=target_distance,
            options=options,
            status="pending"
        )
        
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        
        return task
    
    
    def get_route_task(self, task_id: str, user_id: int) -> Optional[RouteGenerationTask]:
        """
        경로 생성 Task 조회
        
        Args:
            task_id: Task ID
            user_id: 사용자 ID (본인 확인용)
        
        Returns:
            Optional[RouteGenerationTask]: Task (없으면 None)
        """
        return self.db.query(RouteGenerationTask).filter(
            RouteGenerationTask.id == task_id,
            RouteGenerationTask.user_id == user_id
        ).first()
    
    
    def update_task_status(
        self,
        task_id: str,
        status: str,
        route_id: int = None,
        error_message: str = None
    ):
        """
        Task 상태 업데이트
        
        Args:
            task_id: Task ID
            status: 새 상태 (processing/completed/failed)
            route_id: 생성된 경로 ID (완료 시)
            error_message: 에러 메시지 (실패 시)
        """
        task = self.db.query(RouteGenerationTask).filter(
            RouteGenerationTask.id == task_id
        ).first()
        
        if task:
            task.status = status
            
            if status == "processing":
                task.started_at = datetime.utcnow()
            elif status == "completed":
                task.route_id = route_id
                task.completed_at = datetime.utcnow()
            elif status == "failed":
                task.error_message = error_message
            
            self.db.commit()
    
    
    # ============================================
    # 경로 조회 관련
    # ============================================
    
    def get_route(self, route_id: int, user_id: int = None) -> Optional[Route]:
        """
        경로 조회
        
        Args:
            route_id: 경로 ID
            user_id: 사용자 ID (본인 확인용, None이면 확인 안함)
        
        Returns:
            Optional[Route]: 경로 (없으면 None)
        """
        query = self.db.query(Route).filter(Route.id == route_id)
        
        if user_id:
            query = query.filter(Route.user_id == user_id)
        
        return query.first()
    
    
    def get_route_options(self, route_id: int) -> List[RouteOption]:
        """
        경로 옵션 목록 조회
        
        Args:
            route_id: 경로 ID
        
        Returns:
            List[RouteOption]: 옵션 목록
        """
        return self.db.query(RouteOption).filter(
            RouteOption.route_id == route_id
        ).all()
    
    
    def get_route_option(self, option_id: int, route_id: int = None) -> Optional[RouteOption]:
        """
        경로 옵션 상세 조회
        
        Args:
            option_id: 옵션 ID
            route_id: 경로 ID (확인용)
        
        Returns:
            Optional[RouteOption]: 옵션 (없으면 None)
        """
        query = self.db.query(RouteOption).filter(RouteOption.id == option_id)
        
        if route_id:
            query = query.filter(RouteOption.route_id == route_id)
        
        return query.first()
    
    
    # ============================================
    # 경로 저장 관련
    # ============================================
    
    def save_route(
        self,
        user_id: int,
        route_id: int,
        custom_name: str = None,
        note: str = None
    ) -> SavedRoute:
        """
        경로 저장 (북마크)
        
        Args:
            user_id: 사용자 ID
            route_id: 경로 ID
            custom_name: 커스텀 이름
            note: 메모
        
        Returns:
            SavedRoute: 저장된 경로
        
        Raises:
            ValidationException: 이미 저장한 경로인 경우
        """
        # 이미 저장했는지 확인
        existing = self.db.query(SavedRoute).filter(
            SavedRoute.user_id == user_id,
            SavedRoute.route_id == route_id
        ).first()
        
        if existing:
            raise ValidationException(
                message="이미 저장한 경로입니다",
                field="route_id"
            )
        
        saved = SavedRoute(
            user_id=user_id,
            route_id=route_id,
            custom_name=custom_name,
            note=note
        )
        
        self.db.add(saved)
        self.db.commit()
        self.db.refresh(saved)
        
        return saved
    
    
    def unsave_route(self, user_id: int, route_id: int) -> bool:
        """
        경로 저장 취소
        
        Args:
            user_id: 사용자 ID
            route_id: 경로 ID
        
        Returns:
            bool: 삭제 성공 여부
        
        Raises:
            NotFoundException: 저장하지 않은 경로인 경우
        """
        saved = self.db.query(SavedRoute).filter(
            SavedRoute.user_id == user_id,
            SavedRoute.route_id == route_id
        ).first()
        
        if not saved:
            raise NotFoundException(
                resource="SavedRoute",
                resource_id=route_id
            )
        
        self.db.delete(saved)
        self.db.commit()
        
        return True
    
    
    def get_saved_routes(
        self,
        user_id: int,
        page: int = 1,
        limit: int = 20,
        sort: str = "date_desc"
    ) -> tuple[List[SavedRoute], int]:
        """
        저장한 경로 목록 조회
        
        Args:
            user_id: 사용자 ID
            page: 페이지 번호
            limit: 페이지당 항목 수
            sort: 정렬 방식
        
        Returns:
            tuple: (저장된 경로 목록, 전체 개수)
        """
        query = self.db.query(SavedRoute).filter(SavedRoute.user_id == user_id)
        
        # 정렬
        if sort == "date_desc":
            query = query.order_by(SavedRoute.saved_at.desc())
        
        total = query.count()
        
        offset = (page - 1) * limit
        routes = query.offset(offset).limit(limit).all()
        
        return routes, total
    
    
    # ============================================
    # 경로 생성 로직 (TODO: 실제 구현 필요)
    # ============================================
    
    async def generate_route(self, task_id: str):
        """
        실제 경로 생성 로직
        
        [TODO: 실제 구현 필요]
        1. 카카오맵/네이버맵 API를 통한 실제 도로 데이터 조회
        2. 모양 템플릿에 맞는 경로 계산
        3. 안전도 점수 계산 (CCTV, 가로등 위치 기반)
        4. 3가지 옵션 생성 (균형/안전/경치)
        
        Args:
            task_id: Task ID
        """
        try:
            # Task 조회
            task = self.db.query(RouteGenerationTask).filter(
                RouteGenerationTask.id == task_id
            ).first()
            
            if not task:
                return
            
            # 상태 업데이트: processing
            task.status = "processing"
            task.started_at = datetime.utcnow()
            self.db.commit()
            
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
            self.db.add(route)
            self.db.commit()
            
            # 3개 옵션 생성
            for i, opt_type in enumerate(["balanced", "safety", "scenic"]):
                path_data = {"coordinates": []}
                safety_score = 90 - (i * 5)
                if path_data.get("coordinates"):
                    infra = load_cctv_points(DEFAULT_CCTV_CSV) + load_lamp_points(DEFAULT_LAMP_CSV)
                    result = compute_safety_score(path_data["coordinates"], infra)
                    safety_score = int(round(result["score"]))

                option = RouteOption(
                    route_id=route.id,
                    option_type=opt_type,
                    distance=task.target_distance + (i * 0.1),
                    estimated_time=int(task.target_distance * 10),
                    safety_score=safety_score,
                    elevation_gain=50 + (i * 10),
                    path_data=path_data
                )
                self.db.add(option)
            
            # 완료 상태 업데이트
            task.status = "completed"
            task.route_id = route.id
            task.completed_at = datetime.utcnow()
            self.db.commit()
            
        except Exception as e:
            # 실패 상태 업데이트
            task = self.db.query(RouteGenerationTask).filter(
                RouteGenerationTask.id == task_id
            ).first()
            
            if task:
                task.status = "failed"
                task.error_message = str(e)
                self.db.commit()
