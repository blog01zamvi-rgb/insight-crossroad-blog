import os
import json
import random
import time
import re
from datetime import datetime
import requests
from google import genai
from google.genai import types
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

class ProfitOptimizedBlogSystem:
    def __init__(self):
        # API 키 및 설정 로드
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        self.unsplash_api_key = os.getenv('UNSPLASH_API_KEY')
        self.blog_id = os.getenv('BLOGGER_BLOG_ID')
        self.client_id = os.getenv('OAUTH_CLIENT_ID')
        self.client_secret = os.getenv('OAUTH_CLIENT_SECRET')
        self.refresh_token = os.getenv('OAUTH_REFRESH_TOKEN')
        
        # Gemini 클라이언트 설정
        self.client = genai.Client(api_key=self.gemini_api_key)
        # SDK v1에서는 'gemini-1.5-flash'만 적는 것이 정확합니다.
        self.model_name = 'gemini-1.5-flash'
        
        self.profitable_niches = {
            'finance': {'keywords': ['credit card', 'insurance', 'investing', 'mortgage'], 'cpc_level': 'high'},
            'technology': {'keywords': ['AI tools', 'SaaS', 'cloud computing', 'tech gadgets'], 'cpc_level': 'medium-high'},
            'health': {'keywords': ['fitness', 'diet plan', 'supplements', 'nutrition'], 'cpc_level': 'high'},
            'business': {'keywords': ['productivity tools', 'marketing', 'remote work'], 'cpc_level': 'medium-high'}
        }

    def generate_with_retry(self, prompt, max_retries=3):
        """429 에러 대응 재시도 로직"""
        for i in range(max_retries):
            try:
                time.sleep(2) # 기본 지연
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt
                )
                return response.text
            except Exception as e:
                # 할당량 초과 시에만 대기 후 재시도
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    wait_time = (i + 1) * 65
                    print(f"⚠️ 할당량 초과. {wait_time}초 후 재시도... ({i+1}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    print(f"❌ API 호출 오류: {e}")
                    raise e
        return None

    def get_blogger_service(self):
        """Blogger API 인증"""
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
        """주제 찾기"""
        niche = random.choice(list(self.profitable_niches.keys()))
        prompt = f"Find 3 trending topics for {niche}. Format as JSON: {{'niche': '{niche}', 'topics': [{{'title': '...', 'primary_keyword': '...', 'secondary_keywords': ['...'], 'description': '...'}}]}}"
        text = self.generate_with_retry(prompt)
        if not text: return None
        try:
            match = re.search(r'\{.*\}', text, re.DOTALL)
            return json.loads(match.group()) if match else None
        except: return None

    def generate_monetized_blog_post(self, topic):
        """상세 포스팅 생성 (이미지 마커 포함)"""
        current_year = datetime.now().year
        prompt = f"Write a 2000-word HTML blog post about: {topic['title']}. Use <h2>. Include [IMAGE: description] 3 times. Focus keyword: {topic['primary_keyword']}. Year: {current_year}."
        content = self.generate_with_retry(prompt)
        if not content: return None
        if "```html" in content:
            content = content.split("```html")[1].split("```")[0].strip()
        return {
            'title': topic['title'].replace('2024', str(current_year)),
            'content': content,
            'tags': topic.get('secondary_keywords', [])[:5],
            'primary_keyword': topic['primary_keyword']
        }

    def get_unsplash_image(self, keyword):
        """Unsplash 이미지 가져오기"""
        try:
            url = "[https://api.unsplash.com/photos/random](https://api.unsplash.com/photos/random)"
            params = {'query': keyword, 'client_id': self.unsplash_api_key, 'orientation': 'landscape'}
            res = requests.get(url, params=params)
            if res.status_code == 200:
                data = res.json()
                return {'url': data['urls']['regular'], 'credit': f"Photo by {data['user']['name']} on Unsplash"}
        except: return None
        return None

    def publish_to_blogger(self, post_data):
        """Blogger 발행 (이미지 여러 장 포함)"""
        try:
            content = post_data['content']
            # 이미지 마커를 실제 이미지 태그로 교체
            for _ in range(3):
                img = self.get_unsplash_image(post_data['primary_keyword'])
                if img:
                    img_html = f"<div style='text-align:center;margin:20px;'><img src='{img['url']}' style='max-width:100%;border-radius:8px;'><p style='font-size:12px;'>{img['credit']}</p></div>"
                    content = re.sub(r'\[IMAGE:.*?\]', img_html, content, count=1)
            
            service = self.get_blogger_service()
            post = {'kind': 'blogger#post', 'blog': {'id': self.blog_id}, 'title': post_data['title'], 'content': content, 'labels': post_data['tags']}
            result = service.posts().insert(blogId=self.blog_id, body=post).execute()
            return {'success': True, 'url': result.get('url')}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def run(self):
        print(f"💰 시작 시간: {datetime.now()}")
        data = self.get_high_value_topics()
        if not data: return
        topic = data['topics'][0]
        print(f"🎯 주제: {topic['title']}")
        
        post = self.generate_monetized_blog_post(topic)
        if not post: return
        
        result = self.publish_to_blogger(post)
        if result['success']: print(f"🎉 발행 성공: {result['url']}")
        else: print(f"❌ 실패: {result['error']}")

if __name__ == "__main__":
    ProfitOptimizedBlogSystem().run()
