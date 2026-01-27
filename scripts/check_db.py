# ============================================
# scripts/check_db.py - 기존 DB 확인
# ============================================
# 이미 구축된 데이터베이스의 테이블을 확인하는 스크립트
# ============================================

import sys
from pathlib import Path

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# .env 파일 명시적 로드
from dotenv import load_dotenv
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)

from sqlalchemy import create_engine, inspect, text
from app.config import settings

print("="*60)
print("📊 데이터베이스 연결 확인")
print("="*60)
print(f"호스트: {settings.DB_HOST}")
print(f"데이터베이스: {settings.DB_NAME}")
print(f"사용자: {settings.DB_USER}")
print("="*60)

try:
    # 엔진 생성
    engine = create_engine(settings.DATABASE_URL)
    
    # 연결 테스트
    with engine.connect() as conn:
        print("✅ 데이터베이스 연결 성공!")
        
        # 현재 데이터베이스 이름 확인
        result = conn.execute(text("SELECT DATABASE()"))
        current_db = result.scalar()
        print(f"📁 현재 데이터베이스: {current_db}")
        
        # 테이블 목록 조회
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        print(f"\n📋 총 {len(tables)}개의 테이블 발견:")
        print("-" * 60)
        for i, table in enumerate(tables, 1):
            # 각 테이블의 컬럼 정보
            columns = inspector.get_columns(table)
            print(f"{i}. {table} ({len(columns)}개 컬럼)")
            
        # 각 테이블의 상세 정보
        print("\n" + "="*60)
        print("📊 테이블 상세 정보")
        print("="*60)
        for table in tables:
            print(f"\n테이블: {table}")
            print("-" * 40)
            columns = inspector.get_columns(table)
            for col in columns:
                col_type = str(col['type'])
                nullable = "NULL" if col['nullable'] else "NOT NULL"
                default = f" DEFAULT {col['default']}" if col.get('default') else ""
                print(f"  - {col['name']}: {col_type} {nullable}{default}")
                
except Exception as e:
    print(f"❌ 오류 발생: {e}")
    import traceback
    traceback.print_exc()
