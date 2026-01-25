import os
import json
import random
import re
import sys # 시스템 종료 제어용
from datetime import datetime
import requests
from google import genai
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

class ProfitOptimizedBlogSystem:
    def __init__(self):
        # 환경 변수 로드 확인
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        self.unsplash_api_key = os.getenv('UNSPLASH_API_KEY')
        self.blog_id = os.getenv('BLOGGER_BLOG_ID')
        
        if not self.gemini_api_key:
            print("❌ 오류: GEMINI_API_KEY가 설정되지 않았습니다.")
            sys.exit(1)

        self.client = genai.Client(api_key=self.gemini_api_key)
        
        self.profitable_niches = {
            'technology': ['AI', 'SaaS', 'Gadgets'],
            'finance': ['Stocks', 'Crypto', 'Passive Income']
        }

    def get_blogger_service(self):
        from google.auth.transport.requests import Request
        authorized_user_info = {
            'client_id': os.getenv('OAUTH_CLIENT_ID'),
            'client_secret': os.getenv('OAUTH_CLIENT_SECRET'),
            'refresh_token': os.getenv('OAUTH_REFRESH_TOKEN'),
            'token_uri': 'https://oauth2.googleapis.com/token'
        }
        creds = Credentials.from_authorized_user_info(authorized_user_info, scopes=['https://www.googleapis.com/auth/blogger'])
        creds.refresh(Request())
        return build('blogger', 'v3', credentials=creds)

    def run_daily_automation(self):
        print(f"🚀 자동화 시작 시간: {datetime.now()}")
        
        # 1. 주제 생성
        try:
            niche = random.choice(list(self.profitable_niches.keys()))
            prompt = f"Find 1 trending blog topic for {niche} in 2026. Return ONLY JSON like {{\"title\": \"...\", \"keyword\": \"...\"}}"
            
            # 여기서 429 에러가 나면 바로 로그에 찍힐 겁니다
            response = self.client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
            print("✅ Gemini 주제 생성 응답 수신 성공")
            
            text = response.text
            if "```json" in text: text = text.split("```json")[1].split("```")[0]
            topic_data = json.loads(text.strip())
            
        except Exception as e:
            print(f"❌ 1단계(주제생성) 실패: {str(e)}")
            return

        # 2. 본문 생성
        try:
            post_prompt = f"Write a long HTML blog post about {topic_data['title']}. Use [IMAGE: {topic_data['keyword']}] 3 times."
            post_response = self.client.models.generate_content(model='gemini-2.0-flash', contents=post_prompt)
            content = post_response.text
            if "```html" in content: content = content.split("```html")[1].split("```")[0].strip()
            
            # 이미지 교체 (각기 다른 사진)
            image_markers = re.findall(r'\[IMAGE:.*?\]', content)
            for marker in image_markers:
                # Unsplash 호출
                img_res = requests.get(f"https://api.unsplash.com/photos/random?query={topic_data['keyword']}&client_id={self.unsplash_api_key}")
                if img_res.status_code == 200:
                    img_url = img_res.json()['urls']['regular']
                    img_html = f'<div style="text-align:center; margin:30px 0;"><img src="{img_url}" style="width:100%; max-width:1000px; height:auto; border-radius:12px;"></div>'
                    content = content.replace(marker, img_html, 1)
                else:
                    content = content.replace(marker, '', 1)
            
            print("✅ 본문 생성 및 이미지 매핑 완료")
        except Exception as e:
            print(f"❌ 2단계(본문생성) 실패: {str(e)}")
            return

        # 3. 발행 (데스크탑 반응형 적용)
        try:
            # 반응형 래퍼 (데스크탑 가독성 확보)
            final_html = f"""
            <div style="width:100%; max-width:1000px; margin:0 auto; padding:0 20px; box-sizing:border-box; line-height:1.8;">
                {content}
            </div>
            """
            service = self.get_blogger_service()
            service.posts().insert(
                blogId=self.blog_id,
                body={'title': topic_data['title'], 'content': final_html, 'status': 'DRAFT'}
            ).execute()
            print("🎉 모든 프로세스 완료! Blogger 드래프트 함을 확인하세요.")
        except Exception as e:
            print(f"❌ 3단계(발행) 실패: {str(e)}")

if __name__ == "__main__":
    blog_system = ProfitOptimizedBlogSystem()
    blog_system.run_daily_automation()
