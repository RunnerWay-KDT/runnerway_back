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

async def precache_area(lat: float, lon: float, radius: float, delay_ms: int = 100):
    """특정 지역의 도로 노드 고도를 사전 수집하여 캐시함 (API 딜레이 추가)"""
    db = SessionLocal()
    
    print(f"지역 수집 시작: ({lat}, {lon}), 반경 {radius}m")
    print(f"API 호출 간격: {delay_ms}ms (Rate Limit 회피용)\n")
    
    try:
        # 1. 해당 지역의 도로 네트워크 노드 추출
        print("도로 네트워크 분석 중...")
        fetcher = RoadNetworkFetcher()
        G = await asyncio.to_thread(
            fetcher.fetch_pedestrian_network_from_point,
            center_point=(lat, lon),
            distance=radius
        )
        
        nodes = list(G.nodes(data=True))
        print(f"총 {len(nodes):,}개의 도로 지점 발견\n")
        
        # 2. 좌표 리스트 생성
        coordinates = []
        for node, data in nodes:
            coordinates.append((data['y'], data['x']))
        
        # 3. ElevationService로 고도 데이터 수집 (캐시 활용)
        print(f"고도 데이터 수집 시작 (Open-Meteo API)...")
        print(f"NOTE: 캐시 히트된 데이터는 API 호출 안 함\n")
        
        async with ElevationService(db) as service:
            results = await service.get_elevations_batch(coordinates)
        
        print(f"\n수집 완료!")
        print(f"- 요청 좌표: {len(coordinates):,}개")
        print(f"- 수집 성공: {len(results):,}개")
        print(f"- 캐시 히트율: API 로그 참조")
        
    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RunnerWay 고도 데이터 사전 구축 도구 (개선 버전)")
    parser.add_argument("--lat", type=float, default=37.5005, help="중심 위도 (기본: 역삼역)")
    parser.add_argument("--lon", type=float, default=127.0365, help="중심 경도 (기본: 역삼역)")
    parser.add_argument("--radius", type=float, default=5000, help="수집 반경(m) (기본: 5000m = 5km)")
    parser.add_argument("--delay", type=int, default=100, help="API 호출 간격(ms) (기본: 100ms)")
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("강남구 고도 데이터 대량 수집 도구")
    print("=" * 70)
    print(f"중심 좌표: ({args.lat}, {args.lon})")
    print(f"반경: {args.radius/1000:.1f}km")
    print(f"예상 커버 면적: ~{3.14 * (args.radius/1000)**2:.1f} km²")
    print("=" * 70 + "\n")
    
    asyncio.run(precache_area(args.lat, args.lon, args.radius, args.delay))
    
    print("\n" + "=" * 70)
    print("다음 단계: python scripts/check_gangnam_coverage.py 로 커버리지 확인")
    print("=" * 70)
