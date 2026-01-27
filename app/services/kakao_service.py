# ============================================
# app/services/kakao_service.py - 카카오 API 서비스
# ============================================
# 카카오 소셜 로그인 관련 비즈니스 로직을 처리합니다.
# ============================================

import httpx
from typing import Optional, Dict, Any

from app.config import settings
from app.core.exceptions import SocialAuthFailedException


class KakaoService:
    """
    카카오 API 서비스 클래스
    
    카카오 소셜 로그인 관련 기능을 제공합니다.
    
    [신입 개발자를 위한 팁]
    - OAuth 2.0 흐름:
      1. 프론트엔드에서 카카오 로그인 버튼 클릭
      2. 카카오 로그인 페이지로 이동 (카카오 SDK 처리)
      3. 사용자가 로그인 및 동의
      4. 카카오가 프론트엔드로 인가 코드(code) 또는 토큰 반환
      5. 프론트엔드가 백엔드로 토큰과 프로필 정보 전송
      6. 백엔드에서 토큰 검증 후 회원가입/로그인 처리
    
    [카카오 개발자 문서]
    https://developers.kakao.com/docs/latest/ko/kakaologin/rest-api
    """
    
    # 카카오 API 엔드포인트
    KAKAO_TOKEN_INFO_URL = "https://kapi.kakao.com/v1/user/access_token_info"
    KAKAO_USER_INFO_URL = "https://kapi.kakao.com/v2/user/me"
    
    def __init__(self):
        """
        카카오 서비스 초기화
        
        httpx.AsyncClient를 사용하여 비동기 HTTP 요청을 처리합니다.
        """
        self.client_id = settings.KAKAO_CLIENT_ID
        self.client_secret = settings.KAKAO_CLIENT_SECRET
    
    async def verify_access_token(self, access_token: str) -> Dict[str, Any]:
        """
        카카오 액세스 토큰 검증
        
        프론트엔드에서 받은 카카오 액세스 토큰이 유효한지 확인합니다.
        
        Args:
            access_token: 카카오 SDK에서 받은 액세스 토큰
            
        Returns:
            Dict: 토큰 정보 (id, expires_in 등)
            
        Raises:
            SocialAuthFailedException: 토큰이 유효하지 않은 경우
            
        [API 응답 예시]
        {
            "id": 1234567890,
            "expires_in": 7199,
            "app_id": 123456
        }
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    self.KAKAO_TOKEN_INFO_URL,
                    headers={
                        "Authorization": f"Bearer {access_token}"
                    }
                )
                
                if response.status_code != 200:
                    # 토큰이 유효하지 않음
                    raise SocialAuthFailedException("카카오")
                
                return response.json()
                
            except httpx.HTTPError as e:
                # HTTP 요청 실패
                print(f"카카오 토큰 검증 실패: {e}")
                raise SocialAuthFailedException("카카오")
    
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """
        카카오 사용자 정보 조회
        
        액세스 토큰을 사용하여 카카오 사용자 프로필을 조회합니다.
        
        Args:
            access_token: 카카오 액세스 토큰
            
        Returns:
            Dict: 사용자 정보 (id, kakao_account, properties 등)
            
        Raises:
            SocialAuthFailedException: 조회 실패 시
            
        [API 응답 예시]
        {
            "id": 1234567890,
            "connected_at": "2024-01-01T00:00:00Z",
            "kakao_account": {
                "profile_nickname_needs_agreement": false,
                "profile_image_needs_agreement": false,
                "profile": {
                    "nickname": "홍길동",
                    "thumbnail_image_url": "https://...",
                    "profile_image_url": "https://..."
                },
                "email_needs_agreement": false,
                "is_email_valid": true,
                "is_email_verified": true,
                "email": "user@example.com"
            },
            "properties": {
                "nickname": "홍길동",
                "profile_image": "https://..."
            }
        }
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    self.KAKAO_USER_INFO_URL,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/x-www-form-urlencoded;charset=utf-8"
                    }
                )
                
                if response.status_code != 200:
                    raise SocialAuthFailedException("카카오")
                
                return response.json()
                
            except httpx.HTTPError as e:
                print(f"카카오 사용자 정보 조회 실패: {e}")
                raise SocialAuthFailedException("카카오")
    
    async def validate_and_get_profile(
        self,
        access_token: str,
        provided_profile: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        토큰을 검증하고 사용자 프로필을 반환합니다.
        
        1. 액세스 토큰 유효성 검증
        2. 사용자 정보 조회 (제공된 프로필이 없는 경우)
        3. 프로필 정보 정규화
        
        Args:
            access_token: 카카오 액세스 토큰
            provided_profile: 프론트엔드에서 제공한 프로필 (선택)
            
        Returns:
            Dict: 정규화된 사용자 프로필
                - kakao_id: 카카오 사용자 ID
                - email: 이메일 (없으면 None)
                - nickname: 닉네임
                - profile_image: 프로필 이미지 URL (없으면 None)
        """
        # 1. 토큰 검증
        token_info = await self.verify_access_token(access_token)
        kakao_id = str(token_info.get("id"))
        
        # 2. 사용자 정보 조회 (프로필이 제공되지 않은 경우)
        if provided_profile:
            # 프론트엔드에서 제공한 프로필 사용
            return {
                "kakao_id": provided_profile.get("id") or kakao_id,
                "email": provided_profile.get("email"),
                "nickname": provided_profile.get("nickname", "카카오사용자"),
                "profile_image": provided_profile.get("profile_image")
            }
        
        # 카카오 API에서 직접 조회
        user_info = await self.get_user_info(access_token)
        
        # 3. 프로필 정보 추출 및 정규화
        kakao_account = user_info.get("kakao_account", {})
        profile = kakao_account.get("profile", {})
        properties = user_info.get("properties", {})
        
        return {
            "kakao_id": str(user_info.get("id")),
            "email": kakao_account.get("email"),
            "nickname": profile.get("nickname") or properties.get("nickname", "카카오사용자"),
            "profile_image": profile.get("profile_image_url") or properties.get("profile_image")
        }


# 싱글톤 인스턴스 (애플리케이션 전체에서 하나만 사용)
kakao_service = KakaoService()
