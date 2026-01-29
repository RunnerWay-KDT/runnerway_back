CREATE TABLE `users` (
  `id` varchar(36) PRIMARY KEY COMMENT 'UUID, 사용자 고유 식별자',
  `email` varchar(255) UNIQUE NOT NULL COMMENT '이메일 (로그인 ID)',
  `password_hash` varchar(255) COMMENT '해시된 비밀번호',
  `name` varchar(100) NOT NULL COMMENT '사용자 이름 (최소 2자)',
  `avatar_url` varchar(500) COMMENT '프로필 이미지 URL',
  `created_at` timestamp NOT NULL DEFAULT (now()) COMMENT '가입일',
  `updated_at` timestamp NOT NULL DEFAULT (now()) COMMENT '마지막 수정일',
  `deleted_at` timestamp COMMENT '탈퇴일 (Soft Delete)'
);

CREATE TABLE `user_stats` (
  `id` varchar(36) PRIMARY KEY COMMENT 'UUID',
  `user_id` varchar(36) UNIQUE NOT NULL COMMENT '사용자 ID',
  `total_distance` decimal(10,2) DEFAULT 0 COMMENT '총 운동 거리 (km)',
  `total_workouts` int DEFAULT 0 COMMENT '총 운동 횟수',
  `completed_routes` int DEFAULT 0 COMMENT '완료한 경로 수',
  `updated_at` timestamp NOT NULL DEFAULT (now())
);

CREATE TABLE `user_settings` (
  `id` varchar(36) PRIMARY KEY COMMENT 'UUID',
  `user_id` varchar(36) UNIQUE NOT NULL COMMENT '사용자 ID',
  `dark_mode` boolean DEFAULT true COMMENT '다크 모드',
  `language` varchar(10) DEFAULT 'ko' COMMENT '언어 설정',
  `push_enabled` boolean DEFAULT true COMMENT '푸시 알림 활성화',
  `workout_reminder` boolean DEFAULT true COMMENT '운동 시작 알림',
  `goal_achievement` boolean DEFAULT true COMMENT '목표 달성 알림',
  `community_activity` boolean DEFAULT false COMMENT '커뮤니티 활동 알림',
  `auto_lap` boolean DEFAULT false COMMENT '자동 랩',
  `night_safety_mode` boolean DEFAULT true COMMENT '야간 안전 모드',
  `auto_night_mode` boolean DEFAULT true COMMENT '자동 야간 모드',
  `share_location` boolean DEFAULT false COMMENT '위치 공유',
  `sos_button` boolean DEFAULT true COMMENT 'SOS 버튼',
  `created_at` timestamp NOT NULL DEFAULT (now()),
  `updated_at` timestamp NOT NULL DEFAULT (now())
);

CREATE TABLE `emergency_contacts` (
  `id` varchar(36) PRIMARY KEY COMMENT 'UUID',
  `user_id` varchar(36) NOT NULL COMMENT '사용자 ID',
  `name` varchar(50) NOT NULL COMMENT '연락처 이름',
  `phone` varchar(20) NOT NULL COMMENT '전화번호 (10-15자리)',
  `created_at` timestamp NOT NULL DEFAULT (now())
);

CREATE TABLE `refresh_tokens` (
  `id` varchar(36) PRIMARY KEY COMMENT 'UUID',
  `user_id` varchar(36) NOT NULL COMMENT '사용자 ID',
  `token` varchar(500) UNIQUE NOT NULL COMMENT '리프레시 토큰',
  `expires_at` timestamp NOT NULL COMMENT '만료 시간',
  `created_at` timestamp NOT NULL DEFAULT (now()),
  `revoked_at` timestamp COMMENT '폐기 시간'
);

CREATE TABLE `route_shapes` (
  `id` varchar(36) PRIMARY KEY COMMENT 'UUID',
  `name` varchar(50) NOT NULL COMMENT '도형 이름 (하트, 별 등)',
  `icon_name` varchar(50) NOT NULL COMMENT '아이콘 이름',
  `category` varchar(20) NOT NULL COMMENT '카테고리 (shape, animal)',
  `estimated_distance` decimal(5,2) COMMENT '예상 거리 (km)',
  `svg_url` text COMMENT 'SVG url',
  `is_active` boolean DEFAULT true,
  `created_at` timestamp NOT NULL DEFAULT (now())
);

