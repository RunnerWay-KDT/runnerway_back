from typing import List, Tuple, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, tuple_
from app.models.elevation import ElevationCache
from app.core.exceptions import ExternalAPIException
import httpx
import logging
import asyncio
import os
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

logger = logging.getLogger(__name__)

# SRTM 데이터 (모듈 레벨에서 1회만 초기화, 이후 재사용)
_srtm_data = None

def _get_srtm_data():
    """SRTM 데이터를 싱글턴으로 로드"""
    global _srtm_data
    if _srtm_data is None:
        try:
            import srtm
            _srtm_data = srtm.get_data()
            logger.info("✅ SRTM 데이터 초기화 완료")
        except Exception as e:
            logger.warning(f"⚠️ SRTM 초기화 실패: {e}. Open-Meteo fallback 사용.")
    return _srtm_data

class ElevationService:
    """고도 데이터 조회 서비스 (SRTM 우선 → 캐시 → API fallback)"""
    
    # 서울시 경계 (안전 여유 포함)
    SEOUL_BOUNDS = {
        'lat_min': 37.4,
        'lat_max': 37.7,
        'lon_min': 126.7,
        'lon_max': 127.2
    }
    
    # 캐시 검색 허용 오차 (약 11m)
    CACHE_TOLERANCE = 0.0001
    
    def __init__(self, db: Session):
        self.db = db
        self._client = None
        self._srtm = _get_srtm_data()
    
    def _get_srtm_elevation(self, lat: float, lon: float) -> Optional[float]:
        """SRTM에서 고도 조회 (로컬 데이터)"""
        if self._srtm is not None:
            try:
                elev = self._srtm.get_elevation(lat, lon)
                if elev is not None:
                    return float(elev)
            except Exception:
                pass
        return None
    
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
        """단일 좌표 고도 조회 (SRTM → 캐시 → API 순서)"""
        
        # 1. SRTM 우선 조회 (로컬, 가장 빠름)
        srtm_elev = self._get_srtm_elevation(lat, lon)
        if srtm_elev is not None:
            return srtm_elev
        
        # 2. 서울시 범위 체크
        if not self.is_in_seoul(lat, lon):
            logger.warning(f"Coordinate out of Seoul bounds: ({lat}, {lon})")
            return await self._fetch_from_api(lat, lon)
        
        # 3. 캐시 조회
        cached = self._get_from_cache(lat, lon)
        if cached:
            cached.hit_count += 1
            return float(cached.elevation)
        
        # 4. API 호출
        elevation = await self._fetch_from_api(lat, lon)
        
        # 5. 캐시 저장
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
        
        # 1. SRTM 우선 조회 (로컬 데이터, 가장 빠름)
        srtm_results = {}
        remaining_coords = []
        
        for lat, lon in coordinates:
            srtm_elev = self._get_srtm_elevation(lat, lon)
            if srtm_elev is not None:
                srtm_results[(lat, lon)] = srtm_elev
            else:
                remaining_coords.append((lat, lon))
        
        if srtm_results:
            logger.info(f"📍 SRTM 조회: {len(srtm_results)}/{len(coordinates)}개 성공")
        
        # 결과에 SRTM 데이터 추가
        results.update(srtm_results)
        
        # SRTM에서 못 찾은 좌표만 계속 처리
        if not remaining_coords:
            return results
        
        coordinates = remaining_coords
        
        # 2. 그리딩 (좌표 정규화 및 중복 제거)
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
            # logger.info(f"📊 Nearest Cache Hit Rate: {hit_rate:.1f}% ({hit_count_log}/{total_requests} hits, {len(cache_misses)} misses)")
            
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
                
        # 4. 캐시 미스 분량 API 호출 (재활성화)
        if cache_misses:
            # logger.info(f"📡 Fetching {len(cache_misses)} missing points from Open-Meteo API...")
            
            try:
                # 배치 크기 제한 (500개씩) - Open-Meteo는 대량 요청 지원
                batch_size = 500
                api_results = []
                
                for i in range(0, len(cache_misses), batch_size):
                    batch = cache_misses[i:i+batch_size]
                    # logger.info(f"  Batch {i//batch_size + 1}/{(len(cache_misses)-1)//batch_size + 1}: {len(batch)} points")
                    
                    try:
                        elevations = await self._fetch_batch_from_api(batch)
                        api_results.extend(zip(batch, elevations))
                        
                        # Rate limit 방지: 배치 간 대기 (0.05s) - 배치 사이즈 늘려서 호출 횟수 감소
                        if i + batch_size < len(cache_misses):
                            await asyncio.sleep(0.05)
                    except Exception as e:
                        logger.warning(f"  Batch failed: {e}, skipping...")
                        continue
                
                # 결과 매핑 및 저장
                if api_results:
                    # 결과에 추가
                    for coord, elev in api_results:
                        # 그리드 맵에서 원본 좌표들 찾기
                        if coord in grid_map:
                            for orig in grid_map[coord]:
                                results[orig] = elev
                    
                    # DB에 저장
                    cache_items = [(lat, lon, elev) for (lat, lon), elev in api_results]
                    self._save_batch_to_cache(cache_items)
                    
                    # logger.info(f"✅ Successfully fetched and cached {len(api_results)} new points")
                
            except Exception as e:
                logger.error(f"❌ API batch fetch failed: {e}")
        
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
        대량 고도 데이터 캐시 저장 (Bulk Insert) - 중복 방지 최적화
        Args:
            items: (lat, lon, elevation) 튜플 리스트
        """
        if not items:
            return

        from app.db.database import SessionLocal
        
        cache_db = SessionLocal()
        try:
            # 1. 입력된 좌표들의 키 집합 (반올림 처리)
            # 딕셔너리로 만들어서 나중에 고도값도 쉽게 찾을 수 있게 함
            input_map = {
                (round(lat, 7), round(lon, 7)): round(elev, 2) 
                for lat, lon, elev in items
            }
            
            if not input_map:
                return

            # 2. DB에서 이미 존재하는 좌표 조회 (Bulk 조회)
            existing_records = cache_db.query(ElevationCache.latitude, ElevationCache.longitude).filter(
                tuple_(ElevationCache.latitude, ElevationCache.longitude).in_(input_map.keys())
            ).all()
            
            # 이미 존재하는 좌표 집합
            existing_coords = set((float(r.latitude), float(r.longitude)) for r in existing_records)
            
            # 3. 존재하지 않는 새로운 데이터만 필터링
            new_objects = []
            for (lat, lon), elev in input_map.items():
                # DB에서 가져온 값은 float 변환 필요 (Decimal 등으로 올 수 있음)
                # 위에서 이미 float으로 변환해서 set에 넣었으므로 바로 비교 가능
                # 단, 부동소수점 오차 고려하여 round 처리된 값끼리 비교
                if (lat, lon) not in existing_coords:
                    new_objects.append(
                        ElevationCache(
                            latitude=lat,
                            longitude=lon,
                            elevation=elev
                        )
                    )
            
            # 4. 정말로 새로운 데이터만 Bulk Insert
            if new_objects:
                cache_db.bulk_save_objects(new_objects)
                cache_db.commit()
                # logger.info(f"✅ Bulk saved {len(new_objects)} new elevation points to cache (skipped {len(items) - len(new_objects)} duplicates)")
            else:
                # logger.info(f"ℹ️ All {len(items)} points already exist in cache. Skipping save.")
                pass
            
        except Exception as e:
            cache_db.rollback()
            logger.warning(f"⚠️ Bulk save failed: {e}")
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
