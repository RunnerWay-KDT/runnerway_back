# ============================================
# app/models/__init__.py
# ============================================
# 데이터베이스 모델 패키지 초기화
# 
# 모든 모델을 한 곳에서 import할 수 있도록 합니다.
# ============================================

"""
데이터베이스 모델 모듈

이 모듈에서 모든 데이터베이스 테이블 모델을 관리합니다.
SQLAlchemy ORM을 사용하여 Python 클래스로 테이블을 정의합니다.

[신입 개발자를 위한 팁]
- 각 파일은 관련된 테이블들을 묶어놓았습니다.
- user.py: 사용자 관련 테이블
- route.py: 경로 관련 테이블
- workout.py: 운동 관련 테이블
- community.py: 커뮤니티 관련 테이블
"""

# 모든 모델을 import하여 Base.metadata에 등록
from app.models.user import (
    User,
    UserStats,
    UserSettings,
    RefreshToken
)
from app.models.route import (
    RouteShape,
    Route,
    RouteOption,
    SavedRoute,
    RouteGenerationTask,
    Place,
    RecommendedRoute
)
from app.models.workout import (
    Workout,
    WorkoutSplit
)
from app.models.community import (
    Post,
    PostLike,
    PostBookmark,
    Comment,
    CommentLike
)
from app.models.elevation import ElevationCache

# 외부에서 import할 수 있는 모델 목록
__all__ = [
    # User 관련
    "User",
    "UserStats",
    "UserSettings",
    "RefreshToken",
    # Route 관련
    "RouteShape",
    "Route",
    "RouteOption",
    "SavedRoute",
    "RouteGenerationTask",
    "Place",
    "RecommendedRoute",
    # Workout 관련
    "Workout",
    "WorkoutSplit",
    # Community 관련
    "Post",
    "PostLike",
    "PostBookmark",
    "Comment",
    "CommentLike",
    # Elevation 관련
    "ElevationCache"
]
