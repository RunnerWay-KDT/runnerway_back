from typing import List, Tuple, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.models.elevation import ElevationCache
import httpx
import logging
import asyncio

logger = logging.getLogger(__name__)

class ElevationService:
    """고도 데이터 조회 서비스 (캐시 우선)"""
    
    # 서울시 경계 (안전 여유 포함)
    SEOUL_BOUNDS = {
        'lat_min': 37.4,
        'lat_max': 37.7,
        'lon_min': 126.7,
        'lon_max': 127.2
    }
    
    # 캐시 검색 허용 오차 (약 11m)
    # DECIMAL(9,7) 정밀도이므로 소수점 4자리까지 비교
    CACHE_TOLERANCE = 0.0001
    
    def __init__(self, db: Session, api_key: str):
        self.db = db
        self.api_key = api_key
        self._client = None
    
    async def get_client(self) -> httpx.AsyncClient:
        """AsyncClient 싱글톤/풀링 처리"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(10.0, connect=5.0),
                limits=httpx.Limits(max_keepalive_connections=20, max_connections=50)
            )
        return self._client
    
    def is_in_seoul(self, lat: float, lon: float) -> bool:
        """서울시 범위 내 좌표인지 확인"""
        return (
            self.SEOUL_BOUNDS['lat_min'] <= lat <= self.SEOUL_BOUNDS['lat_max'] and
            self.SEOUL_BOUNDS['lon_min'] <= lon <= self.SEOUL_BOUNDS['lon_max']
        )
    
    async def get_elevation(self, lat: float, lon: float) -> float:
        """단일 좌표 고도 조회"""
        
        # 서울시 범위 체크
        if not self.is_in_seoul(lat, lon):
            logger.warning(f"Coordinate out of Seoul bounds: ({lat}, {lon})")
            return await self._fetch_from_api(lat, lon)
        
        # 1. 캐시 조회
        cached = self._get_from_cache(lat, lon)
        if cached:
            cached.hit_count += 1
            self.db.commit()
            return float(cached.elevation)
        
        # 2. API 호출
        elevation = await self._fetch_from_api(lat, lon)
        
        # 3. 캐시 저장
        self._save_to_cache(lat, lon, elevation)
        
        return elevation
    
    async def get_elevations_batch(
        self,
        coordinates: List[Tuple[float, float]]
    ) -> Dict[Tuple[float, float], float]:
        """배치 고도 조회 (그리딩 + 벌크 히트 + 적응형 샘플링)"""
        
        if not coordinates:
            return {}
            
        results = {}
        
        # 1. 그리딩 (11m 단위로 좌표 정규화하여 중복 제거)
        grid_map = {} 
        for lat, lon in coordinates:
            grid_coord = (round(lat, 4), round(lon, 4))
            if grid_coord not in grid_map:
                grid_map[grid_coord] = []
            grid_map[grid_coord].append((lat, lon))
            
        unique_grids = list(grid_map.keys())
        seoul_grids = [gc for gc in unique_grids if self.is_in_seoul(*gc)]
        
        # 2. 벌크 캐시 조회 (범위 쿼리로 한 번에 가져오기)
        if seoul_grids:
            lats = [g[0] for g in seoul_grids]
            lons = [g[1] for g in seoul_grids]
            min_lat, max_lat = min(lats) - self.CACHE_TOLERANCE, max(lats) + self.CACHE_TOLERANCE
            min_lon, max_lon = min(lons) - self.CACHE_TOLERANCE, max(lons) + self.CACHE_TOLERANCE
            
            # 해당 범위의 모든 캐시 데이터를 한 번에 조회
            cached_records = self.db.query(ElevationCache).filter(
                and_(
                    ElevationCache.latitude.between(min_lat, max_lat),
                    ElevationCache.longitude.between(min_lon, max_lon)
                )
            ).all()
            
            # 조회된 데이터 맵핑 (그리드 좌표와 매칭)
            cache_data_map = {}
            for rec in cached_records:
                # 저장된 좌표를 그리드 단위(0.0001)로 변환하여 맵핑
                g_key = (round(float(rec.latitude), 4), round(float(rec.longitude), 4))
                cache_data_map[g_key] = float(rec.elevation)

            # 캐시 히트/미스 분류
            cache_hits = {}
            cache_misses = []
            for lat, lon in seoul_grids:
                g_key = (lat, lon)
                if g_key in cache_data_map:
                    cache_hits[g_key] = cache_data_map[g_key]
                else:
                    cache_misses.append((lat, lon))
        else:
            cache_hits = {}
            cache_misses = unique_grids

        # 3. 결과 맵핑
        for gc, elev in cache_hits.items():
            for orig in grid_map[gc]:
                results[orig] = elev
                
        # 4. 캐시 미스 분량 API 호출 (적응형 샘플링 도입)
        if cache_misses:
            # 실시간 요청의 경우 너무 많으면 샘플링 (Pre-cache 스크립트 외의 경우 대비)
            # 여기서는 호출하는 쪽에서 이미 조절하겠지만, 이중 방어막 구축
            max_api_calls = 300
            if len(cache_misses) > max_api_calls:
                import random
                logger.warning(f"Too many cache misses ({len(cache_misses)}). Sampling to {max_api_calls} points.")
                api_targets = random.sample(cache_misses, max_api_calls)
            else:
                api_targets = cache_misses

            client = await self.get_client()
            sem = asyncio.Semaphore(10)
            
            async def fetch_with_sem(lat, lon):
                async with sem:
                    return await self._fetch_from_api(lat, lon, client)
            
            tasks = [fetch_with_sem(lat, lon) for lat, lon in api_targets]
            api_elevations = await asyncio.gather(*tasks)
            
            # API 결과 반영 및 저장
            temp_results = dict(zip(api_targets, api_elevations))
            for (lat, lon), elev in temp_results.items():
                for orig in grid_map[(lat, lon)]:
                    results[orig] = elev
                if self.is_in_seoul(lat, lon):
                    self._save_to_cache(lat, lon, elev)
            
            # 샘플링으로 빠진 지점들은 주변 데이터로 보간 (간단히 기본값 처리 또는 가까운 지점 활용)
            for gc in cache_misses:
                if gc not in temp_results:
                    for orig in grid_map[gc]:
                        results[orig] = results.get(api_targets[0], 20.0) # 가장 가까운 보간 대신 기본값 우선

        # [중요] 모든 변경사항을 DB에 반영
        try:
            self.db.commit()
        except Exception as e:
            logger.error(f"Failed to commit elevation batch: {e}")
            self.db.rollback()

        return results
    
    def _get_from_cache(self, lat: float, lon: float) -> Optional[ElevationCache]:
        """캐시에서 조회 (±10m 오차 허용)"""
        return self.db.query(ElevationCache).filter(
            and_(
                ElevationCache.latitude.between(
                    lat - self.CACHE_TOLERANCE,
                    lat + self.CACHE_TOLERANCE
                ),
                ElevationCache.longitude.between(
                    lon - self.CACHE_TOLERANCE,
                    lon + self.CACHE_TOLERANCE
                )
            )
        ).first()
    
    def _save_to_cache(self, lat: float, lon: float, elevation: float):
        """캐시에 저장 (중복 방지 및 트랜잭션 안전성 확보)"""
        try:
            # SAVEPOINT 생성: 에러 발생 시 이 지점으로만 롤백 (전체 트랜잭션 보호)
            with self.db.begin_nested():
                cache_entry = ElevationCache(
                    latitude=round(lat, 7),
                    longitude=round(lon, 7),
                    elevation=round(elevation, 2)
                )
                self.db.add(cache_entry)
                self.db.flush() # 즉시 DB 반영 시도 (제약조건 위반 체크)
        except Exception:
            # 중복 키 등 에러 발생 시 해당 건만 무시하고 진행
            # begin_nested()가 자동으로 롤백 처리함
            pass
    
    async def _fetch_from_api(self, lat: float, lon: float, client: Optional[httpx.AsyncClient] = None) -> float:
        """VWorld API에서 고도 조회 (클라이언트 재사용)"""
        url = "https://api.vworld.kr/req/data"
        params = {
            "service": "data",
            "request": "GetFeature",
            "data": "LT_CH_DEM_10M",
            "key": self.api_key,
            "domain": "localhost",
            "geomFilter": f"POINT({lon} {lat})"
        }
        
        # 클라이언트가 없으면 일시적으로 생성 (단일 호출 대비)
        temp_client = None
        if client is None:
            temp_client = httpx.AsyncClient()
            client = temp_client
            
        try:
            # 타임아웃 10초로 상향
            response = await client.get(url, params=params, timeout=10.0)
            if response.status_code == 200:
                data = response.json()
                res = data.get("response", {})
                if res.get("status") == "OK":
                    features = res.get("result", {}).get("featureCollection", {}).get("features", [])
                    if features:
                        height = features[0].get("properties", {}).get("height")
                        if height is not None:
                            return float(height)
                elif res.get("status") == "NOT_FOUND":
                    return 20.0
                elif res.get("status") == "ERROR":
                    logger.error(f"VWorld API returned ERROR status for ({lat}, {lon})")
        except Exception as e:
            logger.error(f"VWorld API error at ({lat}, {lon}): {type(e).__name__} - {e}")
        finally:
            if temp_client:
                await temp_client.aclose()
        
        return 20.0  # 기본값
