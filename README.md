# 러너웨이 백엔드 (RunnerWay Backend)

원하는 도형 모양으로 러닝 경로를 만들어주는 앱 **러너웨이**의 백엔드 서버입니다.

사용자가 하트, 별 같은 도형을 선택하면 실제 도로 위에 해당 모양의 러닝 코스를 생성해주고, GPS로 운동을 추적하고, 결과를 커뮤니티에 공유할 수 있습니다.

## 기술 스택

- **Python 3.12+** / **FastAPI**
- **SQLAlchemy 2.0** + **MariaDB**
- **JWT** 인증 (카카오 소셜 로그인 지원)
- **OSMnx** + **NetworkX** — OpenStreetMap 도로 네트워크 기반 경로 생성
- **OpenCV** — SVG 경로 단순화 (Douglas-Peucker)

## 프로젝트 구조

```
app/
├── main.py              # FastAPI 앱 진입점
├── config.py            # 환경 설정 (.env 기반)
├── api/v1/              # API 엔드포인트
│   ├── auth.py          # 회원가입, 로그인, 토큰 갱신
│   ├── users.py         # 프로필, 통계, 설정
│   ├── routes.py        # 경로 생성 / 저장 / 조회
│   ├── workouts.py      # 운동 시작 / 완료 / 기록
│   └── community.py     # 피드, 좋아요, 댓글, 북마크
├── models/              # DB 테이블 정의 (SQLAlchemy)
├── schemas/             # 요청/응답 스키마 (Pydantic)
├── services/            # 비즈니스 로직
├── core/                # JWT, 비밀번호 해싱, 예외 처리
├── db/                  # DB 연결 설정
├── gps_art/             # GPS 아트 경로 생성 엔진
└── utils/               # 기하 계산, SVG 처리 등 유틸
```

## 주요 기능

### 경로 생성 (GPS Art)

도형 템플릿이나 직접 그린 SVG를 기반으로 실제 도로 위 러닝 경로를 생성합니다. OSMnx로 주변 도로 네트워크를 가져오고, A\* 알고리즘으로 도형과 유사한 경로를 탐색합니다. 비동기로 처리되어 task_id로 결과를 폴링합니다.

### 운동 추적

운동 시작 → 실시간 GPS 기록 → 완료 흐름을 지원합니다. km 단위 구간(split) 기록, 페이스/칼로리/고도 등 통계를 저장합니다.

### 커뮤니티

운동 결과를 게시글로 공유하고 좋아요, 댓글, 북마크 기능을 제공합니다. 최신순/인기순/트렌딩 정렬을 지원합니다.

### 인증

이메일/비밀번호 회원가입과 카카오 소셜 로그인을 지원합니다. JWT Access Token + Refresh Token 방식입니다.

## 시작하기

### 1. 패키지 설치

```bash
pip install -r requirements.txt
```

### 2. 환경 변수 설정

`.env` 파일을 프로젝트 루트에 생성합니다.

```env
SECRET_KEY=your-secret-key
DB_HOST=localhost
DB_PORT=3306
DB_NAME=runnerway
DB_USER=root
DB_PASSWORD=your-password
KAKAO_CLIENT_ID=your-kakao-key
```

### 3. 서버 실행

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

실행 후 [http://localhost:8000/docs](http://localhost:8000/docs)에서 Swagger API 문서를 확인할 수 있습니다.

## API 엔드포인트

### 인증 `/api/v1/auth`

| 메서드 | 경로       | 설명             |
| ------ | ---------- | ---------------- |
| POST   | `/signup`  | 회원가입         |
| POST   | `/login`   | 이메일 로그인    |
| POST   | `/refresh` | 액세스 토큰 갱신 |
| POST   | `/logout`  | 로그아웃         |

### 사용자 `/api/v1/users`

| 메서드 | 경로               | 설명              |
| ------ | ------------------ | ----------------- |
| GET    | `/me`              | 내 프로필 조회    |
| PATCH  | `/me`              | 프로필 수정       |
| DELETE | `/me`              | 회원 탈퇴         |
| GET    | `/me/workouts`     | 내 운동 기록 목록 |
| GET    | `/me/saved-routes` | 저장한 경로 목록  |
| GET    | `/me/settings`     | 앱 설정 조회      |
| PATCH  | `/me/settings`     | 앱 설정 수정      |

### 경로 `/api/v1/routes`

| 메서드 | 경로                              | 설명                    |
| ------ | --------------------------------- | ----------------------- |
| POST   | `/generate`                       | 경로 생성 요청 (비동기) |
| GET    | `/generate/{task_id}`             | 경로 생성 상태 조회     |
| GET    | `/{route_id}/options`             | 경로 옵션 목록 조회     |
| GET    | `/{route_id}/options/{option_id}` | 경로 옵션 상세 조회     |
| PATCH  | `/{route_id}/name`                | 경로 이름 수정          |
| POST   | `/{route_id}/save`                | 경로 저장 (북마크)      |
| DELETE | `/{route_id}/save`                | 경로 저장 취소          |
| GET    | `/shapes`                         | 도형 템플릿 목록        |

### 운동 `/api/v1/workouts`

| 메서드 | 경로                     | 설명                |
| ------ | ------------------------ | ------------------- |
| POST   | `/start`                 | 운동 시작           |
| POST   | `/{workout_id}/complete` | 운동 완료           |
| POST   | `/{workout_id}/pause`    | 운동 일시정지       |
| POST   | `/{workout_id}/resume`   | 운동 재개           |
| GET    | `/{workout_id}`          | 운동 상세 조회      |
| DELETE | `/{workout_id}`          | 운동 취소           |
| DELETE | `/{workout_id}/record`   | 운동 기록 삭제      |
| GET    | `/current/status`        | 현재 진행 중인 운동 |

### 커뮤니티 `/api/v1/community`

| 메서드 | 경로                    | 설명             |
| ------ | ----------------------- | ---------------- |
| GET    | `/feed`                 | 피드 조회        |
| POST   | `/posts`                | 게시글 작성      |
| GET    | `/posts/{post_id}`      | 게시글 상세 조회 |
| PATCH  | `/posts/{post_id}`      | 게시글 수정      |
| DELETE | `/posts/{post_id}`      | 게시글 삭제      |
| POST   | `/posts/{post_id}/like` | 좋아요           |
| DELETE | `/posts/{post_id}/like` | 좋아요 취소      |
