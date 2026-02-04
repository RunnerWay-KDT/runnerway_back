#!/usr/bin/env python
"""
서울 전체 고도 데이터 Pre-caching 스크립트

서울 전역을 그리드로 나누어 체계적으로 고도 데이터를 수집하여 DB에 저장합니다.
"""

import asyncio
import sys
import os
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.db.database import SessionLocal
from app.services.elevation_service import ElevationService
from app.config import settings
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# 서울 전체 경계 (대략적)
SEOUL_BOUNDS = {
    'min_lat': 37.41,   # 남쪽 (관악산/청계산 인근)
    'max_lat': 37.71,   # 북쪽 (북한산/도봉산 인근)
    'min_lon': 126.76,  # 서쪽 (강서구/김포공항)
    'max_lon': 127.19   # 동쪽 (강동구/상일동)
}

# 그리드 간격 (0.00045° ≈ 50m)
GRID_STEP = 0.00045


def generate_seoul_grid():
    """
    서울 전역을 그리드로 나누어 좌표 리스트 생성
    
    Returns:
        List[Tuple[float, float]]: (latitude, longitude) 리스트
    """
    coordinates = []
    
    lat = SEOUL_BOUNDS['min_lat']
    while lat <= SEOUL_BOUNDS['max_lat']:
        lon = SEOUL_BOUNDS['min_lon']
        while lon <= SEOUL_BOUNDS['max_lon']:
            # 5자리 반올림 (더 정밀하게)
            lat_rounded = round(lat, 5)
            lon_rounded = round(lon, 5)
            coordinates.append((lat_rounded, lon_rounded))
            lon += GRID_STEP
        lat += GRID_STEP
    
    logger.info(f"Generated {len(coordinates):,} grid points for Seoul (Step: 50m)")
    return coordinates


async def precache_batch(coordinates, batch_size=500):
    """
    좌표 배치를 캐싱
    
    Args:
        coordinates: 좌표 리스트
        batch_size: 배치 크기 (한 번에 처리할 좌표 수)
    """
    db = SessionLocal()
    
    try:
        async with ElevationService(db) as elevation_service:
            total = len(coordinates)
            processed = 0
            
            # 배치 단위로 처리
            for i in range(0, total, batch_size):
                batch = coordinates[i:i + batch_size]
                
                logger.info(f"Processing batch {i // batch_size + 1}/{(total + batch_size - 1) // batch_size} ({processed}/{total} completed)")
                
                # 배치 조회 (자동으로 캐싱됨)
                # 예외 처리 없이 호출하여 에러 발생 시 즉시 중단
                result = await elevation_service.get_elevations_batch(batch)
                
                processed += len(batch)
                
                # 진행률 표시
                progress = (processed / total) * 100
                logger.info(f"Progress: {progress:.1f}% ({processed:,}/{total:,})")
                
                # API 부하 조절을 위한 짧은 대기 (Open-Meteo는 관대하지만 예의상)
                await asyncio.sleep(0.2)
            
            logger.info(f"Pre-caching completed! Total: {processed:,} coordinates")
            
    except Exception as e:
        logger.error(f"Pre-caching failed: {e}")
        raise
    finally:
        db.close()


async def main():
    """메인 실행 함수"""
    logger.info("=" * 60)
    logger.info("서울 전체 고도 데이터 Pre-caching 시작")
    logger.info("=" * 60)
    
    # 1. 그리드 생성
    logger.info("Step 1: Generating Seoul grid...")
    coordinates = generate_seoul_grid()
    
    # 2. 예상 시간 계산
    estimated_time_minutes = len(coordinates) / 500 * 5 / 60  # 500개당 5초 가정
    logger.info(f"Estimated time: {estimated_time_minutes:.1f} minutes")
    
    # 3. Pre-caching 실행
    logger.info("Step 2: Starting pre-caching...")
    await precache_batch(coordinates, batch_size=500)
    
    logger.info("=" * 60)
    logger.info("All done!")
    logger.info("=" * 60)


if __name__ == "__main__":
    # 실행 전 확인
    print("=" * 60)
    print("서울 전체 고도 데이터 Pre-caching")
    print("=" * 60)
    print(f"대상 지역: 서울 전역 ({SEOUL_BOUNDS})")
    print(f"그리드 간격: {GRID_STEP} (약 11m)")
    print()
    
    # response = input("계속하시겠습니까? (y/n): ")
    # if response.lower() != 'y':
    #     print("취소되었습니다.")
    #     sys.exit(0)
    print("사용자 요청에 의해 즉시 시작합니다...")
    
    # 비동기 실행
    asyncio.run(main())
