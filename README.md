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
│   │   │   ├── auth.py          # 인증 관련 API (회원가입, 로그인)
│   │   │   ├── users.py         # 사용자 관련 API
│   │   │   ├── routes.py        # 경로 생성 관련 API
│   │   │   ├── workouts.py      # 운동 관련 API
│   │   │   └── community.py     # 커뮤니티 관련 API
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
│   │   ├── community.py         # 커뮤니티 관련 스키마
│   │   └── common.py            # 공통 스키마
│   │
│   ├── services/                # 비즈니스 로직 (실제 기능 구현)
│   │   ├── __init__.py
│   │   ├── auth_service.py      # 인증 서비스
│   │   ├── route_service.py     # 경로 서비스
│   │   ├── workout_service.py   # 운동 서비스
│   │   ├── community_service.py # 커뮤니티 서비스
│   │   └── kakao_service.py     # 카카오 맵 API 서비스
│   │
│   └── db/                      # 데이터베이스 관련
│       ├── __init__.py
│       └── database.py          # DB 연결 설정
│
├── scripts/                     # 유틸리티 스크립트
│   └── check_db.py             # DB 연결 테스트
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

### 3. 서버 실행

```bash
# 개발 모드 (코드 변경 시 자동 재시작)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. API 문서 확인

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

- `POST /signup` - 회원가입 (이메일/비밀번호)
- `POST /login` - 로그인
- `POST /refresh` - 액세스 토큰 갱신
- `POST /logout` - 로그아웃

### 사용자 API (`/api/v1/users`)

- `GET /me` - 내 프로필 조회
- `PATCH /me` - 프로필 수정
- `DELETE /me` - 회원 탈퇴
- `GET /me/workouts` - 내 운동 기록 목록
- `GET /me/saved-routes` - 저장한 경로 목록

### 경로 API (`/api/v1/routes`)

- `POST /generate` - 경로 생성 요청 (비동기)
- `GET /generate/{task_id}` - 경로 생성 상태 조회
- `GET /{route_id}/options` - 경로 옵션 목록 조회 (3개)
- `GET /{route_id}/options/{option_id}` - 옵션 상세 조회
- `POST /{route_id}/save` - 경로 저장
- `DELETE /saved-routes/{saved_route_id}` - 저장 취소
- `GET /shapes` - 모양 템플릿 목록

### 운동 API (`/api/v1/workouts`)

- `POST /start` - 운동 시작
- `POST /{id}/track` - 실시간 위치 트래킹
- `POST /{id}/pause` - 일시정지
- `POST /{id}/resume` - 재개
- `POST /{id}/complete` - 운동 완료
- `DELETE /{id}` - 운동 취소
- `GET /{id}` - 운동 상세 조회
- `GET /current/status` - 현재 진행 중인 운동 확인

### 커뮤니티 API (`/api/v1/community`)

- `GET /feed` - 피드 조회 (최신순/인기순/트렌딩)
- `POST /posts` - 게시글 작성
- `GET /posts/{id}` - 게시글 상세 조회
- `PATCH /posts/{id}` - 게시글 수정
- `DELETE /posts/{id}` - 게시글 삭제
- `POST /posts/{id}/like` - 좋아요
- `DELETE /posts/{id}/like` - 좋아요 취소
- `POST /posts/{id}/bookmark` - 북마크
- `DELETE /posts/{id}/bookmark` - 북마크 취소
- `POST /posts/{id}/comments` - 댓글 작성
- `DELETE /comments/{id}` - 댓글 삭제
- `POST /comments/{id}/like` - 댓글 좋아요
- `GET /bookmarks` - 내 북마크 목록

## 🗄️ 데이터베이스

- **DBMS**: MariaDB
- **ORM**: SQLAlchemy 2.0
- **마이그레이션**: 수동 관리 (Alembic 추후 도입 예정)

### 주요 테이블

**사용자 관련:**

- `users` - 사용자 기본 정보 (이메일, 이름, 프로필 이미지 등)
- `user_stats` - 사용자 통계 (총 거리, 운동 횟수, 완주 경로 수)
- `user_settings` - 사용자 설정 (다크모드, 자동랩 등)
- `emergency_contacts` - 긴급 연락처
- `refresh_tokens` - JWT 리프레시 토큰

**경로 관련:**

- `route_shapes` - 모양 템플릿 (하트, 별, 원 등)
- `routes` - 생성된 경로
- `route_options` - 경로 옵션 (안전 우선, 균형, 경치 우선 등 3가지)
- `saved_routes` - 사용자가 저장한 경로
- `route_generation_tasks` - 경로 생성 비동기 작업
- `places` - 주변 장소 정보
- `recommended_routes` - 추천 경로

**운동 관련:**

- `workouts` - 운동 기록 (거리, 시간, 칼로리, 경로 데이터 등)
- `workout_splits` - 구간별 기록 (1km, 2km, ...)

- 각 파일 상단에 파일 설명 주석 작성

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

## 🚨 주요 변경사항 (v2.0)

- ✅ 이메일/비밀번호 로그인만 지원 (카카오 소셜 로그인 제거)
- ✅ 뱃지/업적 시스템 제거
- ✅ 팔로우 기능 제거
- ✅ 운동 트래킹 데이터를 `workouts.path_data` JSON 필드로 통합
- ✅ 경유지(waypoints) 테이블 제거
- ✅ 필드명 변경: `avatar` → `avatar_url`, `svg_template` → `svg_url`
- ✅ UserStats 간소화: `total_calories`, `total_duration` 제거

## 🐛 디버깅

### DB 연결 테스트

```bash
python scripts/check_db.py
```

### 로그 확인

```bash
# 앱 로그는 콘솔에 출력됨
# 필요시 파일 로깅 추가 가능
```

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
