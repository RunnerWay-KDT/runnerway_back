# 러너웨이 백엔드 (RunnerWay Backend)

> 🏃‍♂️ 러너웨이 - 나만의 그림 경로로 러닝을 시작하세요!

## 📁 프로젝트 구조

```
runnerway_back/
│
├── app/                          # 메인 애플리케이션 폴더
│   ├── __init__.py              # 패키지 초기화 파일
│   ├── main.py                  # FastAPI 앱 시작점 (가장 먼저 보세요!)
│   ├── config.py                # 환경 설정 (DB 연결, API 키 등)
│   │
│   ├── api/                     # API 엔드포인트 모음
│   │   ├── __init__.py
│   │   ├── v1/                  # API 버전 1
│   │   │   ├── __init__.py
│   │   │   ├── router.py        # 모든 라우터를 모아놓은 파일
│   │   │   ├── auth.py          # 인증 관련 API (로그인, 회원가입)
│   │   │   ├── users.py         # 사용자 관련 API
│   │   │   ├── routes.py        # 경로 생성 관련 API
│   │   │   ├── workouts.py      # 운동 관련 API
│   │   │   ├── community.py     # 커뮤니티 관련 API
│   │   │   └── recommendations.py  # 추천 관련 API
│   │   └── deps.py              # API 의존성 (인증 체크 등)
│   │
│   ├── core/                    # 핵심 기능 모음
│   │   ├── __init__.py
│   │   ├── security.py          # 보안 관련 (JWT 토큰, 비밀번호 해싱)
│   │   └── exceptions.py        # 커스텀 예외 처리
│   │
│   ├── models/                  # 데이터베이스 모델 (테이블 정의)
│   │   ├── __init__.py
│   │   ├── user.py              # 사용자 관련 테이블
│   │   ├── route.py             # 경로 관련 테이블
│   │   ├── workout.py           # 운동 관련 테이블
│   │   └── community.py         # 커뮤니티 관련 테이블
│   │
│   ├── schemas/                 # Pydantic 스키마 (요청/응답 형식 정의)
│   │   ├── __init__.py
│   │   ├── auth.py              # 인증 관련 스키마
│   │   ├── user.py              # 사용자 관련 스키마
│   │   ├── route.py             # 경로 관련 스키마
│   │   ├── workout.py           # 운동 관련 스키마
│   │   └── community.py         # 커뮤니티 관련 스키마
│   │
│   ├── services/                # 비즈니스 로직 (실제 기능 구현)
│   │   ├── __init__.py
│   │   ├── auth_service.py      # 인증 서비스
│   │   ├── user_service.py      # 사용자 서비스
│   │   ├── route_service.py     # 경로 서비스
│   │   ├── workout_service.py   # 운동 서비스
│   │   ├── community_service.py # 커뮤니티 서비스
│   │   └── kakao_service.py     # 카카오 API 연동 서비스
│   │
│   └── db/                      # 데이터베이스 관련
│       ├── __init__.py
│       ├── database.py          # DB 연결 설정
│       └── init_db.py           # DB 초기화
│
├── requirements.txt             # 필요한 패키지 목록
├── .env.example                 # 환경 변수 예시 파일
└── README.md                    # 이 파일!
```

## 🚀 시작하기

### 1. 가상환경 생성 및 활성화

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Mac/Linux
python3 -m venv venv
source venv/bin/activate
```

### 2. 패키지 설치

```bash
pip install -r requirements.txt
```

### 3. 환경 변수 설정

`.env.example` 파일을 복사해서 `.env` 파일을 만들고, 값을 채워주세요.

```bash
copy .env.example .env
```

### 4. 데이터베이스 초기화 및 시드 데이터

```bash
# 테이블 생성 및 초기 데이터 삽입
python scripts/seed_data.py
```

### 5. 서버 실행

```bash
# 개발 모드 (코드 변경 시 자동 재시작)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 6. API 문서 확인

서버 실행 후 브라우저에서:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 📚 신입 개발자를 위한 학습 순서

