import sys
import os
import asyncio
import argparse

# 프로젝트 루트를 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import SessionLocal
from app.services.elevation_service import ElevationService
from app.services.road_network import RoadNetworkFetcher
from app.config import settings
import osmnx as ox

async def precache_area(lat: float, lon: float, radius: float):
    """특정 지역의 도로 노드 고도를 사전 수집하여 캐시함"""
    db = SessionLocal()
    api_key = settings.VWORLD_API_KEY
    
    if not api_key:
        print("❌ VWORLD_API_KEY가 설정되지 않았습니다.")
        return

    service = ElevationService(db, api_key)
    fetcher = RoadNetworkFetcher()

    print(f"📍 지역 수집 시작: ({lat}, {lon}), 반경 {radius}m")
    
    try:
        # 1. 해당 지역의 도로 네트워크 노드 추출
        print("🔍 도로 네트워크 분석 중...")
        G = await asyncio.to_thread(
            fetcher.fetch_pedestrian_network_from_point,
            center_point=(lat, lon),
            distance=radius
        )
        
        nodes = list(G.nodes(data=True))
        print(f"✅ 총 {len(nodes)}개의 도로 지점 발견")
        
        # 2. 좌표 리스트 생성
        coordinates = []
        for node, data in nodes:
            coordinates.append((data['y'], data['x']))
            
        # 3. 배치 조회 및 저장 (ElevationService가 자동으로 DB 저장함)
        print(f"🚀 고도 데이터 수집 및 DB 저장 시작 (VWorld API 호출)...")
        results = await service.get_elevations_batch(coordinates)
        
        print(f"\n✨ 수집 완료!")
        print(f"- 수집된 지점: {len(results)}개")
        print(f"- 서울 범위 내 저장된 지점: {len([c for c in coordinates if service.is_in_seoul(*c)])}개")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RunnerWay 고도 데이터 사전 구축 도구")
    parser.add_argument("--lat", type=float, default=37.5005, help="중심 위도 (기본: 역삼역)")
    parser.add_argument("--lon", type=float, default=127.0365, help="중심 경도 (기본: 역삼역)")
    parser.add_argument("--radius", type=float, default=2000, help="수집 반경(m) (기본: 2000m)")
    
    args = parser.parse_args()
    
    asyncio.run(precache_area(args.lat, args.lon, args.radius))
