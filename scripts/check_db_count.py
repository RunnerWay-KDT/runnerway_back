import sys
import os

# 프로젝트 루트를 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import SessionLocal
from app.models.elevation import ElevationCache
from sqlalchemy import func

def check_count():
    db = SessionLocal()
    try:
        count = db.query(func.count(ElevationCache.id)).scalar()
        print(f"[OK] Total cached elevation records: {count}")
        
        # 최근 저장된 데이터 5개 확인
        print("\n[INFO] Recent records (Top 5):")
        recent = db.query(ElevationCache).order_by(ElevationCache.id.desc()).limit(5).all()
        for r in recent:
            print(f"- ID: {r.id}, Coord: ({r.latitude}, {r.longitude}), Elev: {r.elevation}m")
            
    except Exception as e:
        print(f"[ERROR] Failed to query: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_count()
