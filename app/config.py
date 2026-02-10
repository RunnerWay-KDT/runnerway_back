# ============================================
# app/config.py - 환경 설정 파일
# ============================================
# 이 파일은 애플리케이션의 모든 설정을 관리합니다.
# .env 파일에서 값을 읽어와서 사용합니다.
# ============================================

from functools import lru_cache
from typing import List, Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    애플리케이션 설정 클래스
    
    Pydantic의 BaseSettings를 상속받아 환경 변수를 자동으로 로드합니다.
    - .env 파일에서 값을 읽어옵니다.
    - 환경 변수가 설정되어 있으면 그 값을 우선 사용합니다.
    
    [신입 개발자를 위한 팁]
    - 이 클래스의 변수명과 .env 파일의 키 이름은 동일해야 합니다.
    - 대소문자는 구분하지 않습니다 (SECRET_KEY = secret_key)
    """
    
    # --------------------------------------------
    # 서버 설정
    # --------------------------------------------
    # 현재 환경 (development, production, testing)
    ENVIRONMENT: str = "development"
    
    # 디버그 모드
    DEBUG: bool = True
    
    # JWT 서명에 사용할 비밀 키 (반드시 .env에서 변경하세요!)
    SECRET_KEY: str = "your-super-secret-key-change-this-in-production"
    
    # CORS 허용 도메인 (프론트엔드 주소)
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:19006,http://localhost:8081"
    
    # API 버전 프리픽스
    API_V1_PREFIX: str = "/api/v1"
    
    # OSMnx 캐시 디렉토리
    OSMNX_CACHE_DIR: str = "cache/osmnx"
    
    # --------------------------------------------
    # 데이터베이스 설정
    # --------------------------------------------
    # MariaDB 호스트
    DB_HOST: str = "localhost"
    
    # MariaDB 포트
    DB_PORT: int = 3306
    
    # 데이터베이스 이름
    DB_NAME: str = "runnerway"
    
    # 데이터베이스 사용자명
    DB_USER: str = "root"
    
    # 데이터베이스 비밀번호
    DB_PASSWORD: str = ""
    
    # --------------------------------------------
    # JWT 토큰 설정
    # --------------------------------------------
    # Access Token 만료 시간 (일) - 10년 (Y2038 문제 방지)
    ACCESS_TOKEN_EXPIRE_DAYS: int = 3650
    
    # Refresh Token 만료 시간 (일) - 10년 (Y2038 문제 방지)
    REFRESH_TOKEN_EXPIRE_DAYS: int = 3650
    
    # JWT 알고리즘
    JWT_ALGORITHM: str = "HS256"
    
    # --------------------------------------------
    # 카카오 OAuth 설정
    # --------------------------------------------
    # 카카오 REST API 키
    KAKAO_CLIENT_ID: str = ""
    
    # 카카오 Client Secret (선택사항)
    KAKAO_CLIENT_SECRET: str = ""
    
    # 카카오 로그인 후 리다이렉트 URL
    KAKAO_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/social/kakao/callback"
    
    # --------------------------------------------
    # 기타 설정
    # --------------------------------------------
    # 로그 레벨
    LOG_LEVEL: str = "DEBUG"
    
    # DEM 파일 경로 (선택적)
    DEM_FILE_PATH: Optional[str] = None

    
    @property
    def DATABASE_URL(self) -> str:
        """
        데이터베이스 연결 문자열을 생성합니다.
        
        형식: mysql+pymysql://사용자:비밀번호@호스트:포트/데이터베이스
        
        [신입 개발자를 위한 팁]
        - @property 데코레이터는 메서드를 속성처럼 사용할 수 있게 해줍니다.
        - settings.DATABASE_URL 처럼 () 없이 호출할 수 있습니다.
        """
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            f"?charset=utf8mb4"
        )
    
    @property
    def cors_origins_list(self) -> List[str]:
        """
        CORS 허용 도메인을 리스트로 반환합니다.
        
        환경 변수에서는 쉼표로 구분된 문자열로 저장하고,
        실제 사용할 때는 리스트로 변환합니다.
        """
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    class Config:
        """
        Pydantic 설정
        
        env_file: .env 파일 경로
        env_file_encoding: .env 파일 인코딩
        case_sensitive: 환경 변수 대소문자 구분 여부
        """
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """
    설정 객체를 반환합니다.
    
    @lru_cache() 데코레이터를 사용하여 한 번만 생성하고 캐시합니다.
    매번 새로운 객체를 생성하면 성능이 저하되기 때문입니다.
    
    [신입 개발자를 위한 팁]
    - lru_cache는 함수의 결과를 캐시(저장)해두고 재사용합니다.
    - 같은 인자로 함수를 호출하면 저장된 결과를 바로 반환합니다.
    
    사용 예시:
        from app.config import get_settings
        settings = get_settings()
        print(settings.SECRET_KEY)
    """
    return Settings()


# 전역 설정 객체 (편의를 위해 미리 생성)
settings = get_settings()
