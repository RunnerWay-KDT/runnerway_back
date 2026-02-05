import requests
import json

# API 엔드포인트
url = "http://localhost:8000/api/v1/routes/recommend"

# 요청 데이터
data = {
    "lat": 37.5004,
    "lng": 127.0364,
    "target_distance_km": 3.0,
    "prompt": "목적: 지방 연소, 거리: 3km"
}

print("=" * 70)
print("역삼역 경로 추천 API 테스트")
print("=" * 70)
print(f"위치: 역삼역 ({data['lat']}, {data['lng']})")
print(f"목표: {data['prompt']}")
print("=" * 70)

try:
    # API 호출
    response = requests.post(url, json=data, timeout=60)
    
    if response.status_code == 200:
        result = response.json()
        
        print("\n[SUCCESS] API 호출 성공!\n")
        print(f"추천 경로 수: {len(result.get('candidates', []))}개\n")
        
        for route in result.get('candidates', []):
            print("-" * 70)
            print(f"[ROUTE] {route['name']}")
            print(f"   거리: {route['distance']}")
            print(f"   시간: {route['time']}분")
            print(f"   사유: {route['reason']}")
            
            # 고도 통계
            if 'elevation_stats' in route:
                stats = route['elevation_stats']
                print(f"   [고도 통계]")
                print(f"      - 최저: {stats.get('min_elevation', 'N/A')}m")
                print(f"      - 최고: {stats.get('max_elevation', 'N/A')}m")
                print(f"      - 총 상승: {stats.get('total_ascent', 'N/A')}m")
                print(f"      - 평균 경사: {stats.get('average_grade', 'N/A')}%")
        
        print("=" * 70)
        
    else:
        print(f"[ERROR] API 에러: {response.status_code}")
        print(response.text)

except requests.exceptions.ConnectionError:
    print("[ERROR] 서버가 실행 중이지 않습니다!")
    print("서버를 먼저 실행하세요: uvicorn app.main:app --reload")
except Exception as e:
    print(f"[ERROR] 오류 발생: {e}")
