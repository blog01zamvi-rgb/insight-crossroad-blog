import os
import json
import random
import re
import time
from datetime import datetime
import requests
from google import genai
from google.api_core import exceptions # 에러 처리를 위해 추가
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
        
        self.client = genai.Client(api_key=self.gemini_api_key)
        
        self.profitable_niches = {
            'technology': {'keywords': ['AI tools', 'SaaS', 'future tech'], 'cpc_level': 'high'},
            'finance': {'keywords': ['investing', 'passive income', 'crypto'], 'cpc_level': 'high'},
            'business': {'keywords': ['productivity', 'entrepreneurship'], 'cpc_level': 'medium-high'}
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
        current_year = datetime.now().year
        prompt = f"Find 3 trending high-value blog topics in {niche} for {current_year}. Format as JSON."
        try:
            response = self.client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
            text = response.text
            if "```json" in text: text = text.split("```json")[1].split("```")[0]
            return json.loads(text.strip())
        except:
            return {"topics": [{"title": f"The Future of AI in {current_year}", "primary_keyword": "AI technology", "secondary_keywords": ["AI"], "description": "AI guide"}]}

    def generate_monetized_blog_post(self, topic):
        current_year = datetime.now().year
        print("⏳ Quota 보호를 위해 15초 대기 중...")
        time.sleep(15) # 429 에러 방지를 위해 대기 시간을 조금 더 늘렸습니다.

        prompt = f"Write a detailed HTML blog post about {topic['title']}. Use [IMAGE: keyword] 4-5 times."

        try:
            response = self.client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
            content = response.text.strip()
            if "```html" in content: content = content.split("```html")[1].split("```")[0].strip()
            
            # 이미지 마커 처리 (반응형 스타일 적용)
            image_markers = re.findall(r'\[IMAGE:.*?\]', content)
            for marker in image_markers:
                keyword = marker.replace('[IMAGE:', '').replace(']', '').strip()
                img_info = self.get_unsplash_image([keyword if keyword else topic['primary_keyword']])
                
                if img_info:
                    # width: 100%와 max-width: 100%를 조합해 화면 크기에 따라 유연하게 변함
                    img_html = f"""
                    <div style="margin: 40px 0; text-align: center;">
                        <img src="{img_info['url']}" alt="{img_info['alt']}" style="width: 100%; height: auto; max-width: 100%; border-radius: 12px; display: block; margin: 0 auto;">
                        <p style="font-size: 0.85em; color: #777; margin-top: 12px;">{img_info['credit']}</p>
                    </div>
                    """
                    content = content.replace(marker, img_html, 1)
                    time.sleep(1.5)
                else:
                    content = content.replace(marker, '', 1)

            return {
                'title': topic['title'].replace('2024', str(current_year)).replace('2025', str(current_year)),
                'content': content,
                'tags': topic.get('secondary_keywords', [])
            }
        except Exception as e:
            print(f"❌ 글 생성 중 에러: {e}")
            return None

    def get_unsplash_image(self, keywords):
        try:
            url = f"https://api.unsplash.com/photos/random"
            params = {'query': " ".join(keywords), 'client_id': self.unsplash_api_key, 'orientation': 'landscape'}
            response = requests.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                return {'url': data['urls']['regular'], 'alt': data['alt_description'], 'credit': f"Photo by {data['user']['name']} on Unsplash"}
        except: return None

    def publish_to_blogger(self, post_data):
        try:
            # 유연한 반응형 래퍼 (최대폭은 1000px로 잡되, 그보다 작은 화면에선 100%를 유지)
            responsive_wrapper = f"""
            <div style="width: 100%; max-width: 1000px; margin: 0 auto; padding: 0 15px; box-sizing: border-box; font-family: 'Helvetica Neue', Arial, sans-serif; line-height: 1.8; color: #333; word-break: break-word;">
                <div style="background: #f4f7f6; padding: 20px; border-radius: 10px; margin-bottom: 30px; font-size: 0.95em; border-left: 5px solid #2ecc71;">
                    💡 <strong>Editor's Note:</strong> This article provides the latest insights for {datetime.now().year}.
                </div>
                {post_data['content']}
            </div>
            """
            
            service = self.get_blogger_service()
            post_body = {
                'title': post_data['title'],
                'content': responsive_wrapper,
                'labels': post_data['tags'],
                'status': 'DRAFT'
            }
            result = service.posts().insert(blogId=self.blog_id, body=post_body).execute()
            return {'success': True, 'url': result.get('url')}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def run_daily_automation(self):
        print(f"🚀 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 자동 발행 시작")
        topics_data = self.get_high_value_topics()
        if not topics_data: return
        
        topic = topics_data['topics'][0]
        post_data = self.generate_monetized_blog_post(topic)
        
        if post_data:
            result = self.publish_to_blogger(post_data)
            print(f"✅ 결과: {result}")

if __name__ == "__main__":
    blog_system = ProfitOptimizedBlogSystem()
    blog_system.run_daily_automation()
