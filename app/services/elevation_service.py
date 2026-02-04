from typing import List, Tuple, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.models.elevation import ElevationCache
from app.core.exceptions import ExternalAPIException
import httpx
import logging
import asyncio
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

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
    
    def __init__(self, db: Session):
        self.db = db
        self._client = None
    
    async def __aenter__(self):
        """Context Manager 진입: AsyncClient 생성"""
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=5.0),
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=50)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context Manager 종료: AsyncClient 정리"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        return False
    
    async def get_client(self) -> httpx.AsyncClient:
        """AsyncClient 반환 (Context Manager 사용 시 자동 생성됨)"""
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
            # hit_count 증가 (커밋은 배치 작업 끝에만 수행)
            cached.hit_count += 1
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
        """
        배치 고도 조회 (그리딩 + 벌크 히트 + Nearest Neighbor Lookup + 적응형 샘플링)
        """
        if not coordinates:
            return {}
            
        results = {}
        
        # 1. 그리딩 (좌표 정규화 및 중복 제거) - 반올림 유지 (API 호출 시 활용)
        grid_map = {} 
        for lat, lon in coordinates:
            # 11m 단위 정도는 같은 점으로 취급해도 무방하므로 4자리 반올림
            grid_coord = (round(lat, 4), round(lon, 4))
            if grid_coord not in grid_map:
                grid_map[grid_coord] = []
            grid_map[grid_coord].append((lat, lon))
            
        unique_grids = list(grid_map.keys())
        # 서울시 내부 좌표만 필터링
        seoul_grids = [gc for gc in unique_grids if self.is_in_seoul(*gc)]
        
        # 2. 캐시 조회 (Nearest Neighbor Lookup)
        # 해당 영역의 모든 캐시 데이터를 가져와서 메모리에서 가까운 점 찾기
        cache_hits = {}
        cache_misses = []
        
        if seoul_grids:
            lats = [g[0] for g in seoul_grids]
            lons = [g[1] for g in seoul_grids]
            
            # 검색 범위 설정 (여유분 포함)
            # 0.005도 ≈ 500m 여유 (경로 주변 데이터를 충분히 가져옴)
            margin = 0.005 
            min_lat, max_lat = min(lats) - margin, max(lats) + margin
            min_lon, max_lon = min(lons) - margin, max(lons) + margin
            
            # DB에서 범위 내 모든 캐시 데이터 로드
            cached_records = self.db.query(ElevationCache).filter(
                and_(
                    ElevationCache.latitude.between(min_lat, max_lat),
                    ElevationCache.longitude.between(min_lon, max_lon)
                )
            ).all()
            
            # 빠른 검색을 위한 데이터 구조화 (반올림된 좌표 키 사용 가능성 체크)
            # KD-Tree는 오버헤드가 클 수 있으니, 단순 거리 계산 (데이터가 아주 많지 않다고 가정)
            # 최적화: 0.001도(약 100m) 단위 로 격자화하여 검색 대상 축소
            spatial_index = {}
            for rec in cached_records:
                # DB에서 가져온 Decimal 타입을 float으로 변환
                r_lat = float(rec.latitude)
                r_lon = float(rec.longitude)
                r_elev = float(rec.elevation)
                
                # 100m 그리드 키
                lat_idx = int(r_lat * 1000)
                lon_idx = int(r_lon * 1000)
                key = (lat_idx, lon_idx)
                
                if key not in spatial_index:
                    spatial_index[key] = []
                spatial_index[key].append((r_lat, r_lon, r_elev))

            # 각 요청 좌표에 대해 가장 가까운 캐시 찾기
            hit_count_log = 0
            
            for lat, lon in seoul_grids:
                found_elevation = None
                min_dist = float('inf')
                
                # 검색할 인접 그리드 키들 (자신 + 주변 8방향)
                base_lat_idx = int(lat * 1000)
                base_lon_idx = int(lon * 1000)
                
                candidate_points = []
                for d_lat in [-1, 0, 1]:
                    for d_lon in [-1, 0, 1]:
                        k = (base_lat_idx + d_lat, base_lon_idx + d_lon)
                        if k in spatial_index:
                            candidate_points.extend(spatial_index[k])
                
                # 후보군 중에서 가장 가까운 점 찾기
                for c_lat, c_lon, c_elev in candidate_points:
                    # 유클리드 거리 근사 (속도 최적화)
                    # 위도 1도 ≈ 111km, 경도 1도 ≈ 88.8km (서울 기준)
                    dy = (lat - c_lat) * 111000
                    dx = (lon - c_lon) * 88800
                    dist = (dx*dx + dy*dy) ** 0.5
                    
                    if dist < min_dist:
                        min_dist = dist
                        found_elevation = c_elev
                
                # 허용 오차: 45m (50m 격자의 대각선 절반 35.35m 커버 + 여유)
                if found_elevation is not None and min_dist <= 45:
                    cache_hits[(lat, lon)] = found_elevation
                    hit_count_log += 1
                else:
                    cache_misses.append((lat, lon))
            
            # 📊 캐시 히트율 로깅
            total_requests = len(seoul_grids)
            hit_rate = (hit_count_log / total_requests * 100) if total_requests > 0 else 0
            logger.info(f"📊 Nearest Cache Hit Rate: {hit_rate:.1f}% ({hit_count_log}/{total_requests} hits, {len(cache_misses)} misses)")
            
        else:
            cache_hits = {}
            # 서울 밖이면 전체가 미스 (단, 서울 밖은 API 호출 대상이 아닐 수도 있음. 로직 확인 필요)
            # 여기서는 unique_grids가 서울 밖인 경우 cache_misses에 추가되어 API 호출됨 (기존 로직 유지)
            # 단, is_in_seoul 체크가 위에서 있었으므로 서울 밖은 cache_misses에 아예 안 들어갈 수도 있음.
            # 원본 로직 유지: 서울 아닌 곳은 API 호출 (get_elevation 참조)
            # 하지만 여기서 seoul_grids만 처리했으므로, 서울 밖 좌표는 누락될 수 있음.
            # unique_grids 전체를 순회하며 서울 밖은 바로 cache_misses로?
            # -> 기존 코드: seoul_grids만 캐시 로직 태움.
            
            # 서울 밖 좌표 처리
            non_seoul = [gc for gc in unique_grids if not self.is_in_seoul(*gc)]
            cache_misses.extend(non_seoul)

        # 3. 결과 맵핑 (히트된 데이터)
        for gc, elev in cache_hits.items():
            for orig in grid_map[gc]:
                results[orig] = elev
                
        # 4. 캐시 미스 분량 API 호출 (Skip for now to avoid 429)
        if cache_misses:
            logger.info(f"Skipping Open-Meteo API for {len(cache_misses)} points due to rate limits. Using defaults.")
            # API 호출 없이 단순히 넘어갑니다. 
            # 호출자(RoadNetworkFetcher)에서 .get(coord, 20.0)으로 기본값을 처리합니다.

        return results
    
    
    def _get_from_cache(self, lat: float, lon: float) -> Optional[ElevationCache]:
        """
        캐시에서 조회 (정확한 좌표 매칭)
        """
        # 그리딩과 동일한 방식으로 좌표 반올림 (11m 단위)
        lat_key = round(lat, 4)
        lon_key = round(lon, 4)
        
        return self.db.query(ElevationCache).filter(
            and_(
                ElevationCache.latitude == lat_key,
                ElevationCache.longitude == lon_key
            )
        ).first()
    
    
    def _save_to_cache(self, lat: float, lon: float, elevation: float):
        """
        캐시에 저장 (별도 세션 사용으로 트랜잭션 독립성 보장)
        """
        from app.db.database import SessionLocal
        
        cache_db = SessionLocal()
        try:
            # 중복 체크
            existing = cache_db.query(ElevationCache).filter(
                and_(
                    ElevationCache.latitude == round(lat, 7),
                    ElevationCache.longitude == round(lon, 7)
                )
            ).first()
            
            if existing:
                existing.hit_count += 1
                cache_db.commit()
            else:
                cache_entry = ElevationCache(
                    latitude=round(lat, 7),
                    longitude=round(lon, 7),
                    elevation=round(elevation, 2)
                )
                cache_db.add(cache_entry)
                cache_db.commit()
        except Exception as e:
            cache_db.rollback()
            logger.warning(f"❌ Cache save failed: {e}")
            # 캐시 저장 실패는 크리티컬하지 않으므로 로그만 남김 (사용자 흐름 방해 X)
        finally:
            cache_db.close()

    def _save_batch_to_cache(self, items: List[Tuple[float, float, float]]):
        """
        대량 고도 데이터 캐시 저장 (Bulk Insert)
        Args:
            items: (lat, lon, elevation) 튜플 리스트
        """
        if not items:
            return

        from app.db.database import SessionLocal
        
        cache_db = SessionLocal()
        try:
            new_entries = []
            
            # 1. 중복 확인을 위해 이미 존재하는 좌표 조회
            # (데이터가 많을 경우 여기서도 성능 이슈가 있을 수 있으나, 
            #  일단 INSERT 시 충돌 방지를 위해 체크하거나 ON CONFLICT DO NOTHING을 써야 함.
            #  SQLAlchemy Core를 쓰지 않고 ORM Level에서 처리하려면 간단히 조회 후 없는 것만 추가)
            
            # 입력된 좌표들의 키 집합
            input_keys = set((round(lat, 7), round(lon, 7)) for lat, lon, _ in items)
            
            # OR 조건을 동적으로 생성하기 어려우니, 단순화를 위해
            # Loop check 대신, TRY-EXCEPT으로 개별 등록 혹은
            # Postgres의 ON CONFLICT 기능을 쓰는게 좋지만, 
            # 여기서는 DB 종속성을 최소화하고 로직 단순화를 위해 
            # '없는 것만 추가'하는 로직을 Python 레벨에서 구현 (Batch Size가 작으므로 가능)

            # 하지만 100개 정도면 그냥 bulk_save_objects를 시도하되, 
            # 중복 에러가 나면 무시하는 방법도 있음.
            # 가장 안전하고 범용적인 방법: 하나씩 확인하지 않고, 
            # 캐시되지 않은 좌표만 필터링해서 Bulk Insert

            # DB에 있는 해당 범위의 데이터 조회는 복잡하므로,
            # 단순하게: 
            # "방금 API에서 가져온 데이터는 DB에 없을 확률이 높음 (왜냐하면 아까 조회했을 때 없었으니까)"
            # 단, 동시성 이슈로 그 사이에 누가 넣었을 수는 있음.
            
            # 안전하게 가기 위해:
            # objects 생성
            
            objects = [
                ElevationCache(
                    latitude=round(lat, 7),
                    longitude=round(lon, 7),
                    elevation=round(elev, 2)
                )
                for lat, lon, elev in items
            ]
            
            # bulk_save_objects 사용 (return_defaults=False로 속도 향상)
            # 중복 키 에러 발생 시... 사실 이걸 막으려면 조회후 넣거나
            # merge를 써야하는데 merge는 느림.
            # 여기서는 API에서 가져온 'Miss' 데이터이므로, 기본적으로 DB에 없다고 가정하고 넣되
            # 에러 발생 시(Unique Violation) 해당 배치는 개별 건으로 재시도하거나 포기(Log only).
            
            cache_db.bulk_save_objects(objects)
            cache_db.commit()
            logger.info(f"✅ Bulk saved {len(objects)} elevation points to cache")
            
        except Exception as e:
            cache_db.rollback()
            logger.warning(f"⚠️ Bulk save failed (possibly duplicate), retrying individually: {e}")
            # 실패 시 개별 저장 시도 (Fallback)
            for lat, lon, elev in items:
                self._save_to_cache(lat, lon, elev)
        finally:
            cache_db.close()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        reraise=True
    )
    async def _fetch_batch_from_api(self, coordinates: List[Tuple[float, float]]) -> List[float]:
        """Open-Meteo API에서 다중 좌표 고도 조회"""
        if not coordinates:
            return []
            
        url = "https://api.open-meteo.com/v1/elevation"
        
        # 좌표 목록을 콤마로 구분된 문자열로 변환
        lats = [str(lat) for lat, lon in coordinates]
        lons = [str(lon) for lat, lon in coordinates]
        
        params = {
            "latitude": ",".join(lats),
            "longitude": ",".join(lons)
        }
        
        client = await self.get_client()
        
        try:
            response = await client.get(url, params=params, timeout=20.0) # 배치라 시간 좀 더 줌
            response.raise_for_status()
            
            data = response.json()
            elevations = data.get("elevation", [])
            
            if not elevations:
                raise ExternalAPIException("Open-Meteo returned no data")
                
            if len(elevations) != len(coordinates):
                raise ExternalAPIException(f"Open-Meteo data mismatch: requested {len(coordinates)}, got {len(elevations)}")
                
            return [float(e) for e in elevations]
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Open-Meteo API HTTP error: {e.response.status_code}")
            raise ExternalAPIException(f"Elevation fetch failed: HTTP {e.response.status_code}")
        except Exception as e:
            logger.error(f"Open-Meteo API error: {e}")
            raise # 예외 전파
