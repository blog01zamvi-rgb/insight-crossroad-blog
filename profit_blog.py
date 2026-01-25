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
        
        # 제휴 마케팅 설정
        self.amazon_tag = os.getenv('AMAZON_ASSOCIATE_TAG', '')
        
        # Gemini 클라이언트 및 모델 설정
        self.client = genai.Client(api_key=self.gemini_api_key)
        self.model_name = 'gemini-1.5-flash'  # 할당량이 넉넉한 1.5-flash로 고정
        
        # 고수익 키워드 카테고리
        self.profitable_niches = {
            'finance': {'keywords': ['credit card', 'insurance', 'investing', 'mortgage', 'cryptocurrency', 'personal finance'], 'cpc_level': 'high'},
            'technology': {'keywords': ['AI tools', 'SaaS', 'cloud computing', 'cybersecurity', 'software review', 'tech gadgets'], 'cpc_level': 'medium-high'},
            'health': {'keywords': ['fitness', 'diet plan', 'supplements', 'mental health', 'weight loss', 'nutrition'], 'cpc_level': 'high'},
            'business': {'keywords': ['productivity tools', 'marketing', 'entrepreneurship', 'remote work', 'side hustle'], 'cpc_level': 'medium-high'},
            'education': {'keywords': ['online courses', 'learning platforms', 'skill development', 'certifications'], 'cpc_level': 'medium'}
        }
    
    def generate_with_retry(self, prompt, max_retries=3):
        """429 Resource Exhausted 에러 발생 시 재시도 로직"""
        for i in range(max_retries):
            try:
                # API 호출 간 간격 두기 (RPM 제한 방지)
                time.sleep(2) 
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt
                )
                return response.text
            except Exception as e:
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    wait_time = (i + 1) * 60  # 60초, 120초... 점진적 대기
                    print(f"⚠️ 할당량 초과 발생. {wait_time}초 후 재시도합니다... ({i+1}/{max_retries})")
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
        """고수익 키워드 기반 트렌딩 주제 찾기"""
        niche = random.choice(list(self.profitable_niches.keys()))
        keywords = self.profitable_niches[niche]['keywords']
        
        prompt = f"""
        Find 3 trending, high-value blog topics in the {niche} niche.
        Focus on: {', '.join(keywords)}
        Format as JSON:
        {{
            "niche": "{niche}",
            "topics": [
                {{
                    "title": "...",
                    "primary_keyword": "...",
                    "secondary_keywords": ["...", "..."],
                    "commercial_intent": "high",
                    "description": "..."
                }}
            ]
        }}
        """
        
        try:
            text = self.generate_with_retry(prompt)
            if not text: return None
            
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            
            return json.loads(text.strip())
        except Exception as e:
            print(f"Error getting topics: {e}")
            return None
    
    def generate_monetized_blog_post(self, topic):
        """수익화 최적화 블로그 글 생성"""
        current_year = datetime.now().year
        prompt = f"Write a factual 2000-word HTML blog post about: {topic['title']}. Use <h2> for sections. Include [IMAGE: desc] placeholders. Year is {current_year}."
        
        try:
            content = self.generate_with_retry(prompt)
            if not content: return None
            
            if "```html" in content:
                content = content.split("```html")[1].split("```")[0].strip()
            
            # 후처리: 제목 및 메타 데이터 구성
            title = topic['title'].replace('2024', str(current_year))
            return {
                'title': title,
                'content': content,
                'meta_description': f"{topic['description'][:150]}...",
                'focus_keyword': topic['primary_keyword'],
                'tags': topic['secondary_keywords'][:5]
            }
        except Exception as e:
            print(f"Error generating post: {e}")
            return None

    def get_unsplash_image(self, keywords):
        """이미지 가져오기"""
        try:
            query = " ".join(keywords[:2])
            url = "[https://api.unsplash.com/photos/random](https://api.unsplash.com/photos/random)"
            params = {'query': query, 'client_id': self.unsplash_api_key, 'orientation': 'landscape'}
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

    def publish_to_blogger(self, post_data, image_data):
        """Blogger 발행"""
        try:
            image_html = f"<div style='text-align: center;'><img src='{image_data['url']}' style='max-width:100%'></div>" if image_data else ""
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
        print(f"💰 Starting at {datetime.now()}")
        
        # 1. 주제 선정
        topics_data = self.get_high_value_topics()
        if not topics_data: return
        topic = topics_data['topics'][0]
        
        # 2. 글 생성
        post_data = self.generate_monetized_blog_post(topic)
        if not post_data: return
        
        # 3. 이미지
        image_data = self.get_unsplash_image(topic['secondary_keywords'])
        
        # 4. 발행
        result = self.publish_to_blogger(post_data, image_data)
        
        if result['success']:
            print(f"🎉 Published: {result['url']}")
            # 로그 기록
            with open('profit_blog_log.jsonl', 'a') as f:
                f.write(json.dumps({'time': datetime.now().isoformat(), 'title': post_data['title'], 'url': result['url']}) + '\n')
        else:
            print(f"❌ Failed: {result['error']}")

if __name__ == "__main__":
    blog_system = ProfitOptimizedBlogSystem()
    blog_system.run_daily_automation()
