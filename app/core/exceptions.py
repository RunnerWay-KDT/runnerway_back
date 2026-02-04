# ============================================
# app/core/exceptions.py - 커스텀 예외 클래스
# ============================================
# 애플리케이션 전체에서 사용하는 커스텀 예외들을 정의합니다.
# FastAPI의 HTTPException을 상속받아 일관된 에러 응답을 제공합니다.
# ============================================

from fastapi import HTTPException, status
from typing import Optional, Any


class RunnerWayException(HTTPException):
    """
    러너웨이 기본 예외 클래스
    
    모든 커스텀 예외의 부모 클래스입니다.
    
    [신입 개발자를 위한 팁]
    - 예외를 발생시키면 FastAPI가 자동으로 HTTP 응답으로 변환합니다.
    - status_code: HTTP 상태 코드 (400, 401, 404 등)
    - detail: 에러 메시지 (클라이언트에게 전달)
    """
    def __init__(
        self,
        status_code: int,
        error_code: str,
        message: str,
        details: Optional[Any] = None
    ):
        # 일관된 에러 응답 형식
        detail = {
            "success": False,
            "error": {
                "code": error_code,
                "message": message
            }
        }
        
        if details:
            detail["error"]["details"] = details
        
        super().__init__(status_code=status_code, detail=detail)


# ============================================
# 인증 관련 예외
# ============================================

class UnauthorizedException(RunnerWayException):
    """
    인증 실패 예외 (401)
    
    - 토큰이 없거나 유효하지 않을 때
    - 로그인 정보가 잘못되었을 때
    """
    def __init__(
        self,
        message: str = "인증이 필요합니다",
        error_code: str = "UNAUTHORIZED"
    ):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code=error_code,
            message=message
        )


class InvalidCredentialsException(RunnerWayException):
    """
    로그인 정보 불일치 예외 (401)
    """
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="INVALID_CREDENTIALS",
            message="이메일 또는 비밀번호가 올바르지 않습니다"
        )


class TokenExpiredException(RunnerWayException):
    """
    토큰 만료 예외 (401)
    """
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="TOKEN_EXPIRED",
            message="토큰이 만료되었습니다. 다시 로그인해주세요"
        )


class InvalidTokenException(RunnerWayException):
    """
    유효하지 않은 토큰 예외 (401)
    """
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="INVALID_TOKEN",
            message="유효하지 않은 토큰입니다"
        )


# ============================================
# 검증 관련 예외
# ============================================

class ValidationException(RunnerWayException):
    """
    입력값 검증 실패 예외 (400)
    """
    def __init__(
        self,
        message: str = "입력값이 유효하지 않습니다",
        field: Optional[str] = None,
        reason: Optional[str] = None
    ):
        details = None
        if field or reason:
            details = {"field": field, "reason": reason}
        
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="VALIDATION_ERROR",
            message=message,
            details=details
        )


class EmailAlreadyExistsException(RunnerWayException):
    """
    이메일 중복 예외 (409)
    """
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            error_code="EMAIL_ALREADY_EXISTS",
            message="이미 가입된 이메일입니다"
        )


# ============================================
# 리소스 관련 예외
# ============================================

class NotFoundException(RunnerWayException):
    """
    리소스를 찾을 수 없음 예외 (404)
    """
    def __init__(
        self,
        resource: str = "리소스",
        error_code: str = "NOT_FOUND"
    ):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code=error_code,
            message=f"{resource}를 찾을 수 없습니다"
        )


class UserNotFoundException(NotFoundException):
    """사용자를 찾을 수 없음"""
    def __init__(self):
        super().__init__(resource="사용자", error_code="USER_NOT_FOUND")


class RouteNotFoundException(NotFoundException):
    """경로를 찾을 수 없음"""
    def __init__(self):
        super().__init__(resource="경로", error_code="ROUTE_NOT_FOUND")


class WorkoutNotFoundException(NotFoundException):
    """운동 기록을 찾을 수 없음"""
    def __init__(self):
        super().__init__(resource="운동 기록", error_code="WORKOUT_NOT_FOUND")


class PostNotFoundException(NotFoundException):
    """게시물을 찾을 수 없음"""
    def __init__(self):
        super().__init__(resource="게시물", error_code="POST_NOT_FOUND")


class CommentNotFoundException(NotFoundException):
    """댓글을 찾을 수 없음"""
    def __init__(self):
        super().__init__(resource="댓글", error_code="COMMENT_NOT_FOUND")


# ============================================
# 중복 관련 예외
# ============================================

class AlreadyExistsException(RunnerWayException):
    """
    이미 존재하는 리소스 예외 (409)
    """
    def __init__(
        self,
        message: str = "이미 존재합니다",
        error_code: str = "ALREADY_EXISTS"
    ):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            error_code=error_code,
            message=message
        )


class AlreadyLikedException(AlreadyExistsException):
    """이미 좋아요를 누름"""
    def __init__(self):
        super().__init__(
            message="이미 좋아요를 눌렀습니다",
            error_code="ALREADY_LIKED"
        )


class AlreadyBookmarkedException(AlreadyExistsException):
    """이미 북마크함"""
    def __init__(self):
        super().__init__(
            message="이미 북마크했습니다",
            error_code="ALREADY_BOOKMARKED"
        )


# ============================================
# 권한 관련 예외
# ============================================

class ForbiddenException(RunnerWayException):
    """
    권한 없음 예외 (403)
    """
    def __init__(self, message: str = "권한이 없습니다"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="FORBIDDEN",
            message=message
        )


# ============================================
# 소셜 로그인 관련 예외
# ============================================

class SocialAuthFailedException(RunnerWayException):
    """
    소셜 로그인 실패 예외 (401)
    """
    def __init__(self, provider: str = "소셜"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="SOCIAL_AUTH_FAILED",
            message=f"{provider} 로그인에 실패했습니다"
        )


# ============================================
# 서비스 관련 예외
# ============================================

class ServiceUnavailableException(RunnerWayException):
    """
    서비스 이용 불가 예외 (503)
    """
    def __init__(self, message: str = "서비스를 일시적으로 이용할 수 없습니다"):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="SERVICE_UNAVAILABLE",
            message=message
        )


class ExternalAPIException(RunnerWayException):
    """
    외부 API 호출 실패 예외 (502)
    
    Open-Meteo, OSMnx 등 외부 서비스 호출 실패 시 사용
    """
    def __init__(self, message: str = "외부 서비스 호출에 실패했습니다"):
        super().__init__(
            status_code=status.HTTP_502_BAD_GATEWAY,
            error_code="EXTERNAL_API_ERROR",
            message=message
        )


class TooManyRequestsException(RunnerWayException):
    """
    요청 횟수 초과 예외 (429)
    """
    def __init__(self, message: str = "요청 횟수가 너무 많습니다. 잠시 후 다시 시도해주세요"):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            error_code="TOO_MANY_REQUESTS",
            message=message
        )