CREATE TABLE `routes` (
  `id` varchar(36) PRIMARY KEY COMMENT 'UUID',
  `user_id` varchar(36) NOT NULL COMMENT '생성자 ID',
  `shape_id` varchar(36) COMMENT '프리셋 도형 ID (null=커스텀)',
  `name` varchar(100) NOT NULL COMMENT '경로 이름',
  `type` varchar(20) COMMENT 'preset / custom / none(null아님!)은 도형그리기 아님',
  `mode` varchar(20) COMMENT 'running / walking / none(null아님!)은 도형그리기임',
  `start_latitude` decimal(10,7) NOT NULL COMMENT '시작점 위도',
  `start_longitude` decimal(10,7) NOT NULL COMMENT '시작점 경도',
  `custom_svg_url` text COMMENT 'SVG Path 데이터 (커스텀인 경우)',
  `condition` varchar(20) COMMENT 'recovery/fat-burn/challenge (러닝)',
  `intensity` varchar(20) COMMENT 'light/moderate/brisk (산책)',
  `target_duration` int COMMENT '목표 시간 (분, 산책)',
  `safety_mode` boolean DEFAULT false COMMENT '안전 우선 모드',
  `status` varchar(20) NOT NULL DEFAULT 'active' COMMENT 'active/deleted',
  `created_at` timestamp NOT NULL DEFAULT (now()),
  `updated_at` timestamp NOT NULL DEFAULT (now())
);

CREATE TABLE `route_options` (
  `id` varchar(36) PRIMARY KEY COMMENT 'UUID',
  `route_id` varchar(36) NOT NULL COMMENT '경로 ID',
  `option_number` int NOT NULL COMMENT '옵션 번호 (1, 2, 3)',
  `name` varchar(100) NOT NULL COMMENT '옵션 이름 (하트 경로 A 등)',
  `distance` decimal(5,2) NOT NULL COMMENT '거리 (km)',
  `estimated_time` int NOT NULL COMMENT '예상 소요 시간 (분)',
  `difficulty` varchar(20) NOT NULL COMMENT '쉬움/보통/도전',
  `tag` varchar(20) COMMENT '추천/BEST/null',
  `coordinates` json NOT NULL COMMENT '[{lat, lng}] 배열',
  `safety_score` int DEFAULT 0 COMMENT '안전도 (0-100)',
  `elevation` int DEFAULT 0 COMMENT '고도차 (m)',
  `lighting_score` int DEFAULT 0 COMMENT '조명 점수 (0-100)',
  `sidewalk_score` int DEFAULT 0 COMMENT '인도 비율 (0-100)',
  `created_at` timestamp NOT NULL DEFAULT (now())
);

CREATE TABLE `saved_routes` (
  `id` varchar(36) PRIMARY KEY COMMENT 'UUID',
  `user_id` varchar(36) NOT NULL COMMENT '저장한 사용자 ID',
  `route_id` varchar(36) NOT NULL COMMENT '경로 ID',
  `saved_at` timestamp NOT NULL DEFAULT (now()) COMMENT '저장 일시'
);

CREATE TABLE `route_generation_tasks` (
  `id` varchar(36) PRIMARY KEY COMMENT 'UUID, task_id로 사용',
  `user_id` varchar(36) NOT NULL COMMENT '요청한 사용자 ID',
  `status` varchar(20) NOT NULL DEFAULT 'processing' COMMENT 'processing/completed/failed',
  `progress` int DEFAULT 0 COMMENT '진행률 (0-100)',
  `current_step` varchar(100) COMMENT '현재 단계 설명',
  `estimated_remaining` int COMMENT '예상 남은 시간 (초)',
  `request_data` json NOT NULL COMMENT '경로 생성 요청 전체 데이터',
  `route_id` varchar(36) COMMENT '생성된 경로 ID (완료 시)',
  `error_message` varchar(500) COMMENT '에러 메시지 (실패 시)',
  `created_at` timestamp NOT NULL DEFAULT (now()),
  `completed_at` timestamp COMMENT '완료/실패 시간'
);

CREATE TABLE `places` (
  `id` varchar(36) PRIMARY KEY COMMENT 'UUID',
  `name` varchar(100) NOT NULL COMMENT '장소 이름',
  `category` varchar(30) NOT NULL COMMENT 'cafe/convenience/park/photo/restroom/fountain/cctv',
  `latitude` decimal(10,7) NOT NULL COMMENT '위도',
  `longitude` decimal(10,7) NOT NULL COMMENT '경도',
  `address` varchar(255) COMMENT '주소',
  `rating` decimal(2,1) COMMENT '평점 (0.0-5.0)',
  `review_count` int DEFAULT 0 COMMENT '리뷰 수',
  `icon` varchar(50) COMMENT '아이콘 이름 (coffee, store, trees 등)',
  `color` varchar(10) COMMENT '색상 코드 (#f59e0b)',
  `is_active` boolean DEFAULT true,
  `created_at` timestamp NOT NULL DEFAULT (now()),
  `updated_at` timestamp NOT NULL DEFAULT (now())
);

