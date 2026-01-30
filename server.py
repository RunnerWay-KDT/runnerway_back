import os
from dotenv import load_dotenv

load_dotenv()
import uvicorn
import time
import math
import random
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import osmnx as ox
ox.settings.use_cache = True
ox.settings.log_console = False
import networkx as nx
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# CORS 설정 (HTML 파일에서 요청 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------
# Data Models
# ----------------------------

class RouteOption(BaseModel):
    id: int
    distance_km: float
    estimated_time_min: int
    level: str # 'Easy', 'Medium', 'Hard'

class RouteRequest(BaseModel):
    lat: float
    lng: float
    target_distance_km: float = None # Optional, inferred from prompt if missing
    prompt: str = None # User's natural language input

# ----------------------------
# OpenAI Client Setup
# ----------------------------
import openai
openai.api_key = os.getenv("OPENAI_API_KEY")

# ----------------------------
# Constants & Helpers
# ----------------------------
# 러닝 평균 속도: 약 8km/h -> 7.5분/km
def calculate_time(km):
    return int(km * 7.5)

# ----------------------------
# API Endpoints
# ----------------------------

@app.get("/api/v1/routes/options")
async def get_route_options(condition: str = Query(..., description="recovery, fat_burn, or challenge")):
    options = []
    
    if condition == "recovery":
        # 회복 러닝: 짧고 가볍게
        distances = [1.5, 2.5, 3.5]
        levels = ["Easy", "Medium", "Hard"]
    elif condition == "fat_burn":
        # 지방 연소: 적당한 유산소 거리
        distances = [3.0, 5.0, 7.0]
        levels = ["Easy", "Medium", "Hard"]
    elif condition == "challenge":
        # 기록 도전: 다소 긴 거리 (성능상 최대 10km)
        distances = [5.0, 8.0, 10.0]
        levels = ["Easy", "Medium", "Hard"]
    else:
        # Fallback
        distances = [3.0, 5.0, 10.0]
        levels = ["Easy", "Medium", "Hard"]

    for i, dist in enumerate(distances):
        options.append({
            "id": i,
            "distance_km": dist,
            "estimated_time_min": calculate_time(dist),
            "level": levels[i] if i < len(levels) else "Medium"
        })
        
    return options

