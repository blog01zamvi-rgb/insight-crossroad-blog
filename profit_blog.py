import os
import json
import random
import re
import time
from datetime import datetime
import requests
from google import genai
from google.api_core import exceptions
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

class ProfitOptimizedBlogSystem:
    def __init__(self):
        # [원본 그대로 유지] API 키 및 설정
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        self.unsplash_api_key = os.getenv('UNSPLASH_API_KEY')
        self.blog_id = os.getenv('BLOGGER_BLOG_ID')
        self.client_id = os.getenv('OAUTH_CLIENT_ID')
        self.client_secret = os.getenv('OAUTH_CLIENT_SECRET')
        self.refresh_token = os.getenv('OAUTH_REFRESH_TOKEN')
        self.amazon_tag = os.getenv('AMAZON_ASSOCIATE_TAG', '')
        
        self.client = genai.Client(api_key=self.gemini_api_key)
        
        self.profitable_niches = {
            'finance': {'keywords': ['credit card', 'investing'], 'cpc_level': 'high'},
            'technology': {'keywords': ['AI tools', 'SaaS'], 'cpc_level': 'medium-high'},
            'health': {'keywords': ['fitness', 'nutrition'], 'cpc_level': 'high'},
            'business': {'keywords': ['marketing', 'productivity'], 'cpc_level': 'medium-high'},
            'education': {'keywords': ['online courses'], 'cpc_level': 'medium'}
        }

    def get_blogger_service(self):
        from google.auth.transport.requests import Request
        authorized_user_info = {
            'client_id': self.client_id, 'client_secret': self.client_secret,
            'refresh_token': self.refresh_token, 'token_uri': 'https://oauth2.googleapis.com/token'
        }
        creds = Credentials.from_authorized_user_info(authorized_user_info, scopes=['https://www.googleapis.com/auth/blogger'])
        creds.refresh(Request())
        return build('blogger', 'v3', credentials=creds)

    def get_high_value_topics(self):
        niche = random.choice(list(self.profitable_niches.keys()))
        prompt = f"Find 3 trending high-value blog topics in {niche} for 2026. Format as JSON."
        try:
            response = self.client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
            text = response.text
            if "```json" in text: text = text.split("```json")[1].split("```")[0]
            return json.loads(text.strip())
        except:
            return {"topics": [{"title": "Future Trends 2026", "primary_keyword": "trends", "secondary_keywords": [], "description": ""}]}

    def generate_monetized_blog_post(self, topic):
        """수정: 마커마다 각기 다른 이미지를 삽입하는 로직 적용"""
        current_year = datetime.now().year
        prompt = f"Write a professional SEO HTML blog post about {topic['title']}. Use [IMAGE: keyword] 4-5 times."

        try:
            response = self.client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
            content = response.text.strip()
            if "```html" in content: content = content.split("```html")[1].split("```")[0].strip()
            
            # 제목 및 연도 정리
            title = topic['title'].replace('2024', str(current_year)).replace('2025', str(current_year))
            content = content.replace('2024', str(current_year)).replace('2025', str(current_year))

            # 🔥 [수정] 각 이미지 마커를 서로 다른 실시간 이미지로 교체
            image_markers = re.findall(r'\[IMAGE:.*?\]', content)
            for marker in image_markers:
                keyword = marker.replace('[IMAGE:', '').replace(']', '').strip()
                if not keyword: keyword = topic['primary_keyword']
                
                # Unsplash에서 개별 이미지 검색
                img_info = self.get_unsplash_image([keyword])
                if img_info:
                    img_html = f"""
                    <div style="margin: 40px auto; text-align: center;">
                        <img src="{img_info['url']}" alt="{img_info['alt']}" style="width: 100%; height: auto; max-width: 100%; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.1);">
                        <p style="font-size: 13px; color: #888; margin-top: 10px;">{img_info['credit']}</p>
                    </div>
                    """
                    content = content.replace(marker, img_html, 1)
                else:
                    content = content.replace(marker, '', 1)

            return {'title': title, 'content': content, 'tags': topic.get('secondary_keywords', [])}
        except: return None

    def get_unsplash_image(self, keywords):
        try:
            url = f"https://api.unsplash.com/photos/random"
            params = {'query': " ".join(keywords), 'client_id': self.unsplash_api_key, 'orientation': 'landscape'}
            res = requests.get(url, params=params)
            if res.status_code == 200:
                data = res.json()
                return {'url': data['urls']['regular'], 'alt': data['alt_description'], 'credit': f"Photo by {data['user']['name']} on Unsplash"}
        except: return None

    def publish_to_blogger(self, post_data):
        """수정: 데스크탑에서도 시원하게 보이도록 반응형 래퍼 적용"""
        try:
            # max-width: 1000px로 데스크탑 가독성 확보, padding으로 모바일 여백 확보
            full_content = f"""
            <div style="width: 100%; max-width: 1000px; margin: 0 auto; padding: 0 20px; box-sizing: border-box; line-height: 1.8; font-family: sans-serif;">
                <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 25px;">🤖 AI-Optimized Content for {datetime.now().year}</div>
                {post_data['content']}
            </div>
            """
            service = self.get_blogger_service()
            post_body = {'title': post_data['title'], 'content': full_content, 'labels': post_data['tags'], 'status': 'DRAFT'}
            result = service.posts().insert(blogId=self.blog_id, body=post_body).execute()
            return result.get('url')
        except Exception as e:
            print(f"발행 에러: {e}")
            return None

    def run_daily_automation(self):
        print("🚀 자동화 시작...")
        topics_data = self.get_high_value_topics()
        post_data = self.generate_monetized_blog_post(topics_data['topics'][0])
        if post_data:
            url = self.publish_to_blogger(post_data)
            print(f"✅ 완료: {url}")

if __name__ == "__main__":
    blog_system = ProfitOptimizedBlogSystem()
    blog_system.run_daily_automation()
