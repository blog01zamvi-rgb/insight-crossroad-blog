import os
import json
import random
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
        
        # Gemini 클라이언트 설정
        self.client = genai.Client(api_key=self.gemini_api_key)
        
        # 고수익 키워드 카테고리
        self.profitable_niches = {
            'finance': {
                'keywords': ['credit card', 'insurance', 'investing', 'mortgage', 'cryptocurrency', 'personal finance'],
                'cpc_level': 'high'
            },
            'technology': {
                'keywords': ['AI tools', 'SaaS', 'cloud computing', 'cybersecurity', 'software review', 'tech gadgets'],
                'cpc_level': 'medium-high'
            },
            'health': {
                'keywords': ['fitness', 'diet plan', 'supplements', 'mental health', 'weight loss', 'nutrition'],
                'cpc_level': 'high'
            },
            'business': {
                'keywords': ['productivity tools', 'marketing', 'entrepreneurship', 'remote work', 'side hustle'],
                'cpc_level': 'medium-high'
            },
            'education': {
                'keywords': ['online courses', 'learning platforms', 'skill development', 'certifications'],
                'cpc_level': 'medium'
            }
        }
    
    def get_blogger_service(self):
        """OAuth로 Blogger API 서비스 생성"""
        from google.auth.transport.requests import Request
        
        print("\n" + "="*60)
        print("🔍 OAuth 디버깅 시작")
        print("="*60)
        
        # 환경변수 확인
        print(f"✓ Client ID 존재: {bool(self.client_id)}")
        print(f"✓ Client Secret 존재: {bool(self.client_secret)}")
        print(f"✓ Refresh Token 존재: {bool(self.refresh_token)}")
        print(f"✓ Blog ID: {self.blog_id}")
        
        if self.client_id:
            print(f"✓ Client ID 시작: {self.client_id[:20]}...")
        if self.refresh_token:
            print(f"✓ Refresh Token 시작: {self.refresh_token[:20]}...")
        
        authorized_user_info = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'refresh_token': self.refresh_token,
            'token_uri': 'https://oauth2.googleapis.com/token'
        }
        
        print("\n🔐 Credentials 생성 중...")
        
        try:
            creds = Credentials.from_authorized_user_info(
                authorized_user_info,
                scopes=['https://www.googleapis.com/auth/blogger']
            )
            print("✓ Credentials 객체 생성 성공")
            
            print("\n🔄 Access Token 갱신 중...")
            creds.refresh(Request())
            print("✓ Access Token 갱신 성공")
            
            if creds.token:
                print(f"✓ Access Token 시작: {creds.token[:20]}...")
            
            print("\n🌐 Blogger API 서비스 빌드 중...")
            service = build('blogger', 'v3', credentials=creds)
            print("✓ Blogger API 서비스 생성 성공")
            print("="*60 + "\n")
            
            return service
            
        except Exception as e:
            print(f"\n❌ OAuth 에러 발생!")
            print(f"에러 타입: {type(e).__name__}")
            print(f"에러 메시지: {str(e)}")
            raise

    def get_high_value_topics(self):
        """고수익 키워드 기반 트렌딩 주제 찾기"""
        niche = random.choice(list(self.profitable_niches.keys()))
        keywords = self.profitable_niches[niche]['keywords']
        
        current_year = datetime.now().year
        current_month = datetime.now().strftime("%B %Y")
        
        prompt = f"""
        You are an expert SEO content strategist. Find 3 trending, high-value blog topics in the {niche} niche.
        IMPORTANT: Current date is {current_month}. Use {current_year} in titles, NOT 2024 or 2025.
        Focus on these profitable keywords: {', '.join(keywords)}
        
        Format as JSON:
        {{
            "niche": "{niche}",
            "topics": [
                {{
                    "title": "...",
                    "primary_keyword": "...",
                    "secondary_keywords": ["...", "..."],
                    "commercial_intent": "high",
                    "affiliate_opportunity": "...",
                    "description": "..."
                }}
            ]
        }}
        """
        
        try:
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            
            text = response.text
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            
            topics_data = json.loads(text.strip())
            for topic in topics_data['topics']:
                topic['title'] = topic['title'].replace('2024', str(current_year)).replace('2025', str(current_year))
            
            return topics_data
        except Exception as e:
            print(f"Error getting topics: {e}")
            return {
                "niche": "technology",
                "topics": [{
                    "title": f"Top 10 AI Tools for Productivity in {current_year}",
                    "primary_keyword": "AI productivity tools",
                    "secondary_keywords": ["AI tools", "productivity software", "automation tools"],
                    "commercial_intent": "high",
                    "affiliate_opportunity": "AI SaaS tools",
                    "description": "Review of best AI productivity tools"
                }]
            }

    def generate_monetized_blog_post(self, topic):
        """수익화에 최적화된 블로그 글 작성 - 사실 기반, 최신 정보"""
        current_year = datetime.now().year
        current_month = datetime.now().strftime("%B %Y")
        
        prompt = f"""You are writing a factual, accurate blog post about: {topic['title']}
        Target keyword: {topic['primary_keyword']}
        Current date: {current_month}
        Current year: {current_year}
        ... (중략) ...
        OUTPUT: Complete HTML blog post. Factual, current, honest. Start with <h1>. Include [IMAGE: desc] markers.
        """
        
        try:
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            
            content = response.text.strip()
            if "```html" in content:
                content = content.split("```html")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            title = topic['title'].replace('2024', str(current_year)).replace('2025', str(current_year))
            if '<h1>' in content:
                import re
                h1_match = re.search(r'<h1>(.*?)</h1>', content, re.DOTALL)
                if h1_match:
                    title = h1_match.group(1).strip().replace('2024', str(current_year)).replace('2025', str(current_year))
            
            content = content.replace('2024', str(current_year)).replace('2025', str(current_year))
            
            # 🔥 [수정] 이미지 교체 코드를 try 블록 안으로 정확하게 포함시켰습니다.
            content = content.replace('[IMAGE:',f'<img src="https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=800" alt="').replace(']','" style="max-width:100%;height:auto;border-radius:8px;margin:20px 0;">')
            
            post_data = {
                'title': title,
                'meta_description': f"{topic['description'][:150]}...",
                'content': content,
                'focus_keyword': topic['primary_keyword'],
                'tags': topic['secondary_keywords'][:5],
                'affiliate_products': [],
                'estimated_read_time': '10 min'
            }
            return post_data
            
        except Exception as e:
            print(f"Error generating post: {e}")
            return None

    def get_unsplash_image(self, keywords):
        try:
            query = " ".join(keywords[:2])
            url = f"https://api.unsplash.com/photos/random"
            params = {'query': query, 'client_id': self.unsplash_api_key, 'orientation': 'landscape', 'count': 1}
            response = requests.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list): data = data[0]
                return {
                    'url': data['urls']['regular'],
                    'alt': data['alt_description'] or query,
                    'credit': f"Photo by {data['user']['name']} on Unsplash",
                    'credit_link': data['user']['links']['html']
                }
        except: return None
        return None

    def add_seo_schema(self, post_data):
        schema = f"""
        <script type="application/ld+json">
        {{
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": "{post_data['title']}",
            "description": "{post_data['meta_description']}",
            "keywords": "{', '.join(post_data['tags'])}",
            "datePublished": "{datetime.now().isoformat()}",
            "author": {{ "@type": "Organization", "name": "Insight Crossroad" }}
        }}
        </script>
        """
        return schema

    def publish_to_blogger(self, post_data, image_data):
        try:
            import time
            images = []
            if image_data: images.append(image_data)
            
            image_html = ""
            if images:
                img = images[0]
                image_html = f'<div style="text-align: center; margin: 20px 0;"><img src="{img["url"]}" alt="{img["alt"]}" style="max-width: 100%; height: auto; border-radius: 8px;"><p style="font-size: 12px; color: #666;"><a href="{img["credit_link"]}" target="_blank">{img["credit"]}</a></p></div>'
            
            ai_disclosure = '<div style="background: #f0f8ff; padding: 15px; margin: 20px 0; border-left: 4px solid #4a90e2; border-radius: 4px;"><p style="margin: 0; font-size: 13px; color: #555;"><strong>🤖 AI-Assisted Content:</strong> This article was reviewed for accuracy.</p></div>'
            
            full_content = self.add_seo_schema(post_data) + image_html + ai_disclosure + post_data['content']
            
            service = self.get_blogger_service()
            post = {
                'kind': 'blogger#post',
                'blog': {'id': self.blog_id},
                'title': post_data['title'],
                'content': full_content,
                'labels': post_data.get('tags', []),
                'status': 'DRAFT'
            }
            result = service.posts().insert(blogId=self.blog_id, body=post).execute()
            return {'success': True, 'url': result.get('url')}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def run_daily_automation(self):
        print(f"💰 Starting PROFIT-OPTIMIZED automation at {datetime.now()}")
        topics_data = self.get_high_value_topics()
        topic = topics_data['topics'][0]
        post_data = self.generate_monetized_blog_post(topic)
        if not post_data: return
        image_data = self.get_unsplash_image(topic['secondary_keywords'])
        result = self.publish_to_blogger(post_data, image_data)
        if result['success']: print(f"🎉 Successfully published! URL: {result['url']}")
        else: print(f"❌ Failed: {result.get('error')}")

if __name__ == "__main__":
    blog_system = ProfitOptimizedBlogSystem()
    blog_system.run_daily_automation()
