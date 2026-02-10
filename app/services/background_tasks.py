"""
백그라운드 작업 관리 서비스
경로 생성을 백그라운드에서 실행하고 진행률을 업데이트합니다.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any
from sqlalchemy.orm import Session

from app.models.route import RouteGenerationTask, Route, RouteOption
from app.services.road_network import RoadNetworkFetcher
from app.utils.geometry import has_self_intersection
from app.utils.route_helpers import (
    calculate_turn_count,
    calculate_total_descent,
    calculate_max_grade,
    format_pace_string
)

logger = logging.getLogger(__name__)


def update_task_progress(
    db: Session,
    task_id: str,
    progress: int,
    current_step: str,
    estimated_remaining: int = None
):
    """Task 진행률 업데이트"""
    task = db.query(RouteGenerationTask).filter(
        RouteGenerationTask.id == task_id
    ).first()
    
    if task:
        task.progress = progress
        task.current_step = current_step
        task.status = "processing"  # 진행 중으로 변경
        if estimated_remaining is not None:
            task.estimated_remaining = estimated_remaining
        db.commit()
        logger.info(f"Task {task_id}: {progress}% - {current_step}")


def run_generate_route_background(task_id: str, user_id: str, request_data: Dict[str, Any]):
    """
    백그라운드 작업을 실행하기 위한 동기 래퍼 함수.
    새로운 DB 세션을 생성하고 비동기 함수를 실행합니다.
    """
    from app.db.database import SessionLocal
    
    print(f"🚀 Background Task Wrapper Started for Task {task_id}")
    db = SessionLocal()
    try:
        print(f"🔄 Starting asyncio.run for Task {task_id}")
        asyncio.run(generate_route_background(task_id, user_id, request_data, db))
        print(f"✅ asyncio.run completed for Task {task_id}")
    except Exception as e:
        print(f"❌ Background task execution failed: {e}")
        logger.error(f"Background task execution failed: {e}", exc_info=True)
    finally:
        db.close()
        print(f"🏁 DB Session closed for Task {task_id}")


async def generate_route_background(
    task_id: str,
    user_id: str,
    request_data: Dict[str, Any],
    db: Session
):
    """
    백그라운드에서 경로 생성 실행
    """
    print(f"▶️ generate_route_background started for Task {task_id}")
    try:
        # 0% - 시작
        update_task_progress(db, task_id, 0, "경로 생성 시작 중...", 30)
        
        # 요청 데이터 파싱
        lat = request_data['lat']
        lng = request_data['lng']
        target_time_min = request_data.get('target_time_min')
        target_distance_km = request_data.get('target_distance_km')
        prompt = request_data.get('prompt', '')
        
        # 컨디션 판별
        condition = "normal"
        if prompt:
            p = prompt.lower()
            if "recovery" in p or "회복" in p or "easy" in p:
                condition = "recovery"
            elif "fat" in p or "지방" in p or "burn" in p:
                condition = "fat-burn"
            elif "challenge" in p or "기록" in p or "hard" in p:
                condition = "challenge"
        
        # 페이스 계산 (routes.py와 동일)
        # Recovery: 15분/km, Fat-burn: 10분/km, Challenge: 7분/km
        if condition == "recovery":
            pace_min_per_km = 15.0
        elif condition == "challenge":
            pace_min_per_km = 7.0
        else:
            pace_min_per_km = 10.0
        
        if target_time_min and target_time_min > 0:
            target_dist_km = target_time_min / pace_min_per_km
        else:
            target_dist_km = target_distance_km or 3.0
        
        # 최대 거리 제한 (10km)
        if target_dist_km > 10.0:
            target_dist_km = 10.0
        
        # 10% - 도로 네트워크 가져오기
        update_task_progress(db, task_id, 10, "도로 데이터 가져오는 중...", 25)
        
        # routes.py와 동일한 반경 계산 로직 적용 (2500m 제한)
        radius_meter = (target_dist_km / 2) * 1000 * 0.7
        if radius_meter < 1000: 
            radius_meter = 1000
        if radius_meter > 2500:
            logger.warning(f"Capping radius at 2500m (target: {target_dist_km:.1f}km)")
            radius_meter = 2500
            
        print(f"🛣️ Fetching road network for Task {task_id} (radius: {radius_meter}m)...")
        
        fetcher = RoadNetworkFetcher()
        
        # Blocking Call을 쓰레드풀로 이관하여 이벤트 루프 차단 방지
        G = await asyncio.to_thread(
            fetcher.fetch_pedestrian_network_from_point,
            (lat, lng),
            radius_meter
        )
        print(f"✅ Road network fetched for Task {task_id}")
        
        # 30% - 고도 데이터 가져오기
        update_task_progress(db, task_id, 30, "고도 데이터 가져오는 중...", 20)
        print(f"⛰️ Fetching elevation data for Task {task_id}...")
        
        await fetcher.add_elevation_to_nodes_async(G, db=db)
        
        # CPU 연산이 많은 작업도 쓰레드풀로 이관
        print(f"📐 Calculating grades for Task {task_id}...")
        await asyncio.to_thread(fetcher.calculate_edge_grades_and_weights, G)
        
        # 50% - 경로 생성 (각각 다른 가중치로 3개 직접 생성)
        update_task_progress(db, task_id, 50, "경로 계산 중...", 15)
        print(f"🔄 Generating 3 routes with different weights for Task {task_id}...")
        
        # 3개 경로를 각각 다른 가중치로 생성하여 성격이 다른 경로 제공
        route_configs = [
            {"name": "평지 경로",   "weight": "weight_easy", "tag": None},
            {"name": "균형 경로",   "weight": "length",      "tag": "BEST"},
            {"name": "업다운 경로", "weight": "weight_hard",  "tag": None},
        ]
        
        start_node = fetcher.get_nearest_node(G, (lat, lng))
        generated_routes = []
        
        logger.info(f"Task {task_id}: Generating 3 routes with different weights...")
        
        for i, config in enumerate(route_configs):
            route_data = None
            
            # 최대 2회 시도 (1차 실패 시 재시도 1회)
            for attempt in range(2):
                try:
                    attempt_num = i if attempt == 0 else i + 10
                    
                    full_route = await asyncio.to_thread(
                        fetcher.generate_loop_route,
                        G, start_node, target_dist_km,
                        attempt_number=attempt_num,
                        weight=config["weight"]
                    )
                    
                    if not full_route or len(full_route) < 2:
                        logger.warning(f"Task {task_id}: {config['name']} (attempt {attempt+1}) empty or too short.")
                        continue
                    
                    path_coords = fetcher.path_to_kakao_coordinates(G, full_route)
                    
                    # 자기 교차 검증
                    if has_self_intersection(path_coords):
                        logger.warning(f"Task {task_id}: {config['name']} (attempt {attempt+1}) rejected (self-intersection).")
                        if attempt == 0:
                            continue  # 재시도
                        # 2차 시도도 실패 시 그래도 사용 (fallback)
                    
                    real_distance_km = fetcher.calculate_path_distance(G, full_route) / 1000
                    est_time_min = int(real_distance_km * pace_min_per_km)
                    stats = fetcher.get_elevation_stats(G, full_route)
                    total_elev_change = fetcher.calculate_total_elevation_change(G, full_route)
                    
                    route_data = {
                        'id': i + 1,
                        'name': config['name'],
                        'tag': config['tag'],
                        'route': full_route,
                        'elevation_change': total_elev_change,
                        'distance_km': real_distance_km,
                        'time': est_time_min,
                        'coords': path_coords,
                        'stats': stats,
                        'has_intersection': has_self_intersection(path_coords),
                    }
                    logger.info(f"Task {task_id}: {config['name']} generated ({real_distance_km:.2f}km, elev_change={total_elev_change:.1f}m)")
                    break  # 성공 시 다음 경로로
                    
                except Exception as e:
                    logger.error(f"Task {task_id}: {config['name']} (attempt {attempt+1}) failed: {e}", exc_info=True)
                    continue
            
            if route_data:
                generated_routes.append(route_data)
            
            # 진행률 업데이트 (50-70%)
            progress = 50 + int((i + 1) / 3 * 20)
            update_task_progress(db, task_id, progress, f"경로 계산 중 ({i+1}/3)...", 10)
        
        logger.info(f"Task {task_id}: Total {len(generated_routes)} routes generated.")
        
        if len(generated_routes) < 1:
            logger.error(f"Task {task_id}: No routes generated at all.")
            raise ValueError("유효한 경로를 생성할 수 없습니다 (No viable routes found)")
        
        # 85% - DB 저장 준비
        update_task_progress(db, task_id, 85, "최적 경로 선택 중...", 5)
        
        
        # 90% - DB 저장 (선택적)
        update_task_progress(db, task_id, 90, "결과 저장 중...", 3)
        
        # Route 생성
        route = Route(
            user_id=user_id,
            name=f"{condition} 러닝 경로",
            type="none",
            mode="running",
            start_latitude=lat,
            start_longitude=lng,
            condition=condition,
            status="active"
        )
        db.add(route)
        db.flush()
        
        # RouteOption 저장
        for idx, route_data in enumerate(generated_routes):
            
            option = RouteOption(
                route_id=route.id,
                option_number=idx + 1,
                name=route_data['name'],
                distance=route_data['distance_km'],
                estimated_time=route_data['time'],
                recommended_pace=format_pace_string(pace_min_per_km),
                condition_type=condition,
                difficulty=route_data['name'],
                tag=route_data['tag'],
                coordinates=route_data['coords'],
                safety_score=85,
                total_ascent=route_data['stats']['total_ascent'],
                total_descent=calculate_total_descent(G, route_data['route']),
                total_elevation_change=route_data['elevation_change'],
                average_grade=route_data['stats']['average_grade'],
                max_grade=calculate_max_grade(G, route_data['route']),
                has_self_intersection=route_data.get('has_intersection', False),
                validation_version='v1.0',
                segment_count=len(route_data['coords']) - 1,
                turn_count=calculate_turn_count(route_data['coords'])
            )
            db.add(option)
        
        db.commit()
        
        # 100% - 완료
        task = db.query(RouteGenerationTask).filter(
            RouteGenerationTask.id == task_id
        ).first()
        
        if task:
            task.status = "completed"
            task.progress = 100
            task.current_step = "완료!"
            task.estimated_remaining = 0
            task.route_id = route.id
            task.total_candidates = len(generated_routes)
            task.filtered_by_intersection = 0
            task.completed_at = datetime.utcnow()
            db.commit()
        
        logger.info(f"✅ Task {task_id} completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Task {task_id} failed: {e}", exc_info=True)
        
        # 실패 처리
        task = db.query(RouteGenerationTask).filter(
            RouteGenerationTask.id == task_id
        ).first()
        
        if task:
            task.status = "failed"
            task.error_message = str(e)
            task.completed_at = datetime.utcnow()
            db.commit()
