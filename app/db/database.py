# ============================================
# app/db/database.py - 데이터베이스 연결 설정
# ============================================
# 이 파일은 MariaDB 데이터베이스 연결을 관리합니다.
# SQLAlchemy ORM을 사용하여 데이터베이스 작업을 수행합니다.
# ============================================

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from app.config import settings


# ============================================
# 데이터베이스 엔진 생성
# ============================================
# 엔진(Engine)은 데이터베이스와의 연결을 관리하는 객체입니다.
# 연결 풀(Connection Pool)을 사용하여 효율적으로 연결을 관리합니다.
#
# [신입 개발자를 위한 팁]
# - pool_pre_ping: 연결이 유효한지 미리 확인 (끊어진 연결 방지)
# - pool_recycle: 연결 재사용 시간 (초). MariaDB는 8시간 후 연결 끊김
# - echo: True로 설정하면 실행되는 SQL을 콘솔에 출력 (디버깅용)
# ============================================
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,      # 연결 상태 확인
    pool_recycle=3600,       # 1시간마다 연결 갱신
    echo=settings.DEBUG      # 디버그 모드에서만 SQL 출력
)


# ============================================
# 세션 팩토리 생성
# ============================================
# SessionLocal은 데이터베이스 세션을 생성하는 팩토리입니다.
# 세션(Session)은 데이터베이스 작업(CRUD)을 수행하는 단위입니다.
#
# [신입 개발자를 위한 팁]
# - autocommit=False: 자동 커밋 비활성화 (명시적으로 commit() 호출 필요)
# - autoflush=False: 자동 플러시 비활성화 (쿼리 전에 자동으로 DB에 반영하지 않음)
# - bind=engine: 이 세션이 어떤 엔진(DB)에 연결되는지 지정
# ============================================
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


# ============================================
# 모델 베이스 클래스
# ============================================
# 모든 데이터베이스 모델(테이블)은 이 Base 클래스를 상속받습니다.
# 이를 통해 SQLAlchemy가 테이블을 인식하고 관리할 수 있습니다.
#
# [신입 개발자를 위한 팁]
# - declarative_base()는 ORM 모델의 기본 클래스를 생성합니다.
# - 이 Base를 상속받은 클래스가 실제 데이터베이스 테이블이 됩니다.
# ============================================
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    데이터베이스 세션을 생성하고 반환하는 의존성 함수
    
    FastAPI의 Dependency Injection 시스템에서 사용됩니다.
    API 엔드포인트에서 db 파라미터로 세션을 받을 수 있습니다.
    
    [신입 개발자를 위한 팁]
    - yield를 사용하면 제너레이터 함수가 됩니다.
    - yield 전: 세션 생성
    - yield: 세션을 반환하고 대기
    - yield 후 (finally): 세션 종료 (정리 작업)
    
    사용 예시:
        @app.get("/users")
        def get_users(db: Session = Depends(get_db)):
            return db.query(User).all()
    
    Returns:
        Generator[Session, None, None]: 데이터베이스 세션 제너레이터
    """
    # 새로운 세션 생성
    db = SessionLocal()
    try:
        # 세션을 API 엔드포인트에 전달
        yield db
    finally:
        # API 처리가 끝나면 세션 종료
        # 예외가 발생해도 반드시 실행됩니다
        db.close()
