from sqlalchemy import Column, Integer, Float, DateTime, Index, CheckConstraint, Numeric
from sqlalchemy.sql import func
from app.db.database import Base

class ElevationCache(Base):
    """
    고도 데이터 캐시 (서울시 한정)
    RDS 프리티어 용량 최적화를 위해 위경도 7자리 정밀도 사용
    """
    __tablename__ = "elevation_cache"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    latitude = Column(Numeric(precision=9, scale=7), nullable=False)
    longitude = Column(Numeric(precision=10, scale=7), nullable=False)
    elevation = Column(Numeric(precision=6, scale=2), nullable=False)
    hit_count = Column(Integer, default=1)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        # 복합 인덱스 (중복 방지 및 검색 최적화)
        Index('idx_coords', 'latitude', 'longitude', unique=True),
        # 서울시 범위 제약 (RDS 용량 및 서비스 범위 제한)
        CheckConstraint(
            'latitude BETWEEN 37.4 AND 37.7 AND longitude BETWEEN 126.7 AND 127.2',
            name='check_seoul_bounds'
        ),
    )