@app.post("/api/v1/routes/recommend")
async def recommend_route(request: RouteRequest):
    user_location = (request.lat, request.lng)
    
    # 기본값 설정
    target_dist_km = request.target_distance_km
    condition = "fat_burn" # Default
    reason = "Generated based on your request."

    # 0. GPT로 프롬프트 해석 (프롬프트가 있을 경우)
    if request.prompt:
        logger.info(f"Analyzing prompt with GPT: {request.prompt}")
        try:
            completion = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a professional running coach. Extract 'target_distance_km' (float, default 3.0), 'condition' (one of 'recovery', 'fat_burn', 'challenge', default 'fat_burn'), and 'short_cheer_message' (korean) from the user input. Return JSON only."},
                    {"role": "user", "content": request.prompt}
                ],
                response_format={"type": "json_object"}
            )
            import json
            gpt_response = json.loads(completion.choices[0].message.content)
            
            if not target_dist_km: # 요청에 명시된 거리가 없으면 GPT 값 사용
                target_dist_km = float(gpt_response.get("target_distance_km", 3.0))
            
            condition = gpt_response.get("condition", "fat_burn")
            reason = gpt_response.get("short_cheer_message", "Have a great run!")
            
            logger.info(f"GPT Parsed: Distance={target_dist_km}, Condition={condition}")
            
        except Exception as e:
            logger.error(f"GPT Error: {e}")
            if not target_dist_km: target_dist_km = 3.0 # Fallback
            reason = "GPT analysis failed, using default settings."

    if not target_dist_km:
        target_dist_km = 3.0

    logger.info(f"Processing request: {user_location}, distance: {target_dist_km}km")

    try:
        # 1. 그래프 다운로드 범위 설정
        # 목표 거리의 절반만큼 갔다가 돌아와야 함.
        # 도로의 굴곡을 고려하여 직선 거리보다 조금 더 넓게(1.2배) 잡지 않고,
        # 딱 필요한 만큼만 받아서 성능 최적화. (반지름 = 목표거리/2 * 0.7 정도가 적당할 수 있으나 여유있게)
        # 너무 크면 다운로드 오래 걸림.
        radius_meter = (target_dist_km / 2) * 1000 * 0.8  # 직선 왕복보다는 도로가 꼬불꼬불하므로 조금 덜 잡아도 됨
        if radius_meter < 500: radius_meter = 500 # 최소 반경
        
        logger.info(f"Downloading graph with radius {radius_meter}m...")
        start_time = time.time()
        
        # network_type='walk'가 러닝에 적합
        G = ox.graph_from_point(user_location, dist=radius_meter, network_type='walk')
        logger.info(f"Graph downloaded in {time.time() - start_time:.2f}s")
        
        # 출발지 노드 찾기
        orig_node = ox.distance.nearest_nodes(G, user_location[1], user_location[0])

        # 2. 반환점(Turnaround Point) 찾기
        # 출발지에서 직선 거리로 (target_dist_km / 2) 미터 정도 떨어진 노드들 중 하나를 선택
        possible_nodes = []
        target_radius_m = (target_dist_km * 1000) / 2
        
        # G.nodes는 딕셔너리 형태
        for node, data in G.nodes(data=True):
            # 출발지와의 거리 계산 (Great Circle)
            dist_from_start = ox.distance.great_circle(user_location[0], user_location[1], data['y'], data['x'])
            
            # 목표 반경의 오차범위 15% 내에 있는 노드 후보군
            if target_radius_m * 0.85 <= dist_from_start <= target_radius_m * 1.15:
                possible_nodes.append(node)
                
        if not possible_nodes:
            logger.warning("No nodes found in exact target range. Widening search...")
            # 없으면 그냥 가장 멀리 있는 노드 선택 (반경 내)
            max_dist = 0
            best_node = None
            for node, data in G.nodes(data=True):
                d = ox.distance.great_circle(user_location[0], user_location[1], data['y'], data['x'])
                if d > max_dist:
                    max_dist = d
                    best_node = node
            dest_node = best_node
        else:
            # 후보군 중 랜덤 선택 (매번 다른 경로 추천 가능)
            dest_node = random.choice(possible_nodes)

        # 3. 경로 계산 (왕복 Loop)
        logger.info("Calculating loop route...")
        
        # 가는 길 (최단 경로)
        try:
            route_to = nx.shortest_path(G, orig_node, dest_node, weight='length')
        except nx.NetworkXNoPath:
             raise HTTPException(status_code=404, detail="Cannot find a path to the destination.")

        # 오는 길 (가는 길 피해서)
        # 엣지 가중치 페널티 부여
        for u, v in zip(route_to[:-1], route_to[1:]):
            if G.has_edge(u, v):
                for key in G[u][v]:
                    G[u][v][key]['length'] *= 1000 
            if G.has_edge(v, u): # 양방향 고려
                for key in G[v][u]:
                    G[v][u][key]['length'] *= 1000

        try:
            route_from = nx.shortest_path(G, dest_node, orig_node, weight='length')
        except nx.NetworkXNoPath:
             logger.warning("No alternative return path found. Backtracking.")
             route_from = route_to[::-1]
        
        # 전체 경로 합치기
        full_route = route_to + route_from[1:]
        
        # 좌표 변환
        route_coords = []
        for node in full_route:
            n = G.nodes[node]
            route_coords.append({"lat": n['y'], "lng": n['x']})
            
        logger.info(f"Route generated. Nodes: {len(full_route)}")

        return {
            "destination": f"Custom {target_dist_km}km Loop",
            "reason": reason,
            "path": route_coords
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
