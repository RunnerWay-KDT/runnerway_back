# ============================================
# scripts/remove_sidewalk_column.py - sidewalk_score 컬럼 제거
# ============================================
# route_options 테이블에서 sidewalk_score 컬럼 제거
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

from sqlalchemy import create_engine, text, inspect
from app.config import settings

print("="*60)
print("🗑️  sidewalk_score 컬럼 제거")
print("="*60)

try:
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        print("✅ 데이터베이스 연결 성공!")
        
        # 1. 테이블 구조 확인
        inspector = inspect(engine)
        
        # route_options 테이블이 존재하는지 확인
        tables = inspector.get_table_names()
        
        if 'route_options' not in tables:
            print("\n⚠️  route_options 테이블이 존재하지 않습니다.")
            print("   테이블이 아직 생성되지 않았거나 이름이 다릅니다.")
            exit(0)
        
        columns = inspector.get_columns('route_options')
        column_names = [col['name'] for col in columns]
        
        print(f"\n📋 현재 route_options 테이블 컬럼:")
        for col in columns:
            nullable = "NULL" if col['nullable'] else "NOT NULL"
            print(f"  - {col['name']}: {col['type']} {nullable}")
        
        # 2. sidewalk_score 컬럼 확인
        if 'sidewalk_score' not in column_names:
            print(f"\n✅ sidewalk_score 컬럼이 이미 없습니다. 작업 완료!")
            exit(0)
        
        print(f"\n⚠️  sidewalk_score 컬럼이 존재합니다.")
        print(f"   이 컬럼을 삭제하시겠습니까?")
        print(f"\n   경고: 이 작업은 되돌릴 수 없습니다!")
        response = input("   삭제하려면 'yes'를 입력하세요: ")
        
        if response.lower() != 'yes':
            print("\n❌ 취소되었습니다.")
            exit(0)
        
        # 3. 컬럼 삭제
        print(f"\n🗑️  sidewalk_score 컬럼 삭제 중...")
        alter_sql = "ALTER TABLE route_options DROP COLUMN sidewalk_score"
        print(f"   실행: {alter_sql}")
        
        conn.execute(text(alter_sql))
        conn.commit()
        
        print(f"✅ sidewalk_score 컬럼이 삭제되었습니다!")
        
        # 4. 최종 테이블 구조 확인
        print("\n" + "="*60)
        print("📊 최종 route_options 테이블 구조:")
        print("="*60)
        
        # 새로운 inspector로 다시 조회
        inspector = inspect(engine)
        final_columns = inspector.get_columns('route_options')
        
        for col in final_columns:
            nullable = "NULL" if col['nullable'] else "NOT NULL"
            print(f"  - {col['name']}: {col['type']} {nullable}")
        
        print("\n" + "="*60)
        print("✅ 작업 완료!")
        print("="*60)

except Exception as e:
    print(f"\n❌ 오류 발생: {e}")
    import traceback
    traceback.print_exc()
