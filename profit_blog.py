import os
import json
import random
import re
from datetime import datetime
import requests
from google import genai
from google.genai import types
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

class ProfitOptimizedBlogSystem:
    def __init__(self):
        # API 키 및 설정 (기존과 동일)
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        self.unsplash_api_key = os.getenv('UNSPLASH_API_KEY')
        self.blog_id = os.getenv('BLOGGER_BLOG_ID')
        self.client_id = os.getenv('OAUTH_CLIENT_ID')
        self.client_secret = os.getenv('OAUTH_CLIENT_SECRET')
        self.refresh_token = os.getenv('OAUTH_REFRESH_TOKEN')
        
        self.client = genai.Client(api_key=self.gemini_api_key)
        
        self.profitable_niches = {
            'finance': {'keywords': ['credit card', 'investing', 'mortgage'], 'cpc_level': 'high'},
            'technology': {'keywords': ['AI tools', 'SaaS', 'cybersecurity'], 'cpc_level': 'medium-high'},
            'health': {'keywords': ['fitness', 'supplements', 'weight loss'], 'cpc_level': 'high'},
            'business': {'keywords': ['productivity tools', 'marketing', 'side hustle'], 'cpc_level': 'medium-high'},
            'education': {'keywords': ['online courses', 'learning platforms'], 'cpc_level': 'medium'}
        }

    def get_blogger_service(self):
        from google.auth.transport.requests import Request
        authorized_user_info = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'refresh_token': self.refresh_token,
            'token_uri': 'https://oauth2.googleapis.com/token'
        }
        try:
            creds = Credentials.from_authorized_user_info(authorized_user_info, scopes=['https://www.googleapis.com/auth/blogger'])
            creds.refresh(Request())
            return build('blogger', 'v3', credentials=creds)
        except Exception as e:
            print(f"❌ OAuth 에러: {e}")
            raise

    def get_high_value_topics(self):
        niche = random.choice(list(self.profitable_niches.keys()))
        keywords = self.profitable_niches[niche]['keywords']
        current_year = datetime.now().year
        
        prompt = f"Find 3 trending high-value blog topics in {niche} for {current_year}. Format as JSON."
        try:
            response = self.client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
            text = response.text
            if "```json" in text: text = text.split("```json")[1].split("```")[0]
            return json.loads(text.strip())
        except:
            return {"niche": "technology", "topics": [{"title": f"Top AI Tools {current_year}", "primary_keyword": "AI tools", "secondary_keywords": ["tech"], "description": "Review"}]}

    def generate_monetized_blog_post(self, topic):
        """본문 사진을 각각 다르게 처리하고 스타일 보강"""
        current_year = datetime.now().year
        current_month = datetime.now().strftime("%B %Y")
        
        prompt = f"Write a long HTML blog post about {topic['title']}. Important: Use [IMAGE: keyword] format 4-5 times with different keywords."

        try:
            response = self.client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
            content = response.text.strip()
            if "```html" in content: content = content.split("```html")[1].split("```")[0].strip()
            
            # 1. 연도 및 제목 정리
            title = topic['title'].replace('2024', str(current_year)).replace('2025', str(current_year))
            content = content.replace('2024', str(current_year)).replace('2025', str(current_year))

            # 2. 🔥 [핵심 수정] 이미지 마커별로 서로 다른 사진 넣기
            image_markers = re.findall(r'\[IMAGE:.*?\]', content)
            for marker in image_markers:
                # 마커에서 키워드 추출 (예: [IMAGE: Laptop] -> Laptop)
                keyword = marker.replace('[IMAGE:', '').replace(']', '').strip()
                if not keyword: keyword = topic['primary_keyword']
                
                img_info = self.get_unsplash_image([keyword])
                if img_info:
                    # width: 100%로 PC에서도 꽉 차게, max-width로 너무 커지지 않게 조절
                    img_html = f"""
                    <div style="text-align: center; margin: 40px auto; width: 100%; max-width: 900px;">
                        <img src="{img_info['url']}" alt="{img_info['alt']}" style="width: 100%; height: auto; border-radius: 12px; shadow: 0 10px 15px rgba(0,0,0,0.1);">
                        <p style="font-size: 13px; color: #777; margin-top: 10px;">{img_info['credit']}</p>
                    </div>
                    """
                    content = content.replace(marker, img_html, 1)
                else:
                    content = content.replace(marker, '', 1)

            return {
                'title': title,
                'content': content,
                'meta_description': f"{topic['description'][:150]}...",
                'tags': topic['secondary_keywords'][:5]
            }
        except Exception as e:
            print(f"❌ 글 생성 에러: {e}")
            return None

    def get_unsplash_image(self, keywords):
        try:
            query = " ".join(keywords)
            url = f"https://api.unsplash.com/photos/random"
            params = {'query': query, 'client_id': self.unsplash_api_key, 'orientation': 'landscape'}
            # 사진이 겹치지 않게 하기 위해 매번 새로 호출
            response = requests.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                return {
                    'url': data['urls']['regular'],
                    'alt': data['alt_description'] or query,
                    'credit': f"Photo by {data['user']['name']} on Unsplash",
                    'credit_link': data['user']['links']['html']
                }
        except: return None

    def publish_to_blogger(self, post_data):
        try:
            # 본문 전체를 감싸는 스타일 추가 (모바일처럼 좁아 보이는 현상 방지)
            wrapper_style_start = '<div style="font-family: sans-serif; line-height: 1.8; color: #333; max-width: 1000px; margin: 0 auto; padding: 20px;">'
            wrapper_style_end = '</div>'
            
            ai_disclosure = '<div style="background: #f9f9f9; padding: 15px; border-radius: 8px; font-size: 14px; margin-bottom: 30px;">🤖 This content was optimized by AI for accuracy and clarity.</div>'
            
            full_content = wrapper_style_start + ai_disclosure + post_data['content'] + wrapper_style_end
            
            service = self.get_blogger_service()
            post_body = {
                'kind': 'blogger#post',
                'blog': {'id': self.blog_id},
                'title': post_data['title'],
                'content': full_content,
                'labels': post_data.get('tags', []),
                'status': 'DRAFT'
            }
            result = service.posts().insert(blogId=self.blog_id, body=post_body).execute()
            return {'success': True, 'url': result.get('url')}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def run_daily_automation(self):
        print(f"🚀 자동화 프로세스 시작...")
        topics_data = self.get_high_value_topics()
        topic = topics_data['topics'][0]
        
        post_data = self.generate_monetized_blog_post(topic)
        if not post_data: return
        
        result = self.publish_to_blogger(post_data)
        if result['success']: print(f"✅ 성공! URL: {result['url']}")
        else: print(f"❌ 실패: {result['error']}")

if __name__ == "__main__":
    blog_system = ProfitOptimizedBlogSystem()
    blog_system.run_daily_automation()
