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
        # API 키 및 설정
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        self.unsplash_api_key = os.getenv('UNSPLASH_API_KEY')
        self.blog_id = os.getenv('BLOGGER_BLOG_ID')
        self.client_id = os.getenv('OAUTH_CLIENT_ID')
        self.client_secret = os.getenv('OAUTH_CLIENT_SECRET')
        self.refresh_token = os.getenv('OAUTH_REFRESH_TOKEN')
        
        # Gemini 클라이언트 (1.5 Flash는 쿼터가 넉넉함)
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
            # 주제 생성부터 1.5 Flash 사용
            response = self.client.models.generate_content(model='gemini-1.5-flash', contents=prompt)
            text = response.text
            if "```json" in text: text = text.split("```json")[1].split("```")[0]
            return json.loads(text.strip())
        except:
            return {"topics": [{"title": f"The Future of AI in {current_year}", "primary_keyword": "AI technology", "secondary_keywords": ["AI"], "description": "AI guide"}]}

    def generate_monetized_blog_post(self, topic):
        current_year = datetime.now().year
        # 1.5 버전은 쿼터가 넉넉하지만 안정성을 위해 짧게 대기
        time.sleep(3)

        # 퀄리티 보강을 위한 강력한 프롬프트
        prompt = f"""
        Write a professional, long-form SEO blog post about: {topic['title']}.
        Target Keyword: {topic['primary_keyword']}
        
        Structure:
        1. Compelling Introduction
        2. 4-5 Detailed Sections with <h2> and <h3> subheadings
        3. A Conclusion that encourages engagement
        4. Factual, accurate, and journalistic tone
        5. Insert [IMAGE: keyword] naturally 4-5 times at relevant points
        
        Format: Strictly HTML (No Markdown). Use 1500+ words.
        """

        try:
            # 1.5-flash로 모델 변경
            response = self.client.models.generate_content(model='gemini-1.5-flash', contents=prompt)
            content = response.text.strip()
            if "```html" in content: content = content.split("```html")[1].split("```")[0].strip()
            
            # 반응형 이미지 처리
            image_markers = re.findall(r'\[IMAGE:.*?\]', content)
            for marker in image_markers:
                keyword = marker.replace('[IMAGE:', '').replace(']', '').strip()
                img_info = self.get_unsplash_image([keyword if keyword else topic['primary_keyword']])
                
                if img_info:
                    img_html = f"""
                    <div style="margin: 40px auto; text-align: center; width: 100%;">
                        <img src="{img_info['url']}" alt="{img_info['alt']}" style="width: 100%; max-width: 100%; height: auto; border-radius: 12px; display: block; margin: 0 auto; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
                        <p style="font-size: 0.85em; color: #777; margin-top: 10px;">{img_info['credit']}</p>
                    </div>
                    """
                    content = content.replace(marker, img_html, 1)
                    time.sleep(1) # 이미지 검색 사이 휴식
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
            # 반응형 래퍼 스타일 (PC/모바일 자동 대응)
            responsive_wrapper = f"""
            <div style="width: 100%; max-width: 900px; margin: 0 auto; padding: 0 20px; box-sizing: border-box; font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.8; color: #333; word-break: break-word;">
                <div style="background: #f8f9fa; padding: 25px; border-radius: 15px; margin-bottom: 35px; font-size: 0.95em; border-left: 6px solid #3498db; color: #2c3e50;">
                    📅 <strong>Latest Update:</strong> Insights for {datetime.now().strftime('%B %Y')}
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
        print(f"🚀 {datetime.now().strftime('%H:%M:%S')} Gemini 1.5 기반 자동화 가동")
        topics_data = self.get_high_value_topics()
        if not topics_data: return
        
        topic = topics_data['topics'][0]
        post_data = self.generate_monetized_blog_post(topic)
        
        if post_data:
            result = self.publish_to_blogger(post_data)
            print(f"✅ 포스팅 완료: {result}")

if __name__ == "__main__":
    blog_system = ProfitOptimizedBlogSystem()
    blog_system.run_daily_automation()
