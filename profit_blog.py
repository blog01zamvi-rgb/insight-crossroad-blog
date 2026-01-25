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
        # API 키 설정
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        self.unsplash_api_key = os.getenv('UNSPLASH_API_KEY')
        self.blog_id = os.getenv('BLOGGER_BLOG_ID')
        
        # OAuth 설정
        self.client_id = os.getenv('OAUTH_CLIENT_ID')
        self.client_secret = os.getenv('OAUTH_CLIENT_SECRET')
        self.refresh_token = os.getenv('OAUTH_REFRESH_TOKEN')
        
        # Gemini 클라이언트 설정 - 최신 SDK v1 방식
        self.client = genai.Client(api_key=self.gemini_api_key)
        # 404 에러 방지를 위해 모델명 앞에 'models/'를 붙입니다.
        self.model_name = 'models/gemini-1.5-flash'
        
        # 고수익 키워드 카테고리
        self.profitable_niches = {
            'finance': {'keywords': ['credit card', 'insurance', 'investing', 'mortgage'], 'cpc_level': 'high'},
            'technology': {'keywords': ['AI tools', 'SaaS', 'cloud computing', 'tech gadgets'], 'cpc_level': 'medium-high'},
            'health': {'keywords': ['fitness', 'diet plan', 'supplements', 'nutrition'], 'cpc_level': 'high'},
            'business': {'keywords': ['productivity tools', 'marketing', 'remote work'], 'cpc_level': 'medium-high'}
        }

    def generate_with_retry(self, prompt, max_retries=3):
        """429 Resource Exhausted 에러 발생 시 자동 재시도 로직"""
        for i in range(max_retries):
            try:
                # RPM 제한 방지를 위한 짧은 대기
                time.sleep(2)
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt
                )
                return response.text
            except Exception as e:
                # 할당량 초과(429) 에러 발생 시
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    wait_time = (i + 1) * 65  # 1분 이상 대기
                    print(f"⚠️ 할당량 초과. {wait_time}초 후 재시도합니다... ({i+1}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    print(f"❌ API 호출 중 오류 발생: {e}")
                    raise e
        return None

    def get_blogger_service(self):
        """OAuth로 Blogger API 서비스 생성"""
        from google.auth.transport.requests import Request
        authorized_user_info = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'refresh_token': self.refresh_token,
            'token_uri': 'https://oauth2.googleapis.com/token'
        }
        creds = Credentials.from_authorized_user_info(
            authorized_user_info,
            scopes=['https://www.googleapis.com/auth/blogger']
        )
        creds.refresh(Request())
        return build('blogger', 'v3', credentials=creds)

    def get_high_value_topics(self):
        """수익형 주제 찾기 (재시도 로직 적용)"""
        niche = random.choice(list(self.profitable_niches.keys()))
        keywords = self.profitable_niches[niche]['keywords']
        
        prompt = f"Find 3 trending, high-value blog topics in the {niche} niche. Focus: {', '.join(keywords)}. Format as JSON with niche and topics list."
        
        text = self.generate_with_retry(prompt)
        if not text: return None
        
        try:
            # JSON 추출 로직
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            return json.loads(text.strip())
        except:
            return None

    def generate_monetized_blog_post(self, topic):
        """상세 블로그 글 생성 (기존 프롬프트 규칙 유지 + 재시도 적용)"""
        current_year = datetime.now().year
        prompt = f"Write a professional 2000-word SEO HTML blog post about: {topic['title']}. Use <h2> for sections. Include [IMAGE: description] markers. Focus keyword: {topic['primary_keyword']}. Year: {current_year}."
        
        content = self.generate_with_retry(prompt)
        if not content: return None
        
        if "```html" in content:
            content = content.split("```html")[1].split("```")[0].strip()
        
        return {
            'title': topic['title'].replace('2024', str(current_year)),
            'content': content,
            'meta_description': topic.get('description', '')[:150],
            'tags': topic.get('secondary_keywords', [])[:5],
            'focus_keyword': topic['primary_keyword']
        }

    def get_unsplash_image(self, keywords):
        """이미지 가져오기"""
        try:
            url = f"[https://api.unsplash.com/photos/random](https://api.unsplash.com/photos/random)"
            params = {'query': " ".join(keywords[:2]), 'client_id': self.unsplash_api_key, 'orientation': 'landscape'}
            response = requests.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                return {'url': data['urls']['regular'], 'alt': data['alt_description'] or "blog image"}
        except: return None

    def publish_to_blogger(self, post_data, image_data):
        """Blogger에 최종 발행"""
        try:
            image_html = f"<div style='text-align:center;margin:20px;'><img src='{image_data['url']}' style='max-width:100%;border-radius:8px;'></div>" if image_data else ""
            full_content = image_html + post_data['content']
            
            service = self.get_blogger_service()
            post = {
                'kind': 'blogger#post',
                'blog': {'id': self.blog_id},
                'title': post_data['title'],
                'content': full_content,
                'labels': post_data['tags']
            }
            result = service.posts().insert(blogId=self.blog_id, body=post).execute()
            return {'success': True, 'url': result.get('url')}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def run_daily_automation(self):
        print(f"💰 Starting automation at {datetime.now()}")
        
        topics_data = self.get_high_value_topics()
        if not topics_data or 'topics' not in topics_data:
            print("❌ 주제를 가져오지 못했습니다.")
            return
            
        topic = topics_data['topics'][0]
        print(f"🎯 주제 선정: {topic['title']}")
        
        post_data = self.generate_monetized_blog_post(topic)
        if not post_data:
            print("❌ 글 생성에 실패했습니다.")
            return
            
        image_data = self.get_unsplash_image(post_data['tags'] if post_data['tags'] else [topic['primary_keyword']])
        
        result = self.publish_to_blogger(post_data, image_data)
        
        if result['success']:
            print(f"🎉 발행 성공: {result['url']}")
        else:
            print(f"❌ 발행 실패: {result['error']}")

if __name__ == "__main__":
    blog_system = ProfitOptimizedBlogSystem()
    blog_system.run_daily_automation()
