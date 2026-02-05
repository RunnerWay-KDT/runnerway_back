"""
역삼역 주변 경로 생성 테스트

현재 캐시된 고도 데이터로 실제 경로를 생성해봅니다.
"""

import sys
import os
import asyncio

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import SessionLocal
from app.services.road_network import RoadNetworkFetcher
from app.services.elevation_service import ElevationService


async def test_route_generation():
    """역삼역 주변 경로 생성 테스트"""
    
    # 역삼역 좌표
    yeoksam = {
        'lat': 37.5005,
        'lon': 127.0365,
        'name': '역삼역'
    }
    
    print("=" * 70)
    print(f"{yeoksam['name']} 경로 생성 테스트")
    print("=" * 70)
    print(f"중심 좌표: ({yeoksam['lat']}, {yeoksam['lon']})")
    print(f"반경: 2km")
    print("=" * 70 + "\n")
    
    db = SessionLocal()
    
    try:
        # 1. 도로 네트워크 가져오기
        print("1. 도로 네트워크 분석 중...")
        fetcher = RoadNetworkFetcher()
        
        G = await asyncio.to_thread(
            fetcher.fetch_pedestrian_network_from_point,
            center_point=(yeoksam['lat'], yeoksam['lon']),
            distance=2000
        )
        
        print(f"   노드: {len(G.nodes):,}개")
        print(f"   간선: {len(G.edges):,}개\n")
        
        # 2. 고도 데이터 조회
        print("2. 고도 데이터 조회 중...")
        
        coordinates = [(data['y'], data['x']) for node, data in G.nodes(data=True)]
        
        async with ElevationService(db) as elevation_service:
            elevations = await elevation_service.get_elevations_batch(coordinates)
        
        print(f"   조회 성공: {len(elevations):,}/{len(coordinates):,}개")
        
        if elevations:
            elev_values = list(elevations.values())
            print(f"   고도 범위: {min(elev_values):.1f}m ~ {max(elev_values):.1f}m")
            print(f"   평균 고도: {sum(elev_values)/len(elev_values):.1f}m\n")
        
        # 3. 경로 생성 시뮬레이션
        print("3. 경로 생성 시뮬레이션...")
        
        # 시작점에서 2km 떨어진 목적지 찾기
        import random
        nodes = list(G.nodes())
        start_node = random.choice(nodes)
        
        # 거리 계산 (간단한 유클리드 거리)
        def distance(n1, n2):
            lat1, lon1 = G.nodes[n1]['y'], G.nodes[n1]['x']
            lat2, lon2 = G.nodes[n2]['y'], G.nodes[n2]['x']
            return ((lat1-lat2)**2 + (lon1-lon2)**2)**0.5
        
        # 시작점에서 적당히 떨어진 노드 찾기
        candidates = [
            n for n in nodes 
            if 0.015 < distance(start_node, n) < 0.025  # 약 1.5~2.5km
        ]
        
        if candidates:
            end_node = random.choice(candidates)
            
            start_lat, start_lon = G.nodes[start_node]['y'], G.nodes[start_node]['x']
            end_lat, end_lon = G.nodes[end_node]['y'], G.nodes[end_node]['x']
            
            print(f"   시작: ({start_lat:.4f}, {start_lon:.4f})")
            print(f"   종료: ({end_lat:.4f}, {end_lon:.4f})")
            
            # 경로 찾기 (최단 경로)
            import networkx as nx
            try:
                path = nx.shortest_path(G, start_node, end_node, weight='length')
                
                # 경로 거리 계산
                path_length = sum(
                    G[path[i]][path[i+1]][0]['length']
                    for i in range(len(path)-1)
                )
                
                print(f"   경로 노드: {len(path)}개")
                print(f"   경로 거리: {path_length:.0f}m")
                
                # 경로 상 고도 변화
                path_coords = [(G.nodes[n]['y'], G.nodes[n]['x']) for n in path]
                path_elevations = [elevations.get(coord, 0) for coord in path_coords]
                
                valid_elevations = [e for e in path_elevations if e > 0]
                if valid_elevations:
                    total_ascent = sum(
                        max(0, path_elevations[i+1] - path_elevations[i])
                        for i in range(len(path_elevations)-1)
                        if path_elevations[i] > 0 and path_elevations[i+1] > 0
                    )
                    
                    total_descent = sum(
                        max(0, path_elevations[i] - path_elevations[i+1])
                        for i in range(len(path_elevations)-1)
                        if path_elevations[i] > 0 and path_elevations[i+1] > 0
                    )
                    
                    print(f"   누적 오르막: {total_ascent:.1f}m")
                    print(f"   누적 내리막: {total_descent:.1f}m")
                    print(f"   고도 범위: {min(valid_elevations):.1f}m ~ {max(valid_elevations):.1f}m")
                
                print("\n✅ 경로 생성 성공!")
                
            except nx.NetworkXNoPath:
                print("   ⚠️ 경로를 찾을 수 없습니다.")
        else:
            print("   ⚠️ 적절한 목적지를 찾을 수 없습니다.")
        
        print("\n" + "=" * 70)
        print("테스트 완료!")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(test_route_generation())
