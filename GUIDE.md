# 🏃‍♂️ 러너웨이 백엔드 완벽 가이드

> **신입 개발자를 위한 FastAPI 실전 프로젝트 학습 가이드**
>
> 이 문서는 러너웨이 백엔드 프로젝트를 통해 FastAPI를 처음부터 끝까지 배울 수 있도록 구성되었습니다.

---

## 📚 목차

1. [프로젝트 개요](#1-프로젝트-개요)
2. [프로젝트 구조 이해하기](#2-프로젝트-구조-이해하기)
3. [핵심 개념 학습](#3-핵심-개념-학습)
4. [데이터베이스 설계](#4-데이터베이스-설계)
5. [API 개발 흐름](#5-api-개발-흐름)
6. [인증과 보안](#6-인증과-보안)
7. [실전 기능 추가 예제](#7-실전-기능-추가-예제)
8. [테스트와 디버깅](#8-테스트와-디버깅)
9. [배포 준비](#9-배포-준비)

---

## 1. 프로젝트 개요

### 🎯 러너웨이란?

러너웨이는 사용자가 원하는 **도형 모양**으로 러닝 경로를 생성하고, GPS로 실시간 추적하며, 커뮤니티에서 공유할 수 있는 러닝 앱입니다.

### 🛠 기술 스택

```
언어: Python 3.12+
웹 프레임워크: FastAPI 0.115+
ORM: SQLAlchemy 2.0
데이터베이스: MariaDB (AWS RDS)
인증: JWT (JSON Web Token)
소셜 로그인: Kakao OAuth
비동기: async/await
```

### ⚡ FastAPI를 선택한 이유

1. **빠른 성능**: Node.js, Go와 비슷한 고성능
2. **자동 문서화**: Swagger UI 자동 생성
3. **타입 힌트**: Pydantic으로 자동 검증
4. **비동기 지원**: async/await로 높은 동시성
5. **배우기 쉬움**: Python 문법 + 직관적인 API

---

## 2. 프로젝트 구조 이해하기

### 📁 전체 구조

```
runnerway_back/
│
├── app/                          # 메인 애플리케이션
│   ├── __init__.py              # 패키지 초기화
│   ├── main.py                  # 🔥 FastAPI 앱 시작점 (여기서 시작!)
│   ├── config.py                # 환경 설정 관리
│   │
│   ├── api/                     # API 엔드포인트
│   │   └── v1/                  # API 버전 1
│   │       ├── router.py        # 모든 라우터 통합
│   │       ├── auth.py          # 인증 API
│   │       ├── users.py         # 사용자 API
│   │       ├── routes.py        # 경로 생성 API
│   │       ├── workouts.py      # 운동 API
│   │       └── community.py     # 커뮤니티 API
│   │
│   ├── models/                  # 데이터베이스 모델 (테이블 정의)
│   │   ├── user.py              # 사용자 테이블
│   │   ├── route.py             # 경로 테이블
│   │   ├── workout.py           # 운동 테이블
│   │   └── community.py         # 커뮤니티 테이블
│   │
│   ├── schemas/                 # 요청/응답 형식 (Pydantic)
│   │   ├── auth.py
│   │   ├── user.py
│   │   ├── route.py
│   │   ├── workout.py
│   │   ├── community.py
│   │   └── common.py            # 공통 응답 형식
│   │
│   ├── services/                # 비즈니스 로직
│   │   ├── auth_service.py      # 인증 서비스
│   │   ├── route_service.py     # 경로 서비스
│   │   ├── workout_service.py   # 운동 서비스
│   │   ├── community_service.py # 커뮤니티 서비스
│   │   └── kakao_service.py     # 카카오 API
│   │
│   ├── core/                    # 핵심 기능
│   │   ├── security.py          # JWT, 비밀번호 해싱
│   │   └── exceptions.py        # 예외 처리
│   │
│   └── db/                      # 데이터베이스 설정
│       ├── database.py          # DB 연결
│       └── init_db.py           # DB 초기화
│
├── scripts/                     # 유틸리티 스크립트
│   ├── seed_data.py            # 초기 데이터 삽입
│   ├── fix_charset.py          # DB 인코딩 수정
│   ├── check_db.py             # DB 상태 확인
│   └── test_env.py             # 환경 변수 테스트
│
├── .env                         # 환경 변수 (비밀 정보)
├── .env.example                # 환경 변수 템플릿
├── requirements.txt            # Python 패키지 목록
├── README.md                   # 프로젝트 설명
└── GUIDE.md                    # 이 파일!
```

### 🔍 각 폴더의 역할

#### 1. `app/api/` - API 엔드포인트

**역할**: 클라이언트의 HTTP 요청을 받는 곳

```python
# 예시: app/api/v1/users.py
@router.get("/me")
async def get_my_profile(
    current_user: User = Depends(get_current_user)
):
    """내 프로필 조회"""
    return current_user
```

**특징**:

- `@router.get()`, `@router.post()` 같은 데코레이터로 경로 정의
- 요청 검증은 Pydantic이 자동으로 수행
- 응답도 자동 직렬화

#### 2. `app/models/` - 데이터베이스 모델

**역할**: DB 테이블을 Python 클래스로 정의

```python
# 예시: app/models/user.py
class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
```

**특징**:

- SQLAlchemy ORM 사용
- Python 객체처럼 다룰 수 있음
- 관계(relationship)도 정의 가능

#### 3. `app/schemas/` - 요청/응답 스키마

**역할**: API 입출력 형식 정의 및 검증

```python
# 예시: app/schemas/user.py
class UserCreate(BaseModel):
    email: EmailStr              # 자동 이메일 검증
    password: str = Field(min_length=8)  # 최소 8자
    name: str = Field(max_length=100)

class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    created_at: datetime
```

**특징**:

- Pydantic으로 자동 검증
- 타입 안전성 보장
- 자동 문서화

#### 4. `app/services/` - 비즈니스 로직

**역할**: 실제 기능 구현 (DB 조작, 외부 API 호출 등)

```python
# 예시: app/services/auth_service.py
class AuthService:
    def signup(self, request: SignupRequest):
        # 1. 중복 이메일 체크
        # 2. 비밀번호 해싱
        # 3. DB에 사용자 저장
        # 4. 토큰 발급
        return tokens
```

**특징**:

- API 라우터와 DB 사이의 중간 계층
- 재사용 가능한 로직
- 테스트하기 쉬움

---

## 3. 핵심 개념 학습

### 🔥 1. FastAPI 앱 시작 (`app/main.py`)

```python
from fastapi import FastAPI

# FastAPI 인스턴스 생성
app = FastAPI(
    title="러너웨이 API",
    description="러닝 경로 생성 및 추적 서비스",
    version="1.0.0"
)

# 라우터 등록
app.include_router(
    api_router,
    prefix="/api/v1"  # 모든 API는 /api/v1/ 로 시작
)

# 서버 실행: uvicorn app.main:app --reload
```

**핵심 포인트**:

- `app`은 전체 애플리케이션의 중심
- `include_router()`로 API 엔드포인트 추가
- 자동으로 `/docs`에서 Swagger UI 제공

### 🔒 2. 환경 설정 (`app/config.py`)

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # 데이터베이스
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_NAME: str = "runnerway"
    DB_USER: str = "root"
    DB_PASSWORD: str = ""

    # JWT
    SECRET_KEY: str = "change-this-in-production"

    class Config:
        env_file = ".env"  # .env 파일에서 자동 로드

settings = Settings()
```

**핵심 포인트**:

- `.env` 파일의 값을 자동으로 읽음
- 타입 검증 자동
- 환경별(개발/운영) 설정 분리

### 🗄️ 3. 데이터베이스 연결 (`app/db/database.py`)

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# 엔진 생성 (DB 연결 풀)
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,  # 연결 상태 자동 체크
    echo=True            # SQL 쿼리 로그 출력
)

# 세션 팩토리
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# 의존성 주입용 함수
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

**핵심 포인트**:

- `engine`: DB 연결 관리
- `SessionLocal`: DB 세션 생성
- `get_db()`: FastAPI의 Depends()와 함께 사용

### 🎯 4. 의존성 주입 (Dependency Injection)

```python
from fastapi import Depends

# API 엔드포인트에서 사용
@router.get("/users/me")
async def get_my_profile(
    db: Session = Depends(get_db),              # DB 세션 주입
    current_user: User = Depends(get_current_user)  # 현재 사용자 주입
):
    return current_user
```

**핵심 포인트**:

- `Depends()`로 자동 주입
- 재사용 가능
- 테스트 시 Mock으로 교체 가능

### 🔐 5. 인증 흐름

```
1. 회원가입/로그인
   ↓
2. JWT 토큰 발급 (Access + Refresh)
   ↓
3. 클라이언트가 헤더에 토큰 포함
   Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
   ↓
4. get_current_user()에서 토큰 검증
   ↓
5. 인증된 사용자 정보 반환
```

**구현 코드**:

```python
# app/core/security.py
from jose import jwt

def create_access_token(data: dict):
    """JWT 액세스 토큰 생성"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=60)
    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm="HS256"
    )
    return encoded_jwt

# app/api/deps.py
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """토큰에서 현재 사용자 추출"""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=["HS256"]
        )
        user_id = payload.get("sub")

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise AuthenticationException("사용자를 찾을 수 없습니다")

        return user
    except JWTError:
        raise AuthenticationException("유효하지 않은 토큰입니다")
```

---

## 4. 데이터베이스 설계

### 📊 ERD (Entity Relationship Diagram)

```
┌──────────┐         ┌──────────────┐         ┌──────────┐
│  users   │────────<│  workouts    │>────────│  routes  │
│          │   1:N   │              │   N:1   │          │
│  id      │         │  id          │         │  id      │
│  email   │         │  user_id     │         │  user_id │
│  name    │         │  route_id    │         │  shape_id│
└──────────┘         │  distance    │         └──────────┘
     │               │  duration    │              │
     │1:N            └──────────────┘              │N:1
     │                                             │
     ↓                                             ↓
┌──────────┐                              ┌──────────────┐
│user_stats│                              │route_shapes  │
│          │                              │              │
│  user_id │                              │  shape_id    │
│  total_  │                              │  name        │
│  distance│                              │  icon_name   │
└──────────┘                              └──────────────┘
```

### 🔑 주요 테이블 설명

#### 1. `users` - 사용자

```sql
CREATE TABLE users (
    id VARCHAR(36) PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255),  -- 비밀번호는 bcrypt로 해싱
    name VARCHAR(100) NOT NULL,
    avatar VARCHAR(500),
    provider VARCHAR(20),        -- 'kakao' or NULL
    provider_id VARCHAR(255),    -- 카카오 사용자 ID
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL    -- Soft Delete
);
```

**특징**:

- UUID 사용으로 ID 예측 불가
- 소셜 로그인 지원 (provider, provider_id)
- Soft Delete (deleted_at으로 삭제 표시)

#### 2. `route_shapes` - 도형 템플릿

```sql
CREATE TABLE route_shapes (
    id VARCHAR(36) PRIMARY KEY,
    shape_id VARCHAR(50) UNIQUE NOT NULL,  -- 'heart', 'star' 등
    name VARCHAR(50) NOT NULL,              -- '하트', '별'
    icon_name VARCHAR(50) NOT NULL,         -- 'heart-outline'
    category VARCHAR(20) NOT NULL,          -- 'basic', 'special', 'fun'
    estimated_distance DECIMAL(5,2),        -- 예상 거리 (km)
    svg_template TEXT,                      -- SVG 경로 데이터
    is_active TINYINT DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**특징**:

- 하트, 별, 원 등 다양한 도형
- 카테고리별 분류
- is_active로 활성화 관리

#### 3. `routes` - 생성된 경로

```sql
CREATE TABLE routes (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    shape_id VARCHAR(36),
    name VARCHAR(100) NOT NULL,
    type VARCHAR(20) NOT NULL,          -- 'running', 'walking'
    mode VARCHAR(20) NOT NULL,          -- 'shape', 'custom'
    start_latitude DECIMAL(10,7) NOT NULL,
    start_longitude DECIMAL(10,7) NOT NULL,
    location_address VARCHAR(255),
    location_district VARCHAR(50),
    svg_path TEXT,               -- 사용자가 직접 그린 경로
    custom_points LONGTEXT,             -- JSON 형식 좌표
    condition VARCHAR(20),              -- 'distance', 'duration'
    intensity VARCHAR(20),              -- 'easy', 'normal', 'hard'
    target_duration INTEGER,
    safety_mode TINYINT DEFAULT 0,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (shape_id) REFERENCES route_shapes(id)
);
```

**특징**:

- GPS 좌표 저장 (DECIMAL(10,7) = 1cm 정확도)
- 도형 모드 / 커스텀 모드 지원
- 안전 모드 (야간 조명 경로 우선)

#### 4. `workouts` - 운동 기록

```sql
CREATE TABLE workouts (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    route_id VARCHAR(36),
    route_option_id VARCHAR(36),
    route_name VARCHAR(100) NOT NULL,
    type VARCHAR(20) NOT NULL,
    status VARCHAR(20) DEFAULT 'active',  -- 'active', 'paused', 'completed'
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    start_latitude DECIMAL(10,7) NOT NULL,
    start_longitude DECIMAL(10,7) NOT NULL,
    end_latitude DECIMAL(10,7),
    end_longitude DECIMAL(10,7),
    distance DECIMAL(5,2),              -- 실제 달린 거리
    duration INTEGER,                   -- 실제 소요 시간 (초)
    avg_pace VARCHAR(20),               -- 평균 페이스 (분:초/km)
    max_pace VARCHAR(20),
    min_pace VARCHAR(20),
    calories INTEGER,
    heart_rate_avg INTEGER,
    heart_rate_max INTEGER,
    elevation_gain INTEGER,             -- 고도 상승
    elevation_loss INTEGER,             -- 고도 하강
    route_completion DECIMAL(5,2),      -- 경로 완료율 (%)
    shape_accuracy DECIMAL(5,2),        -- 도형 정확도 (%)
    actual_path LONGTEXT,               -- 실제 달린 GPS 경로
    shape_id VARCHAR(50),
    shape_name VARCHAR(50),
    shape_icon VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (route_id) REFERENCES routes(id)
);
```

**특징**:

- 실시간 상태 관리 (active, paused, completed)
- 상세한 운동 통계
- 도형 정확도 계산

---

## 5. API 개발 흐름

### 🎓 API를 만드는 7단계

새로운 API를 추가할 때는 다음 순서를 따릅니다:

```
1. 요구사항 정의
   ↓
2. Schema 작성 (요청/응답 형식)
   ↓
3. Model 작성/수정 (필요시)
   ↓
4. Service 작성 (비즈니스 로직)
   ↓
5. Router 작성 (API 엔드포인트)
   ↓
6. Router 등록
   ↓
7. 테스트
```

### 📝 실제 예제: 사용자 프로필 조회 API

#### 1단계: 요구사항 정의

```
기능: 로그인한 사용자의 프로필 정보를 조회한다
입력: JWT 토큰 (Authorization 헤더)
출력: 사용자 정보 (이메일, 이름, 프로필 이미지 등)
권한: 로그인 필요
```

#### 2단계: Schema 작성

```python
# app/schemas/user.py

from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional

class UserResponse(BaseModel):
    """사용자 정보 응답"""
    id: str
    email: EmailStr
    name: str
    avatar: Optional[str] = None
    provider: Optional[str] = None
    created_at: datetime

    class Config:
        # ORM 모델을 Pydantic 모델로 변환 허용
        from_attributes = True

class UserStatsResponse(BaseModel):
    """사용자 통계 응답"""
    total_distance: float
    total_workouts: int
    completed_routes: int
    total_calories: int
    total_duration: int  # 초

    class Config:
        from_attributes = True
```

**핵심 포인트**:

- `BaseModel` 상속
- 타입 힌트로 자동 검증
- `Config.from_attributes = True`로 ORM 객체 변환

#### 3단계: Model 확인

```python
# app/models/user.py

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    avatar = Column(String(500))
    provider = Column(String(20))
    provider_id = Column(String(255))
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(TIMESTAMP, nullable=True)

    # 관계 설정
    stats = relationship("UserStats", back_populates="user", uselist=False)
    workouts = relationship("Workout", back_populates="user")
    routes = relationship("Route", back_populates="user")
```

**핵심 포인트**:

- `Base` 상속 (SQLAlchemy)
- `__tablename__`으로 테이블명 지정
- `relationship()`으로 다른 테이블과 관계 설정

#### 4단계: Service 작성

```python
# app/services/user_service.py

from sqlalchemy.orm import Session
from app.models.user import User, UserStats
from app.core.exceptions import NotFoundException

class UserService:
    def __init__(self, db: Session):
        self.db = db

    def get_user_by_id(self, user_id: str) -> User:
        """ID로 사용자 조회"""
        user = self.db.query(User).filter(
            User.id == user_id,
            User.deleted_at.is_(None)  # 삭제되지 않은 사용자만
        ).first()

        if not user:
            raise NotFoundException("사용자를 찾을 수 없습니다")

        return user

    def get_user_stats(self, user_id: str) -> UserStats:
        """사용자 통계 조회"""
        stats = self.db.query(UserStats).filter(
            UserStats.user_id == user_id
        ).first()

        if not stats:
            # 통계가 없으면 생성
            stats = UserStats(user_id=user_id)
            self.db.add(stats)
            self.db.commit()
            self.db.refresh(stats)

        return stats
```

**핵심 포인트**:

- DB 조작 로직을 Service로 분리
- 예외 처리 명확히
- `db.commit()` 잊지 말기

#### 5단계: Router 작성

```python
# app/api/v1/users.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.user import UserResponse, UserStatsResponse
from app.services.user_service import UserService

router = APIRouter()

@router.get(
    "/me",
    response_model=UserResponse,
    summary="내 프로필 조회",
    description="로그인한 사용자의 프로필 정보를 조회합니다"
)
async def get_my_profile(
    current_user: User = Depends(get_current_user)
):
    """
    내 프로필 조회 엔드포인트

    Args:
        current_user: 현재 로그인한 사용자 (자동 주입)

    Returns:
        UserResponse: 사용자 정보
    """
    return current_user


@router.get(
    "/me/stats",
    response_model=UserStatsResponse,
    summary="내 운동 통계 조회"
)
async def get_my_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """내 운동 통계 조회 엔드포인트"""
    user_service = UserService(db)
    stats = user_service.get_user_stats(current_user.id)
    return stats
```

**핵심 포인트**:

- `@router.get()` 데코레이터로 경로 정의
- `response_model`로 응답 형식 지정
- `summary`, `description`으로 자동 문서화
- `Depends()`로 의존성 주입

#### 6단계: Router 등록

```python
# app/api/v1/router.py

from fastapi import APIRouter
from app.api.v1 import users, auth, routes, workouts, community

api_router = APIRouter()

# 사용자 API 등록
api_router.include_router(
    users.router,
    prefix="/users",
    tags=["users"]  # Swagger UI에서 그룹화
)

# 다른 API들도 등록
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(routes.router, prefix="/routes", tags=["routes"])
# ...
```

#### 7단계: 테스트

```python
# 방법 1: Swagger UI에서 테스트
# http://localhost:8000/docs 접속
# "Try it out" 버튼 클릭

# 방법 2: curl로 테스트
curl -X GET "http://localhost:8000/api/v1/users/me" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

# 방법 3: Python requests로 테스트
import requests

response = requests.get(
    "http://localhost:8000/api/v1/users/me",
    headers={"Authorization": f"Bearer {access_token}"}
)
print(response.json())
```

---

## 6. 인증과 보안

### 🔐 JWT 토큰 구조

```
Header.Payload.Signature

예시:
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.    ← Header
eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.    ← Payload
SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c    ← Signature
```

### 🔑 비밀번호 해싱

```python
# app/core/security.py

from passlib.context import CryptContext

# bcrypt 사용 (가장 안전한 해싱 알고리즘 중 하나)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    """비밀번호를 bcrypt로 해싱"""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """비밀번호 검증"""
    return pwd_context.verify(plain_password, hashed_password)
```

**왜 bcrypt인가?**

- Salt 자동 추가 (레인보우 테이블 공격 방어)
- 느린 해싱 (브루트포스 공격 방어)
- 검증된 보안성

### 🚨 예외 처리

```python
# app/core/exceptions.py

from fastapi import HTTPException, status

class AuthenticationException(HTTPException):
    """인증 실패"""
    def __init__(self, message: str = "인증에 실패했습니다"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=message,
            headers={"WWW-Authenticate": "Bearer"}
        )

class NotFoundException(HTTPException):
    """리소스를 찾을 수 없음"""
    def __init__(self, message: str = "리소스를 찾을 수 없습니다"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=message
        )

class ValidationException(HTTPException):
    """입력 검증 실패"""
    def __init__(self, message: str, field: str = None):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": message,
                "field": field
            }
        )
```

**사용 예시**:

```python
# 사용자가 없을 때
if not user:
    raise NotFoundException("사용자를 찾을 수 없습니다")

# 이메일 중복일 때
if existing_user:
    raise ValidationException(
        message="이미 사용 중인 이메일입니다",
        field="email"
    )
```

---

## 7. 실전 기능 추가 예제

### 🎯 예제: "운동 목표 설정" 기능 추가

사용자가 주간/월간 운동 목표를 설정하고 진행률을 확인하는 기능을 추가해봅시다.

---

### ✅ Step 1: 요구사항 정의

```
기능명: 운동 목표 설정 및 조회
설명: 사용자가 거리 목표를 설정하고 달성률을 확인할 수 있다

API 목록:
1. POST /api/v1/goals - 목표 생성
2. GET /api/v1/goals - 내 목표 목록 조회
3. GET /api/v1/goals/{goal_id} - 목표 상세 조회
4. PATCH /api/v1/goals/{goal_id} - 목표 수정
5. DELETE /api/v1/goals/{goal_id} - 목표 삭제
6. GET /api/v1/goals/{goal_id}/progress - 목표 진행률 조회
```

---

### ✅ Step 2: 데이터베이스 테이블 설계

```sql
CREATE TABLE workout_goals (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    goal_type VARCHAR(20) NOT NULL,      -- 'weekly', 'monthly'
    target_type VARCHAR(20) NOT NULL,    -- 'distance', 'workouts', 'calories'
    target_value DECIMAL(10,2) NOT NULL, -- 목표 값
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    is_active TINYINT DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    INDEX idx_user_active (user_id, is_active)
);
```

---

### ✅ Step 3: Model 작성

```python
# app/models/workout.py (기존 파일에 추가)

from sqlalchemy import Column, String, DECIMAL, Date, TINYINT, ForeignKey
from sqlalchemy.orm import relationship
from app.db.database import Base
import uuid
from datetime import datetime

class WorkoutGoal(Base):
    """
    운동 목표 모델

    사용자가 설정한 운동 목표를 저장합니다.
    """
    __tablename__ = "workout_goals"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    goal_type = Column(String(20), nullable=False)      # 'weekly' or 'monthly'
    target_type = Column(String(20), nullable=False)    # 'distance', 'workouts', 'calories'
    target_value = Column(DECIMAL(10, 2), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    is_active = Column(TINYINT, default=1)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 관계 설정
    user = relationship("User", back_populates="goals")
```

---

### ✅ Step 4: Schema 작성

```python
# app/schemas/workout.py (새 파일 또는 기존 파일에 추가)

from pydantic import BaseModel, Field, validator
from datetime import date, datetime
from typing import Optional, Literal
from decimal import Decimal

class WorkoutGoalCreate(BaseModel):
    """운동 목표 생성 요청"""
    goal_type: Literal["weekly", "monthly"] = Field(
        description="목표 기간 (주간/월간)"
    )
    target_type: Literal["distance", "workouts", "calories"] = Field(
        description="목표 유형 (거리/운동횟수/칼로리)"
    )
    target_value: Decimal = Field(
        gt=0,
        description="목표 값"
    )
    start_date: date = Field(
        description="시작일"
    )
    end_date: date = Field(
        description="종료일"
    )

    @validator("end_date")
    def validate_end_date(cls, v, values):
        """종료일은 시작일보다 이후여야 함"""
        if "start_date" in values and v <= values["start_date"]:
            raise ValueError("종료일은 시작일보다 이후여야 합니다")
        return v


class WorkoutGoalUpdate(BaseModel):
    """운동 목표 수정 요청"""
    target_value: Optional[Decimal] = Field(None, gt=0)
    is_active: Optional[bool] = None


class WorkoutGoalResponse(BaseModel):
    """운동 목표 응답"""
    id: str
    user_id: str
    goal_type: str
    target_type: str
    target_value: Decimal
    start_date: date
    end_date: date
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WorkoutGoalProgressResponse(BaseModel):
    """운동 목표 진행률 응답"""
    goal: WorkoutGoalResponse
    current_value: Decimal                  # 현재 달성 값
    achievement_rate: Decimal               # 달성률 (%)
    remaining_value: Decimal                # 남은 목표
    remaining_days: int                     # 남은 일수
    is_completed: bool                      # 목표 달성 여부
    daily_average_needed: Optional[Decimal] # 하루 평균 필요량
```

---

### ✅ Step 5: Service 작성

```python
# app/services/workout_service.py (기존 파일에 추가)

from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from app.models.workout import WorkoutGoal, Workout
from app.schemas.workout import (
    WorkoutGoalCreate,
    WorkoutGoalUpdate,
    WorkoutGoalProgressResponse
)
from app.core.exceptions import NotFoundException, ValidationException
from datetime import date, timedelta
from decimal import Decimal
import uuid

class WorkoutGoalService:
    """운동 목표 서비스"""

    def __init__(self, db: Session):
        self.db = db

    def create_goal(self, user_id: str, request: WorkoutGoalCreate) -> WorkoutGoal:
        """
        운동 목표 생성

        Args:
            user_id: 사용자 ID
            request: 목표 생성 요청

        Returns:
            WorkoutGoal: 생성된 목표
        """
        # 같은 기간에 활성 목표가 있는지 확인
        existing = self.db.query(WorkoutGoal).filter(
            and_(
                WorkoutGoal.user_id == user_id,
                WorkoutGoal.goal_type == request.goal_type,
                WorkoutGoal.is_active == True,
                WorkoutGoal.start_date <= request.end_date,
                WorkoutGoal.end_date >= request.start_date
            )
        ).first()

        if existing:
            raise ValidationException(
                message="같은 기간에 활성화된 목표가 이미 존재합니다"
            )

        # 목표 생성
        goal = WorkoutGoal(
            id=str(uuid.uuid4()),
            user_id=user_id,
            **request.model_dump()
        )

        self.db.add(goal)
        self.db.commit()
        self.db.refresh(goal)

        return goal

    def get_user_goals(
        self,
        user_id: str,
        active_only: bool = True
    ) -> list[WorkoutGoal]:
        """
        사용자의 목표 목록 조회

        Args:
            user_id: 사용자 ID
            active_only: 활성 목표만 조회할지 여부

        Returns:
            list[WorkoutGoal]: 목표 목록
        """
        query = self.db.query(WorkoutGoal).filter(
            WorkoutGoal.user_id == user_id
        )

        if active_only:
            query = query.filter(WorkoutGoal.is_active == True)

        return query.order_by(WorkoutGoal.created_at.desc()).all()

    def get_goal_by_id(self, goal_id: str, user_id: str) -> WorkoutGoal:
        """
        목표 ID로 조회

        Args:
            goal_id: 목표 ID
            user_id: 사용자 ID

        Returns:
            WorkoutGoal: 목표 정보
        """
        goal = self.db.query(WorkoutGoal).filter(
            and_(
                WorkoutGoal.id == goal_id,
                WorkoutGoal.user_id == user_id
            )
        ).first()

        if not goal:
            raise NotFoundException("목표를 찾을 수 없습니다")

        return goal

    def update_goal(
        self,
        goal_id: str,
        user_id: str,
        request: WorkoutGoalUpdate
    ) -> WorkoutGoal:
        """
        목표 수정

        Args:
            goal_id: 목표 ID
            user_id: 사용자 ID
            request: 수정 요청

        Returns:
            WorkoutGoal: 수정된 목표
        """
        goal = self.get_goal_by_id(goal_id, user_id)

        # 수정할 필드 적용
        for field, value in request.model_dump(exclude_unset=True).items():
            setattr(goal, field, value)

        self.db.commit()
        self.db.refresh(goal)

        return goal

    def delete_goal(self, goal_id: str, user_id: str):
        """
        목표 삭제

        Args:
            goal_id: 목표 ID
            user_id: 사용자 ID
        """
        goal = self.get_goal_by_id(goal_id, user_id)
        self.db.delete(goal)
        self.db.commit()

    def get_goal_progress(
        self,
        goal_id: str,
        user_id: str
    ) -> WorkoutGoalProgressResponse:
        """
        목표 진행률 조회

        Args:
            goal_id: 목표 ID
            user_id: 사용자 ID

        Returns:
            WorkoutGoalProgressResponse: 진행률 정보
        """
        goal = self.get_goal_by_id(goal_id, user_id)

        # 목표 기간 내 운동 데이터 집계
        current_value = self._calculate_current_value(goal)

        # 달성률 계산
        achievement_rate = (current_value / goal.target_value * 100) if goal.target_value > 0 else 0

        # 남은 목표
        remaining_value = max(goal.target_value - current_value, 0)

        # 남은 일수
        today = date.today()
        remaining_days = (goal.end_date - today).days + 1
        remaining_days = max(remaining_days, 0)

        # 목표 달성 여부
        is_completed = current_value >= goal.target_value

        # 하루 평균 필요량
        daily_average_needed = None
        if remaining_days > 0 and not is_completed:
            daily_average_needed = remaining_value / remaining_days

        return WorkoutGoalProgressResponse(
            goal=goal,
            current_value=current_value,
            achievement_rate=round(achievement_rate, 2),
            remaining_value=remaining_value,
            remaining_days=remaining_days,
            is_completed=is_completed,
            daily_average_needed=daily_average_needed
        )

    def _calculate_current_value(self, goal: WorkoutGoal) -> Decimal:
        """
        목표 기간 내 현재 달성 값 계산

        Args:
            goal: 목표 정보

        Returns:
            Decimal: 현재 달성 값
        """
        query = self.db.query(Workout).filter(
            and_(
                Workout.user_id == goal.user_id,
                Workout.status == "completed",
                func.date(Workout.started_at) >= goal.start_date,
                func.date(Workout.started_at) <= goal.end_date
            )
        )

        if goal.target_type == "distance":
            # 총 거리 합계
            result = query.with_entities(
                func.sum(Workout.distance)
            ).scalar()
            return Decimal(result or 0)

        elif goal.target_type == "workouts":
            # 운동 횟수
            count = query.count()
            return Decimal(count)

        elif goal.target_type == "calories":
            # 총 칼로리 합계
            result = query.with_entities(
                func.sum(Workout.calories)
            ).scalar()
            return Decimal(result or 0)

        return Decimal(0)
```

---

### ✅ Step 6: Router 작성

```python
# app/api/v1/goals.py (새 파일)

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.workout import (
    WorkoutGoalCreate,
    WorkoutGoalUpdate,
    WorkoutGoalResponse,
    WorkoutGoalProgressResponse
)
from app.schemas.common import CommonResponse
from app.services.workout_service import WorkoutGoalService

router = APIRouter()


@router.post(
    "",
    response_model=CommonResponse[WorkoutGoalResponse],
    status_code=status.HTTP_201_CREATED,
    summary="운동 목표 생성",
    description="새로운 운동 목표를 생성합니다"
)
async def create_goal(
    request: WorkoutGoalCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    운동 목표 생성 엔드포인트

    **목표 유형**:
    - weekly: 주간 목표
    - monthly: 월간 목표

    **목표 타입**:
    - distance: 거리 (km)
    - workouts: 운동 횟수
    - calories: 칼로리 (kcal)
    """
    service = WorkoutGoalService(db)
    goal = service.create_goal(current_user.id, request)

    return CommonResponse(
        success=True,
        data=goal,
        message="목표가 생성되었습니다"
    )


@router.get(
    "",
    response_model=CommonResponse[List[WorkoutGoalResponse]],
    summary="내 목표 목록 조회"
)
async def get_my_goals(
    active_only: bool = True,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    내 목표 목록 조회 엔드포인트

    Args:
        active_only: True면 활성 목표만, False면 모든 목표
    """
    service = WorkoutGoalService(db)
    goals = service.get_user_goals(current_user.id, active_only)

    return CommonResponse(
        success=True,
        data=goals
    )


@router.get(
    "/{goal_id}",
    response_model=CommonResponse[WorkoutGoalResponse],
    summary="목표 상세 조회"
)
async def get_goal_detail(
    goal_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """목표 상세 조회 엔드포인트"""
    service = WorkoutGoalService(db)
    goal = service.get_goal_by_id(goal_id, current_user.id)

    return CommonResponse(
        success=True,
        data=goal
    )


@router.patch(
    "/{goal_id}",
    response_model=CommonResponse[WorkoutGoalResponse],
    summary="목표 수정"
)
async def update_goal(
    goal_id: str,
    request: WorkoutGoalUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """목표 수정 엔드포인트"""
    service = WorkoutGoalService(db)
    goal = service.update_goal(goal_id, current_user.id, request)

    return CommonResponse(
        success=True,
        data=goal,
        message="목표가 수정되었습니다"
    )


@router.delete(
    "/{goal_id}",
    response_model=CommonResponse,
    summary="목표 삭제"
)
async def delete_goal(
    goal_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """목표 삭제 엔드포인트"""
    service = WorkoutGoalService(db)
    service.delete_goal(goal_id, current_user.id)

    return CommonResponse(
        success=True,
        message="목표가 삭제되었습니다"
    )


@router.get(
    "/{goal_id}/progress",
    response_model=CommonResponse[WorkoutGoalProgressResponse],
    summary="목표 진행률 조회"
)
async def get_goal_progress(
    goal_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    목표 진행률 조회 엔드포인트

    현재 달성 값, 달성률, 남은 일수 등을 반환합니다.
    """
    service = WorkoutGoalService(db)
    progress = service.get_goal_progress(goal_id, current_user.id)

    return CommonResponse(
        success=True,
        data=progress
    )
```

---

### ✅ Step 7: Router 등록

```python
# app/api/v1/router.py (기존 파일 수정)

from fastapi import APIRouter
from app.api.v1 import auth, users, routes, workouts, community, goals  # goals 추가

api_router = APIRouter()

# 기존 라우터들...
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(routes.router, prefix="/routes", tags=["routes"])
api_router.include_router(workouts.router, prefix="/workouts", tags=["workouts"])
api_router.include_router(community.router, prefix="/community", tags=["community"])

# 새로운 목표 API 추가
api_router.include_router(goals.router, prefix="/goals", tags=["goals"])
```

---

### ✅ Step 8: 데이터베이스 마이그레이션

```sql
-- scripts/migrations/add_workout_goals.sql

-- 1. 테이블 생성
CREATE TABLE workout_goals (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    goal_type VARCHAR(20) NOT NULL,
    target_type VARCHAR(20) NOT NULL,
    target_value DECIMAL(10,2) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    is_active TINYINT DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_active (user_id, is_active),
    INDEX idx_dates (start_date, end_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. 테스트 데이터 삽입 (선택사항)
-- INSERT INTO workout_goals ...
```

실행:

```sh
# MariaDB 접속 후
mysql -h runnerway-back.xxx.rds.amazonaws.com -u member -p runnerway < scripts/migrations/add_workout_goals.sql
```

---

### ✅ Step 9: 테스트

#### 1. Swagger UI로 테스트

```
1. http://localhost:8000/docs 접속
2. /api/v1/auth/login 으로 로그인 → 토큰 받기
3. 우측 상단 "Authorize" 버튼 클릭 → 토큰 입력
4. /api/v1/goals 엔드포인트 테스트
```

#### 2. curl로 테스트

```sh
# 1. 목표 생성
curl -X POST "http://localhost:8000/api/v1/goals" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "goal_type": "weekly",
    "target_type": "distance",
    "target_value": 20,
    "start_date": "2026-01-27",
    "end_date": "2026-02-02"
  }'

# 2. 목표 목록 조회
curl -X GET "http://localhost:8000/api/v1/goals" \
  -H "Authorization: Bearer YOUR_TOKEN"

# 3. 진행률 조회
curl -X GET "http://localhost:8000/api/v1/goals/{goal_id}/progress" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### 3. Python으로 테스트

```python
import requests

BASE_URL = "http://localhost:8000/api/v1"
TOKEN = "your_access_token_here"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

# 목표 생성
response = requests.post(
    f"{BASE_URL}/goals",
    headers=headers,
    json={
        "goal_type": "weekly",
        "target_type": "distance",
        "target_value": 20,
        "start_date": "2026-01-27",
        "end_date": "2026-02-02"
    }
)
print("목표 생성:", response.json())

goal_id = response.json()["data"]["id"]

# 진행률 조회
response = requests.get(
    f"{BASE_URL}/goals/{goal_id}/progress",
    headers=headers
)
print("진행률:", response.json())
```

---

## 8. 테스트와 디버깅

### 🐛 디버깅 팁

#### 1. SQL 쿼리 로그 확인

```python
# app/db/database.py

engine = create_engine(
    settings.DATABASE_URL,
    echo=True  # ← 이 옵션으로 SQL 쿼리 출력
)
```

실행 로그:

```
INFO sqlalchemy.engine.Engine SELECT users.id, users.email, users.name ...
INFO sqlalchemy.engine.Engine [generated in 0.00054s] {'user_id_1': 'abc123'}
```

#### 2. print 디버깅

```python
@router.post("/test")
async def test_endpoint(request: SomeRequest):
    print(f"받은 요청: {request}")  # ← 콘솔에 출력
    print(f"요청 타입: {type(request)}")

    # 로직...

    print(f"결과: {result}")
    return result
```

#### 3. Pydantic 검증 오류 확인

```python
from pydantic import ValidationError

try:
    user = UserCreate(**data)
except ValidationError as e:
    print(e.json())  # 어떤 필드가 잘못되었는지 상세히 출력
```

#### 4. 데이터베이스 쿼리 디버깅

```python
# 쿼리만 출력하고 실행하지 않기
query = db.query(User).filter(User.email == email)
print(str(query))  # SQL 문 출력

# 실제 실행
user = query.first()
```

### 🧪 단위 테스트 (pytest)

```python
# tests/test_goals.py

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_create_goal():
    """목표 생성 테스트"""
    # 1. 로그인
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "test@test.com",
            "password": "password123"
        }
    )
    token = login_response.json()["data"]["access_token"]

    # 2. 목표 생성
    response = client.post(
        "/api/v1/goals",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "goal_type": "weekly",
            "target_type": "distance",
            "target_value": 20,
            "start_date": "2026-01-27",
            "end_date": "2026-02-02"
        }
    )

    # 3. 검증
    assert response.status_code == 201
    assert response.json()["success"] == True
    assert response.json()["data"]["target_value"] == 20

def test_get_goal_progress():
    """진행률 조회 테스트"""
    # 테스트 코드...
```

실행:

```sh
pytest tests/test_goals.py -v
```

---

## 9. 배포 준비

### 🚀 배포 체크리스트

#### 1. 환경 변수 보안

```sh
# .env 파일을 절대 Git에 올리지 말 것!
# .gitignore에 추가
echo ".env" >> .gitignore
```

#### 2. SECRET_KEY 변경

```python
# 운영 환경에서는 강력한 SECRET_KEY 사용
import secrets
print(secrets.token_urlsafe(32))
# → 'Xhg3K2pQ_vN7mR8sT9wUyZaB1cD0eF2gH4iJ5kL6'
```

#### 3. CORS 설정

```python
# 운영 환경에서는 실제 도메인만 허용
CORS_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
```

#### 4. 데이터베이스 연결 풀 설정

```python
# app/db/database.py

engine = create_engine(
    settings.DATABASE_URL,
    pool_size=10,              # 기본 연결 수
    max_overflow=20,           # 최대 추가 연결 수
    pool_pre_ping=True,        # 연결 상태 체크
    pool_recycle=3600,         # 1시간마다 연결 재생성
    echo=False                 # 운영에서는 SQL 로그 끄기
)
```

#### 5. Gunicorn으로 실행

```sh
# requirements.txt에 추가
gunicorn==21.2.0

# 실행
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 60
```

#### 6. 로깅 설정

```python
# app/main.py

import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
```

---

## 10. 자주 하는 실수와 해결책

### ❌ 실수 1: commit() 잊어버리기

```python
# 잘못된 코드
def create_user(db: Session, user_data):
    user = User(**user_data)
    db.add(user)
    # db.commit() ← 없음!
    return user  # DB에 저장 안 됨!

# 올바른 코드
def create_user(db: Session, user_data):
    user = User(**user_data)
    db.add(user)
    db.commit()
    db.refresh(user)  # DB에서 최신 데이터 가져오기
    return user
```

### ❌ 실수 2: 순환 import

```python
# user.py
from app.models.workout import Workout  # ← 순환 import!

class User(Base):
    workouts = relationship("Workout")

# workout.py
from app.models.user import User  # ← 순환 import!

class Workout(Base):
    user = relationship("User")
```

**해결책**: 문자열로 참조

```python
# user.py
class User(Base):
    workouts = relationship("Workout")  # 문자열로!

# workout.py
class Workout(Base):
    user = relationship("User")  # 문자열로!
```

### ❌ 실수 3: 예외 처리 안 하기

```python
# 잘못된 코드
@router.get("/users/{user_id}")
async def get_user(user_id: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    return user  # user가 None이면 클라이언트는 null 받음

# 올바른 코드
@router.get("/users/{user_id}")
async def get_user(user_id: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundException("사용자를 찾을 수 없습니다")
    return user
```

### ❌ 실수 4: 비밀번호 평문 저장

```python
# 절대 하지 말 것!
user.password = "password123"  # 평문 저장!

# 올바른 코드
from app.core.security import hash_password
user.password_hash = hash_password("password123")
```

---

## 11. 추가 학습 자료

### 📖 공식 문서

- FastAPI: https://fastapi.tiangolo.com/
- SQLAlchemy: https://docs.sqlalchemy.org/
- Pydantic: https://docs.pydantic.dev/

### 🎥 추천 강의

- FastAPI 공식 튜토리얼
- Real Python - FastAPI 시리즈
- SQLAlchemy 2.0 마이그레이션 가이드

### 💡 연습 문제

1. **난이도 ★**: "좋아요" 기능 추가하기
2. **난이도 ★★**: 페이지네이션 구현하기
3. **난이도 ★★★**: 실시간 알림 기능 (WebSocket)
4. **난이도 ★★★★**: 파일 업로드 (프로필 이미지)
5. **난이도 ★★★★★**: 캐싱 시스템 (Redis)

---

## 12. 마무리

### 🎓 배운 내용 요약

1. ✅ FastAPI 프로젝트 구조
2. ✅ SQLAlchemy ORM 사용법
3. ✅ Pydantic으로 데이터 검증
4. ✅ JWT 인증 구현
5. ✅ RESTful API 설계
6. ✅ 의존성 주입 패턴
7. ✅ 예외 처리 및 에러 핸들링
8. ✅ 실전 기능 추가 (목표 관리)

### 💪 다음 단계

1. **실전 프로젝트 만들기**: 직접 API 추가해보기
2. **테스트 코드 작성**: pytest로 단위 테스트
3. **성능 최적화**: 캐싱, 쿼리 최적화
4. **배포하기**: AWS, Docker, CI/CD

---

## 📞 도움이 필요하면?

- 🐛 버그 발견: GitHub Issues
- 💬 질문: GitHub Discussions
- 📧 이메일: dev@runnerway.com

---

**이 가이드가 도움이 되었나요? ⭐ 스타를 눌러주세요!**

Made with ❤️ by RunnerWay Team