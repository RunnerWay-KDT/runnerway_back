import sys
import os
from sqlalchemy import func, and_

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import SessionLocal
from app.models.elevation import ElevationCache

# 강남구 경계
SEOUL_BOUNDS = {
    'min_lat': 37.45,
    'max_lat': 37.54,
    'min_lon': 127.01,
    'max_lon': 127.14
}

def check_gangnam_coverage():
    db = SessionLocal()
    try:
        # 강남구 범위 내의 데이터 개수 조회
        count = db.query(func.count(ElevationCache.id)).filter(
            and_(
                ElevationCache.latitude >= SEOUL_BOUNDS['min_lat'],
                ElevationCache.latitude <= SEOUL_BOUNDS['max_lat'],
                ElevationCache.longitude >= SEOUL_BOUNDS['min_lon'],
                ElevationCache.longitude <= SEOUL_BOUNDS['max_lon']
            )
        ).scalar()
        
        print(f"📊 강남구 지역 ({SEOUL_BOUNDS}) 저장된 고도 데이터 개수: {count:,}")
        
        # 예상 개수 계산 (50m 간격)
        lat_diff = SEOUL_BOUNDS['max_lat'] - SEOUL_BOUNDS['min_lat']
        lon_diff = SEOUL_BOUNDS['max_lon'] - SEOUL_BOUNDS['min_lon']
        grid_step = 0.00045 # 약 50m
        
        expected_rows = int(lat_diff / grid_step)
        expected_cols = int(lon_diff / grid_step)
        expected_total = expected_rows * expected_cols
        
        print(f"📉 예상 그리드 포인트 수 (50m 간격): 약 {expected_total:,}")
        
        if expected_total > 0:
            percentage = (count / expected_total) * 100
            print(f"✅ 진행률: {percentage:.2f}%")
        
    except Exception as e:
        print(f"[ERROR] 조회 실패: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_gangnam_coverage()