1. **`app/main.py`** - FastAPI 앱이 어떻게 시작되는지 확인
2. **`app/config.py`** - 환경 설정이 어떻게 관리되는지 확인
3. **`app/models/`** - 데이터베이스 테이블 구조 이해
4. **`app/schemas/`** - API 요청/응답 형식 이해
5. **`app/api/v1/`** - 실제 API 엔드포인트 확인
6. **`app/services/`** - 비즈니스 로직 이해

## 🔑 주요 기능

### 인증 API (`/api/v1/auth`)

- `POST /signup` - 회원가입
- `POST /login` - 이메일 로그인
- `POST /social/kakao` - 카카오 소셜 로그인
- `POST /refresh` - 토큰 갱신
- `POST /logout` - 로그아웃

### 사용자 API (`/api/v1/users`)

- `GET /me` - 내 프로필 조회
- `PATCH /me` - 프로필 수정
- `DELETE /me` - 회원 탈퇴
- `GET /me/workouts` - 내 운동 기록
- `GET /me/saved-routes` - 저장한 경로
- `GET /me/statistics` - 통계 대시보드

### 경로 API (`/api/v1/routes`)

- `POST /generate` - 경로 생성 요청
- `GET /generate/{task_id}` - 생성 상태 조회
- `GET /{route_id}/options` - 경로 옵션 조회
- `GET /{route_id}/options/{option_id}` - 상세 조회
- `POST /{route_id}/save` - 경로 저장
- `DELETE /{route_id}/save` - 저장 취소
- `GET /shapes` - 모양 템플릿 목록

### 운동 API (`/api/v1/workouts`)

- `POST /start` - 운동 시작
- `POST /{id}/track` - 실시간 트래킹
- `POST /{id}/pause` - 일시정지
- `POST /{id}/resume` - 재개
- `POST /{id}/complete` - 운동 완료
- `DELETE /{id}` - 운동 취소
- `GET /{id}` - 운동 상세 조회

### 커뮤니티 API (`/api/v1/community`)

- `GET /feed` - 피드 조회
- `POST /posts` - 게시글 작성
- `GET /posts/{id}` - 상세 조회
- `PATCH /posts/{id}` - 수정
- `DELETE /posts/{id}` - 삭제
- `POST /posts/{id}/like` - 좋아요
- `POST /posts/{id}/bookmark` - 북마크
- `POST /posts/{id}/comments` - 댓글 작성
- `POST /users/{id}/follow` - 팔로우

## 🗄️ 데이터베이스

- **DBMS**: MariaDB (AWS RDS)
- **ORM**: SQLAlchemy
- **마이그레이션**: Alembic (추후 추가 예정)

### 주요 테이블

- `users` - 사용자 정보
- `user_stats` - 사용자 통계
- `refresh_tokens` - 리프레시 토큰
- `shapes` - 모양 템플릿
- `routes` - 생성된 경로
- `route_options` - 경로 옵션
- `saved_routes` - 저장된 경로
- `workouts` - 운동 기록
- `workout_tracks` - 운동 트래킹 데이터
- `posts` - 커뮤니티 게시글
- `comments` - 댓글
- `follows` - 팔로우 관계

## 📝 코딩 컨벤션

- 변수명/함수명: `snake_case`
- 클래스명: `PascalCase`
- 상수: `UPPER_SNAKE_CASE`
- 모든 함수에 타입 힌트 사용
- 중요한 로직에는 반드시 주석 작성

## 🔧 개발 시 참고사항

### 새로운 API 추가 시

1. `schemas/`에 요청/응답 스키마 정의
2. `models/`에 필요한 모델 추가
3. `services/`에 비즈니스 로직 구현
4. `api/v1/`에 엔드포인트 추가
5. `api/v1/router.py`에 라우터 등록

### 환경 변수 추가 시

1. `.env.example`에 예시 추가
2. `config.py`에 설정 클래스 수정
3. README에 설명 추가

---

Made with ❤️ by RunnerWay Team
