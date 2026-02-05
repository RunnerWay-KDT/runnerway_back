"""
DEM (Digital Elevation Model) 기반 고도 조회 서비스

GeoTIFF 형식의 DEM 파일에서 고도 정보를 추출합니다.
- SRTM 30m DEM 지원
- 메모리 캐싱으로 빠른 조회
- 배치 쿼리 최적화

사용 예시:
    from app.services.dem_elevation_service import DEMElevationService
    
    service = DEMElevationService("data/dem/gangnam_srtm_30m.tif")
    elevation = service.get_elevation(37.5172, 127.0473)  # 선릉역
    print(f"고도: {elevation}m")
"""

import os
import logging
from typing import Optional, List, Tuple, Dict
import numpy as np

try:
    import rasterio
    from rasterio.transform import rowcol
except ImportError:
    rasterio = None

logger = logging.getLogger(__name__)


class DEMElevationService:
    """DEM 파일 기반 고도 조회 서비스"""
    
    def __init__(self, dem_file_path: str):
        """
        Args:
            dem_file_path: GeoTIFF DEM 파일 경로
        """
        if rasterio is None:
            raise ImportError(
                "rasterio가 설치되지 않았습니다. "
                "설치: pip install rasterio 또는 conda install -c conda-forge rasterio"
            )
        
        if not os.path.exists(dem_file_path):
            raise FileNotFoundError(f"DEM 파일을 찾을 수 없습니다: {dem_file_path}")
        
        self.dem_file_path = dem_file_path
        self.dataset = None
        self.elevation_data = None
        self.transform = None
        self.bounds = None
        
        self._load_dem()
        
    def _load_dem(self):
        """DEM 파일을 메모리에 로드"""
        try:
            logger.info(f"DEM 파일 로딩 중: {self.dem_file_path}")
            
            # GeoTIFF 파일 열기
            self.dataset = rasterio.open(self.dem_file_path)
            
            # 고도 데이터를 NumPy 배열로 로드 (메모리 캐싱)
            self.elevation_data = self.dataset.read(1)  # 첫 번째 밴드
            
            # 좌표 변환 매트릭스
            self.transform = self.dataset.transform
            
            # 경계 박스 (위경도)
            self.bounds = self.dataset.bounds
            
            logger.info(
                f"DEM 로딩 완료: "
                f"{self.dataset.width}x{self.dataset.height} 픽셀, "
                f"범위: {self.bounds}"
            )
            
        except Exception as e:
            logger.error(f"DEM 로딩 실패: {e}")
            raise
    
    def is_in_coverage(self, lat: float, lon: float) -> bool:
        """
        주어진 좌표가 DEM 커버리지 내에 있는지 확인
        
        Args:
            lat: 위도
            lon: 경도
            
        Returns:
            커버리지 내 여부
        """
        if self.bounds is None:
            return False
        
        return (
            self.bounds.left <= lon <= self.bounds.right and
            self.bounds.bottom <= lat <= self.bounds.top
        )
    
    def get_elevation(self, lat: float, lon: float) -> Optional[float]:
        """
        단일 좌표의 고도 조회
        
        Args:
            lat: 위도
            lon: 경도
            
        Returns:
            고도 (미터), 범위 밖이거나 오류 시 None
        """
        try:
            # 커버리지 확인
            if not self.is_in_coverage(lat, lon):
                return None
            
            # 위경도 → 픽셀 좌표 변환
            row, col = rowcol(self.transform, lon, lat)
            
            # 배열 범위 확인
            if not (0 <= row < self.elevation_data.shape[0] and 
                    0 <= col < self.elevation_data.shape[1]):
                return None
            
            # 고도 값 추출
            elevation = float(self.elevation_data[row, col])
            
            # NoData 값 처리 (-32768 등)
            if elevation < -1000 or elevation > 9000:  # 실제 지구상 고도 범위
                return None
            
            return elevation
            
        except Exception as e:
            logger.warning(f"고도 조회 실패 ({lat}, {lon}): {e}")
            return None
    
    def get_elevations_batch(
        self, 
        coordinates: List[Tuple[float, float]]
    ) -> Dict[Tuple[float, float], float]:
        """
        배치 고도 조회 (벡터화 연산으로 최적화)
        
        Args:
            coordinates: (lat, lon) 튜플 리스트
            
        Returns:
            {(lat, lon): elevation} 딕셔너리
        """
        results = {}
        
        try:
            # 커버리지 내 좌표만 필터링
            valid_coords = [
                (lat, lon) for lat, lon in coordinates
                if self.is_in_coverage(lat, lon)
            ]
            
            if not valid_coords:
                return results
            
            # NumPy 배열로 변환
            lats = np.array([lat for lat, lon in valid_coords])
            lons = np.array([lon for lat, lon in valid_coords])
            
            # 벡터화 좌표 변환
            rows, cols = rowcol(self.transform, lons, lats)
            
            # 유효한 인덱스만 선택
            valid_indices = (
                (rows >= 0) & (rows < self.elevation_data.shape[0]) &
                (cols >= 0) & (cols < self.elevation_data.shape[1])
            )
            
            # 고도 추출
            for i, (lat, lon) in enumerate(valid_coords):
                if valid_indices[i]:
                    elevation = float(self.elevation_data[rows[i], cols[i]])
                    
                    # NoData 값 필터링
                    if -1000 < elevation < 9000:
                        results[(lat, lon)] = elevation
            
            logger.info(
                f"배치 조회 완료: {len(coordinates)}개 요청, "
                f"{len(results)}개 성공"
            )
            
        except Exception as e:
            logger.error(f"배치 조회 실패: {e}")
        
        return results
    
    def get_coverage_info(self) -> Dict:
        """DEM 커버리지 정보 반환"""
        if self.bounds is None:
            return {}
        
        return {
            "bounds": {
                "south": self.bounds.bottom,
                "west": self.bounds.left,
                "north": self.bounds.top,
                "east": self.bounds.right
            },
            "resolution": {
                "width": self.dataset.width,
                "height": self.dataset.height
            },
            "pixel_size_meters": abs(self.transform[0]) * 111320  # 대략적인 미터 변환
        }
    
    def __del__(self):
        """리소스 정리"""
        if self.dataset:
            self.dataset.close()
