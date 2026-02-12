"""
SRTM 기반 고도 조회 서비스

SRTM 라이브러리를 사용하여 로컬에서 고도 데이터를 조회합니다.
- 네트워크 요청 없음 (완전 오프라인)
- Rate Limit 없음
- 전 세계 육지 약 30m 해상도 지원
"""

from typing import List, Tuple, Dict, Optional
import logging

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
            logger.error(f"❌ SRTM 초기화 실패: {e}")
            raise RuntimeError(f"SRTM 라이브러리를 로드할 수 없습니다: {e}")
    return _srtm_data


class ElevationService:
    """SRTM 기반 고도 조회 서비스 (로컬 데이터, 오프라인)"""
    
    def __init__(self):
        self._srtm = _get_srtm_data()
    
    def get_elevation(self, lat: float, lon: float) -> Optional[float]:
        """
        단일 좌표 고도 조회
        
        Args:
            lat: 위도
            lon: 경도
            
        Returns:
            고도 (미터), 조회 실패 시 None
        """
        if self._srtm is not None:
            try:
                elev = self._srtm.get_elevation(lat, lon)
                if elev is not None:
                    return float(elev)
            except Exception as e:
                logger.warning(f"SRTM 고도 조회 실패 ({lat}, {lon}): {e}")
        return None
    
    def get_elevations_batch(
        self,
        coordinates: List[Tuple[float, float]]
    ) -> Dict[Tuple[float, float], float]:
        """
        배치 고도 조회
        
        Args:
            coordinates: (lat, lon) 튜플 리스트
            
        Returns:
            {(lat, lon): elevation} 딕셔너리
        """
        if not coordinates:
            return {}
        
        results = {}
        success_count = 0
        
        for lat, lon in coordinates:
            elev = self.get_elevation(lat, lon)
            if elev is not None:
                results[(lat, lon)] = elev
                success_count += 1
        
        if coordinates:
            logger.info(f"⛰️ SRTM 배치 조회: {success_count}/{len(coordinates)}개 성공")
        
        return results
