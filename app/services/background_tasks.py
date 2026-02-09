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
        
        # 페이스 계산
        if condition == "recovery":
            pace_min_per_km = 10.0
        elif condition == "challenge":
            pace_min_per_km = 7.0
        else:
            pace_min_per_km = 9.0
        
        if target_time_min and target_time_min > 0:
            target_dist_km = target_time_min / pace_min_per_km
        else:
            target_dist_km = target_distance_km or 3.0
        
        
        # 10% - 도로 네트워크 가져오기
        update_task_progress(db, task_id, 10, "도로 데이터 가져오는 중...", 25)
        
        # routes.py와 동일한 반경 계산 로직 적용 (3000m 제한 해제)
        radius_meter = (target_dist_km / 2) * 1000 * 1.1
        if radius_meter < 1500: 
            radius_meter = 1500
        if radius_meter > 8000:
            logger.warning(f"Capping radius at 8000m (target: {target_dist_km:.1f}km)")
            radius_meter = 8000
            
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
        
        # 50% - 경로 생성
        update_task_progress(db, task_id, 50, "경로 계산 중...", 15)
        print(f"🔄 Generating candidates for Task {task_id}...")
        
        candidate_routes = []
        num_candidates = 6
        
        logger.info(f"Task {task_id}: Generating {num_candidates} candidates...")
        
        for i in range(num_candidates):
            try:
                start_node = fetcher.get_nearest_node(G, (lat, lng))
                
                # 난이도에 따른 가중치 키 선택
                weight_key = 'length'
                if condition == "recovery":
                    weight_key = 'weight_easy'
                elif condition == "challenge":
                    weight_key = 'weight_hard'
                
                # 경로 탐색 알고리즘(Dijkstra/A*) 역시 CPU 집약적이므로 비동기 처리
                full_route = await asyncio.to_thread(
                    fetcher.generate_loop_route,
                    G, start_node, target_dist_km,
                    attempt_number=i,
                    weight=weight_key
                )
                
                if not full_route or len(full_route) < 2:
                    logger.warning(f"Task {task_id}: Candidate {i+1} empty or too short.")
                    continue
                
                real_distance_km = fetcher.calculate_path_distance(G, full_route) / 1000
                est_time_min = int(real_distance_km * pace_min_per_km)
                path_coords = fetcher.path_to_kakao_coordinates(G, full_route)
                stats = fetcher.get_elevation_stats(G, full_route)
                total_elev_change = fetcher.calculate_total_elevation_change(G, full_route)
                
                candidate_routes.append({
                    'id': i + 1,
                    'route': full_route,
                    'elevation_change': total_elev_change,
                    'distance_km': real_distance_km,
                    'time': est_time_min,
                    'coords': path_coords,
                    'stats': stats
                })
                logger.info(f"Task {task_id}: Candidate {i+1} generated ({real_distance_km:.2f}km)")
                
                # 진행률 업데이트 (50-70%)
                progress = 50 + int((i + 1) / num_candidates * 20)
                update_task_progress(db, task_id, progress, f"경로 계산 중 ({i+1}/{num_candidates})...", 10)
                
            except Exception as e:
                logger.error(f"Candidate {i+1} failed: {e}", exc_info=True)
                continue
        
        logger.info(f"Task {task_id}: Total {len(candidate_routes)} candidates generated.")

        # 70% - 자기 교차 필터링
        update_task_progress(db, task_id, 70, "경로 검증 중...", 8)
        
        valid_candidates = []
        rejected_count = 0
        
        for route_data in candidate_routes:
            if not has_self_intersection(route_data['coords']):
                valid_candidates.append(route_data)
            else:
                logger.warning(f"Task {task_id}: Candidate {route_data['id']} rejected (self-intersection).")
                rejected_count += 1
        
        if len(valid_candidates) < 1:
            if len(candidate_routes) > 0:
                 # 교차 검증 실패 시, fallback으로 가장 긴 경로 하나라도 선택
                 logger.warning(f"Task {task_id}: All candidates rejected by intersection check. Using the first candidate as fallback.")
                 valid_candidates.append(candidate_routes[0])
            else:
                 logger.error(f"Task {task_id}: No candidates generated at all.")
                 raise ValueError("유효한 경로를 생성할 수 없습니다 (No viable routes found)")
        
        # 85% - 경로 정렬 및 선택
        update_task_progress(db, task_id, 85, "최적 경로 선택 중...", 5)
        
        valid_candidates.sort(key=lambda x: x['elevation_change'])
        
        selected_count = min(3, len(valid_candidates))
        if selected_count == 3:
            selected_indices = [0, len(valid_candidates) // 2, len(valid_candidates) - 1]
        elif selected_count == 2:
            selected_indices = [0, len(valid_candidates) - 1]
        else:
            selected_indices = [0]
        
        route_names = ["평지 경로", "균형 경로", "업다운 경로"]
        
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
        for idx_position, route_idx in enumerate(selected_indices):
            route_data = valid_candidates[route_idx]
            
            option = RouteOption(
                route_id=route.id,
                option_number=idx_position + 1,
                name=route_names[idx_position],
                distance=route_data['distance_km'],
                estimated_time=route_data['time'],
                recommended_pace=format_pace_string(pace_min_per_km),
                condition_type=condition,
                difficulty=route_names[idx_position],
                tag='BEST' if idx_position == 1 else None,
                coordinates=route_data['coords'],
                safety_score=85,
                total_ascent=route_data['stats']['total_ascent'],
                total_descent=calculate_total_descent(G, route_data['route']),
                total_elevation_change=route_data['elevation_change'],
                average_grade=route_data['stats']['average_grade'],
                max_grade=calculate_max_grade(G, route_data['route']),
                has_self_intersection=False,
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
            task.total_candidates = len(candidate_routes)
            task.filtered_by_intersection = rejected_count
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