CREATE TABLE `workouts` (
  `id` varchar(36) PRIMARY KEY COMMENT 'UUID, workout_id로 사용',
  `user_id` varchar(36) NOT NULL COMMENT '사용자 ID',
  `route_id` varchar(36) COMMENT '경로 ID',
  `route_option_id` varchar(36) COMMENT '선택한 경로 옵션 ID',
  `route_name` varchar(100) NOT NULL COMMENT '경로 이름 (스냅샷)',
  `type` varchar(20) COMMENT 'preset / custom / null은 도형그리기 아님',
  `mode` varchar(20) COMMENT 'running / walking / null은 도형그리기임',
  `status` varchar(20) NOT NULL DEFAULT 'active' COMMENT 'active/paused/completed',
  `started_at` timestamp NOT NULL COMMENT '운동 시작 시간',
  `completed_at` timestamp COMMENT '운동 완료 시간',
  `start_latitude` decimal(10,7) NOT NULL,
  `start_longitude` decimal(10,7) NOT NULL,
  `end_latitude` decimal(10,7),
  `end_longitude` decimal(10,7),
  `distance` decimal(5,2) COMMENT '총 거리 (km)',
  `duration` int COMMENT '총 시간 (초)',
  `avg_pace` varchar(20) COMMENT '평균 페이스',
  `max_pace` varchar(20) COMMENT '최고 페이스',
  `min_pace` varchar(20) COMMENT '최저 페이스',
  `calories` int COMMENT '소모 칼로리 (kcal)',
  `elevation_gain` int COMMENT '상승 고도의 누적합',
  `elevation_loss` int COMMENT '하강 고도의 누적합',
  `route_completion` decimal(5,2) COMMENT '경로 완주율 (%)',
  `actual_path` json COMMENT '[{lat, lng, timestamp}] 배열',
  `created_at` timestamp NOT NULL DEFAULT (now()),
  `updated_at` timestamp NOT NULL DEFAULT (now()),
  `deleted_at` timestamp COMMENT 'Soft Delete'
);

CREATE TABLE `workout_splits` (
  `id` varchar(36) PRIMARY KEY COMMENT 'UUID',
  `workout_id` varchar(36) NOT NULL COMMENT '운동 ID',
  `km` int NOT NULL COMMENT 'km 구간 (1, 2, 3...)',
  `pace` varchar(20) NOT NULL COMMENT '해당 구간 페이스',
  `duration` int NOT NULL COMMENT '해당 구간 소요 시간 (초)'
);

CREATE TABLE `posts` (
  `id` varchar(36) PRIMARY KEY COMMENT 'UUID, post_id로 사용',
  `author_id` varchar(36) NOT NULL COMMENT '작성자 ID',
  `workout_id` varchar(36) UNIQUE COMMENT '공유된 운동 ID',
  `route_name` varchar(100) NOT NULL,
  `shape_id` varchar(50),
  `shape_name` varchar(50),
  `shape_icon` varchar(50),
  `distance` decimal(5,2) NOT NULL,
  `duration` int NOT NULL,
  `pace` varchar(20),
  `calories` int,
  `location` varchar(100) COMMENT '위치 (여의도 한강공원)',
  `caption` text COMMENT '캡션 (선택적)',
  `visibility` varchar(20) NOT NULL DEFAULT 'public' COMMENT 'public/private',
  `like_count` int DEFAULT 0,
  `comment_count` int DEFAULT 0,
  `bookmark_count` int DEFAULT 0,
  `created_at` timestamp NOT NULL DEFAULT (now()),
  `updated_at` timestamp NOT NULL DEFAULT (now()),
  `deleted_at` timestamp COMMENT 'Soft Delete'
);

CREATE TABLE `post_likes` (
  `id` varchar(36) PRIMARY KEY COMMENT 'UUID',
  `post_id` varchar(36) NOT NULL COMMENT '게시물 ID',
  `user_id` varchar(36) NOT NULL COMMENT '좋아요한 사용자 ID',
  `created_at` timestamp NOT NULL DEFAULT (now())
);

CREATE TABLE `post_bookmarks` (
  `id` varchar(36) PRIMARY KEY COMMENT 'UUID',
  `post_id` varchar(36) NOT NULL COMMENT '게시물 ID',
  `user_id` varchar(36) NOT NULL COMMENT '북마크한 사용자 ID',
  `created_at` timestamp NOT NULL DEFAULT (now())
);

CREATE TABLE `comments` (
  `id` varchar(36) PRIMARY KEY COMMENT 'UUID, comment_id로 사용',
  `post_id` varchar(36) NOT NULL COMMENT '게시물 ID',
  `author_id` varchar(36) NOT NULL COMMENT '작성자 ID',
  `content` varchar(500) NOT NULL COMMENT '댓글 내용 (최대 500자)',
  `like_count` int DEFAULT 0 COMMENT '좋아요 수 (캐시)',
  `created_at` timestamp NOT NULL DEFAULT (now()),
  `updated_at` timestamp NOT NULL DEFAULT (now()),
  `deleted_at` timestamp COMMENT 'Soft Delete'
);

