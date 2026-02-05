"""
강남구 고도 캐시 커버리지 확인 스크립트

현재 DB에 저장된 고도 데이터를 분석하고,
강남구 전체를 커버하기 위해 얼마나 더 필요한지 계산합니다.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import SessionLocal
from app.models.elevation import ElevationCache
from sqlalchemy import func


def check_gangnam_coverage():
    """강남구 고도 데이터 커버리지 확인"""
    
    db = SessionLocal()
    
    try:
        # 강남구 경계 (여유있게)
        GANGNAM_BOUNDS = {
            'lat_min': 37.47,   # 남쪽 (수서동)
            'lat_max': 37.54,   # 북쪽 (삼성동)
            'lon_min': 127.02,  # 서쪽 (역삼동)
            'lon_max': 127.09   # 동쪽 (대치동)
        }
        
        print("=" * 60)
        print("강남구 고도 데이터 커버리지 분석")
        print("=" * 60)
        
        # 1. 전체 캐시 데이터 개수
        total_count = db.query(func.count(ElevationCache.id)).scalar()
        print(f"\n전체 DB 캐시 데이터: {total_count:,}개")
        
        # 2. 강남구 범위 내 데이터 개수
        gangnam_count = db.query(func.count(ElevationCache.id)).filter(
            ElevationCache.latitude.between(
                GANGNAM_BOUNDS['lat_min'],
                GANGNAM_BOUNDS['lat_max']
            ),
            ElevationCache.longitude.between(
                GANGNAM_BOUNDS['lon_min'],
                GANGNAM_BOUNDS['lon_max']
            )
        ).scalar()
        
        print(f"강남구 범위 내 데이터: {gangnam_count:,}개")
        
        # 3. 강남구 면적 계산
        lat_diff = GANGNAM_BOUNDS['lat_max'] - GANGNAM_BOUNDS['lat_min']
        lon_diff = GANGNAM_BOUNDS['lon_max'] - GANGNAM_BOUNDS['lon_min']
        
        # 1도 ≈ 111km, 서울 위도에서 경도 1도 ≈ 88km
        area_km2 = (lat_diff * 111) * (lon_diff * 88)
        
        print(f"\n강남구 분석 영역: 약 {area_km2:.1f} km²")
        
        # 4. 도로 네트워크 기준 예상 노드 수
        # 보통 1km² 당 walk 네트워크는 약 500~1000개 노드
        estimated_nodes_min = int(area_km2 * 500)
        estimated_nodes_max = int(area_km2 * 1000)
        
        print(f"예상 필요 데이터: {estimated_nodes_min:,} ~ {estimated_nodes_max:,}개")
        
        # 5. 커버리지 비율
        if estimated_nodes_min > 0:
            coverage_min = (gangnam_count / estimated_nodes_min) * 100
            coverage_max = (gangnam_count / estimated_nodes_max) * 100
            
            print(f"\n현재 커버리지: {coverage_min:.1f}% ~ {coverage_max:.1f}%")
            
            # 부족한 데이터
            missing_min = max(0, estimated_nodes_min - gangnam_count)
            missing_max = max(0, estimated_nodes_max - gangnam_count)
            
            print(f"추가 필요 데이터: {missing_min:,} ~ {missing_max:,}개")
        
        # 6. 샘플 데이터 조회 (최근 10개)
        recent_data = db.query(ElevationCache).filter(
            ElevationCache.latitude.between(
                GANGNAM_BOUNDS['lat_min'],
                GANGNAM_BOUNDS['lat_max']
            ),
            ElevationCache.longitude.between(
                GANGNAM_BOUNDS['lon_min'],
                GANGNAM_BOUNDS['lon_max']
            )
        ).order_by(ElevationCache.created_at.desc()).limit(10).all()
        
        if recent_data:
            print(f"\n최근 캐시 데이터 샘플 (10개):")
            print(f"{'위도':>10} {'경도':>10} {'고도(m)':>10} {'히트수':>10}")
            print("-" * 45)
            for item in recent_data:
                print(f"{float(item.latitude):10.5f} {float(item.longitude):10.5f} "
                      f"{float(item.elevation):10.1f} {item.hit_count:10d}")
        
        # 7. 권장사항
        print("\n" + "=" * 60)
        print("권장 작업")
        print("=" * 60)
        
        if gangnam_count < estimated_nodes_min:
            print(f"강남구 전체를 커버하기 위해 추가 캐싱이 필요합니다.")
            print(f"\n실행 명령:")
            print(f"  # 강남역 중심 3km 반경")
            print(f"  python scripts/precache_elevation.py --lat 37.4979 --lon 127.0276 --radius 3000")
            print(f"\n  # 삼성역 중심 3km 반경")
            print(f"  python scripts/precache_elevation.py --lat 37.5007 --lon 127.0364 --radius 3000")
            print(f"\n  # 선릉역 중심 3km 반경")
            print(f"  python scripts/precache_elevation.py --lat 37.5172 --lon 127.0473 --radius 3000")
        else:
            print(f"강남구 데이터가 충분합니다!")
        
        print("=" * 60)
        
    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    check_gangnam_coverage()
