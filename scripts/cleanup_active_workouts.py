"""
활성 상태의 운동 세션을 정리하는 스크립트
개발 중 비정상 종료된 운동 세션을 정리할 때 사용
"""
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.security import get_password_hash
from app.models.user import User
from app.models.workout import Workout
from app.db.database import get_db_url
from datetime import datetime

def cleanup_active_workouts():
    """활성 상태의 모든 운동을 'completed'로 변경"""
    
    # DB 연결
    engine = create_engine(get_db_url())
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        # 활성 상태의 모든 운동 조회
        active_workouts = db.query(Workout).filter(
            Workout.status.in_(["active", "paused"]),
            Workout.deleted_at.is_(None)
        ).all()
        
        if not active_workouts:
            print("✅ 활성 상태의 운동이 없습니다.")
            return
        
        print(f"🔍 발견된 활성 운동: {len(active_workouts)}개")
        
        for workout in active_workouts:
            print(f"  - ID: {workout.id}")
            print(f"    사용자: {workout.user_id}")
            print(f"    경로: {workout.route_name}")
            print(f"    상태: {workout.status}")
            print(f"    시작: {workout.started_at}")
        
        response = input("\n이 운동들을 'completed' 상태로 변경하시겠습니까? (y/n): ")
        
        if response.lower() != 'y':
            print("❌ 취소되었습니다.")
            return
        
        # 모든 활성 운동을 completed로 변경
        for workout in active_workouts:
            workout.status = "completed"
            if not workout.completed_at:
                workout.completed_at = datetime.utcnow()
            if not workout.distance:
                workout.distance = 0.0
            if not workout.duration:
                workout.duration = 0
            if not workout.avg_pace:
                workout.avg_pace = "0'00\""
            if not workout.calories:
                workout.calories = 0
        
        db.commit()
        print(f"✅ {len(active_workouts)}개의 운동이 정리되었습니다.")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    cleanup_active_workouts()