CREATE TABLE `comment_likes` (
  `id` varchar(36) PRIMARY KEY COMMENT 'UUID',
  `comment_id` varchar(36) NOT NULL COMMENT '댓글 ID',
  `user_id` varchar(36) NOT NULL COMMENT '좋아요한 사용자 ID',
  `created_at` timestamp NOT NULL DEFAULT (now())
);

CREATE TABLE `recommended_routes` (
  `id` varchar(36) PRIMARY KEY COMMENT 'UUID',
  `route_id` varchar(36) NOT NULL COMMENT '경로 ID',
  `target_latitude` decimal(10,7) COMMENT '타겟 위도',
  `target_longitude` decimal(10,7) COMMENT '타겟 경도',
  `radius_km` decimal(5,2) COMMENT '추천 반경 (km)',
  `rating` decimal(2,1) COMMENT '평점',
  `runner_count` int DEFAULT 0 COMMENT '이용자 수',
  `reason` varchar(255) COMMENT '추천 이유',
  `priority` int DEFAULT 0 COMMENT '추천 우선순위',
  `is_active` boolean DEFAULT true,
  `start_date` date COMMENT '추천 시작일',
  `end_date` date COMMENT '추천 종료일',
  `created_at` timestamp NOT NULL DEFAULT (now())
);

ALTER TABLE `emergency_contacts` COMMENT = '사용자당 최대 3개까지';

ALTER TABLE `route_shapes` COMMENT = '템플릿 저장경로';

ALTER TABLE `user_stats` ADD FOREIGN KEY (`user_id`) REFERENCES `users` (`id`);

ALTER TABLE `user_settings` ADD FOREIGN KEY (`user_id`) REFERENCES `users` (`id`);

ALTER TABLE `emergency_contacts` ADD FOREIGN KEY (`user_id`) REFERENCES `users` (`id`);

ALTER TABLE `refresh_tokens` ADD FOREIGN KEY (`user_id`) REFERENCES `users` (`id`);

ALTER TABLE `routes` ADD FOREIGN KEY (`user_id`) REFERENCES `users` (`id`);

ALTER TABLE `routes` ADD FOREIGN KEY (`shape_id`) REFERENCES `route_shapes` (`id`);

ALTER TABLE `route_options` ADD FOREIGN KEY (`route_id`) REFERENCES `routes` (`id`);

ALTER TABLE `saved_routes` ADD FOREIGN KEY (`user_id`) REFERENCES `users` (`id`);

ALTER TABLE `saved_routes` ADD FOREIGN KEY (`route_id`) REFERENCES `routes` (`id`);

ALTER TABLE `route_generation_tasks` ADD FOREIGN KEY (`user_id`) REFERENCES `users` (`id`);

ALTER TABLE `route_generation_tasks` ADD FOREIGN KEY (`route_id`) REFERENCES `routes` (`id`);

ALTER TABLE `workouts` ADD FOREIGN KEY (`user_id`) REFERENCES `users` (`id`);

ALTER TABLE `workouts` ADD FOREIGN KEY (`route_id`) REFERENCES `routes` (`id`);

ALTER TABLE `workouts` ADD FOREIGN KEY (`route_option_id`) REFERENCES `route_options` (`id`);

ALTER TABLE `workout_splits` ADD FOREIGN KEY (`workout_id`) REFERENCES `workouts` (`id`);

ALTER TABLE `posts` ADD FOREIGN KEY (`author_id`) REFERENCES `users` (`id`);

ALTER TABLE `posts` ADD FOREIGN KEY (`workout_id`) REFERENCES `workouts` (`id`);

ALTER TABLE `post_likes` ADD FOREIGN KEY (`post_id`) REFERENCES `posts` (`id`);

ALTER TABLE `post_likes` ADD FOREIGN KEY (`user_id`) REFERENCES `users` (`id`);

ALTER TABLE `post_bookmarks` ADD FOREIGN KEY (`post_id`) REFERENCES `posts` (`id`);

ALTER TABLE `post_bookmarks` ADD FOREIGN KEY (`user_id`) REFERENCES `users` (`id`);

ALTER TABLE `comments` ADD FOREIGN KEY (`post_id`) REFERENCES `posts` (`id`);

ALTER TABLE `comments` ADD FOREIGN KEY (`author_id`) REFERENCES `users` (`id`);

ALTER TABLE `comment_likes` ADD FOREIGN KEY (`comment_id`) REFERENCES `comments` (`id`);

ALTER TABLE `comment_likes` ADD FOREIGN KEY (`user_id`) REFERENCES `users` (`id`);

ALTER TABLE `recommended_routes` ADD FOREIGN KEY (`route_id`) REFERENCES `routes` (`id`);
