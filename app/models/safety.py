# ============================================
# app/models/safety.py - 안전 인프라 데이터베이스 모델
# ============================================
# CCTV, 가로등(보안등) 위치 정보를 저장하는 테이블입니다.
# 안전점수 계산 시 이 테이블의 좌표를 조회합니다.
# ============================================

from sqlalchemy import Column, String, Integer, DECIMAL, Boolean, DateTime
from datetime import datetime

from app.db.database import Base


class Cctv(Base):
    """
    CCTV 위치 테이블 (cctvs)

    CCTV 설치 위치의 위도/경도를 저장합니다.
    안전점수 계산 시 경로 주변 CCTV 커버리지를 측정하는 데 사용됩니다.
    """
    __tablename__ = "cctvs"

    id = Column(Integer, primary_key=True, autoincrement=True, comment='PK')
    latitude = Column(DECIMAL(10, 7), nullable=False, comment='위도')
    longitude = Column(DECIMAL(10, 7), nullable=False, comment='경도')


class Light(Base):
    """
    가로등(보안등) 위치 테이블 (lights)

    가로등/보안등 설치 위치의 위도/경도를 저장합니다.
    안전점수 계산 시 경로 주변 조명 커버리지를 측정하는 데 사용됩니다.
    """
    __tablename__ = "lights"

    id = Column(Integer, primary_key=True, autoincrement=True, comment='PK')
    latitude = Column(DECIMAL(10, 7), nullable=False, comment='위도')
    longitude = Column(DECIMAL(10, 7), nullable=False, comment='경도')
