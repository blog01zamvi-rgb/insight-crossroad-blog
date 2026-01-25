import os
import json
import random
import re
import time
from datetime import datetime
import requests
from google import genai
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

class ProfitOptimizedBlogSystem:
    def __init__(self):
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        self.unsplash_api_key = os.getenv('UNSPLASH_API_KEY')
        self.blog_id = os.getenv('BLOGGER_BLOG_ID')
        self.client_id = os.getenv('OAUTH_CLIENT_ID')
        self.client_secret = os.getenv('OAUTH_CLIENT_SECRET')
        self.refresh_token = os.getenv('OAUTH_REFRESH_TOKEN')
        
        # 클라이언트 초기화
        self.client = genai.Client(api_key=self.gemini_api_key)
        
        self.profitable_niches = {
            'technology': {'keywords': ['AI tools', 'SaaS'], 'cpc_level': 'high'},
            'finance': {'keywords': ['investing', 'passive income'], 'cpc_level': 'high'}
        }

    def get_blogger_service(self):
        from google.auth.transport.requests import Request
        authorized_user_info = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'refresh_token': self.refresh_token,
            'token_uri': 'https://oauth2.googleapis.com/token'
        }
        creds = Credentials.from_authorized_user_info(authorized_user_info, scopes=['https://www.googleapis.com/auth/blogger'])
        creds.refresh(Request())
        return build('blogger', 'v3', credentials=creds)

    def get_high_value_topics(self):
        niche = random.choice(list(self.profitable_niches.keys()))
        prompt = f"Find 3 trending high-value blog topics in {niche} for 2026. Format as JSON."
        try:
            # 모델명에서 'models/'를 빼고 'gemini-1.5-flash'로 시도
            response = self.client.models.generate_content(model='gemini-1.5-flash', contents=prompt)
            text = response.text
            if "```json" in text: text = text.split("```json")[1].split("```")[0]
            return json.loads(text.strip())
        except Exception as e:
            print(f"❌ 주제 생성 실패: {e}")
            return {"topics": [{"title": "Future of AI 2026", "primary_keyword": "AI", "secondary_keywords": ["tech"], "description": "AI Trends"}]}

    def generate_monetized_blog_post(self, topic):
        # 429 방지를 위해 최소한의 대기
        time.sleep(5)
        prompt = f"Write a professional SEO HTML blog post about {topic['title']}. Use [IMAGE: keyword] 4 times."

        try:
            # 1.5-flash 모델명 확인
            response = self.client.models.generate_content(model='gemini-1.5-flash', contents=prompt)
            content = response.text.strip()
            if "```html" in content: content = content.split("```html")[1].split("```")[0].strip()
            
            image_markers = re.findall(r'\[IMAGE:.*?\]', content)
            for marker in image_markers:
                keyword = marker.replace('[IMAGE:', '').replace(']', '').strip()
                img_info = self.get_unsplash_image([keyword if keyword else "technology"])
                if img_info:
                    img_html = f'<div style="margin:40px 0;text-align:center;"><img src="{img_info["url"]}" style="width:100%;max-width:900px;border-radius:12px;"><p style="font-size:12px;color:#777;">{img_info["credit"]}</p></div>'
                    content = content.replace(marker, img_html, 1)
                    time.sleep(1)
                else:
                    content = content.replace(marker, '', 1)

            return {'title': topic['title'], 'content': content, 'tags': topic.get('secondary_keywords', [])}
        except Exception as e:
            print(f"❌ 본문 생성 에러: {e}")
            return None

    def get_unsplash_image(self, keywords):
        try:
            url = "https://api.unsplash.com/photos/random"
            params = {'query': " ".join(keywords), 'client_id': self.unsplash_api_key}
            res = requests.get(url, params=params)
            if res.status_code == 200:
                data = res.json()
                return {'url': data['urls']['regular'], 'alt': data['alt_description'], 'credit': f"Photo by {data['user']['name']}"}
        except: return None

    def publish_to_blogger(self, post_data):
        try:
            # 반응형 래퍼
            full_content = f'<div style="width:100%;max-width:1000px;margin:0 auto;line-height:1.8;padding:0 20px;box-sizing:border-box;">{post_data["content"]}</div>'
            service = self.get_blogger_service()
            post_body = {'title': post_data['title'], 'content': full_content, 'labels': post_data['tags'], 'status': 'DRAFT'}
            result = service.posts().insert(blogId=self.blog_id, body=post_body).execute()
            return {'success': True, 'url': result.get('url')}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def run_daily_automation(self):
        topics = self.get_high_value_topics()
        topic = topics['topics'][0]
        post = self.generate_monetized_blog_post(topic)
        if post:
            res = self.publish_to_blogger(post)
            print(f"✅ 결과: {res}")

if __name__ == "__main__":
    blog_system = ProfitOptimizedBlogSystem()
    blog_system.run_daily_automation()
