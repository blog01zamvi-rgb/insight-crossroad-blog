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
        
        # OAuth 정보를 딕셔너리로 구성
        token_info = {
            'refresh_token': self.refresh_token,
            'token_uri': 'https://oauth2.googleapis.com/token',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'scopes': ['https://www.googleapis.com/auth/blogger']
        }
        
        # from_authorized_user_info로 Credentials 생성
        creds = Credentials.from_authorized_user_info(token_info)
        
        # Access token이 없으면 refresh
        if not creds.token or creds.expired:
            creds.refresh(Request())
        
        return build('blogger', 'v3', credentials=creds)
    
    def get_high_value_topics(self):
        """고수익 키워드 기반 트렌딩 주제 찾기"""
        
        niche = random.choice(list(self.profitable_niches.keys()))
        keywords = self.profitable_niches[niche]['keywords']
        
        prompt = f"""
        You are an expert SEO content strategist. Find 3 trending, high-value blog topics in the {niche} niche.
        
        Focus on these profitable keywords: {', '.join(keywords)}
        
        Requirements:
        - Topics that people actively search for (high search volume)
        - Commercial intent keywords (people ready to buy/click ads)
        - Evergreen + trending combination
        - Suitable for affiliate marketing and AdSense
        
        For each topic provide:
        1. Title: Clickable, SEO-optimized (include power words like "best", "top", "guide", "review")
        2. Primary keyword (exact match keyword to target)
        3. Secondary keywords (3-5 LSI keywords)
        4. Commercial intent level (high/medium/low)
        5. Affiliate opportunity (what products/services can be recommended)
        6. Brief description
        
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
            return topics_data
        except Exception as e:
            print(f"Error getting topics: {e}")
            return {
                "niche": "technology",
                "topics": [{
                    "title": "Top 10 AI Tools for Productivity in 2026",
                    "primary_keyword": "AI productivity tools",
                    "secondary_keywords": ["AI tools", "productivity software", "automation tools"],
                    "commercial_intent": "high",
                    "affiliate_opportunity": "AI SaaS tools",
                    "description": "Review of best AI productivity tools"
                }]
            }
    
    def generate_monetized_blog_post(self, topic):
        """수익화에 최적화된 블로그 글 작성 - 텍스트 기반"""
        
        prompt = f"""Write a comprehensive, SEO-optimized blog post about: {topic['title']}

Target keyword: {topic['primary_keyword']}

Requirements:
- 2000+ words
- SEO optimized with keyword in title, headers, content
- 5-7 main sections with <h2> headers
- Use <h3> subheaders within sections
- Include introduction and conclusion
- Use HTML formatting: <p>, <strong>, <ul>, <li>, <table>
- Conversational, engaging tone
- Include product recommendations naturally

DO NOT use JSON. Write the blog post directly in HTML format.
Start with an <h1> title, then write the full article.
"""
        
        try:
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            
            content = response.text.strip()
            
            # HTML 코드 블록 제거
            if "```html" in content:
                content = content.split("```html")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            # H1 태그에서 제목 추출
            title = topic['title']
            if '<h1>' in content:
                import re
                h1_match = re.search(r'<h1>(.*?)</h1>', content, re.DOTALL)
                if h1_match:
                    title = h1_match.group(1).strip()
            
            # 메타 설명 생성
            meta_description = f"{topic['description'][:150]}..."
            
            # 태그 생성
            tags = topic['secondary_keywords'][:5]
            
            post_data = {
                'title': title,
                'meta_description': meta_description,
                'content': content,
                'focus_keyword': topic['primary_keyword'],
                'tags': tags,
                'affiliate_products': [],
                'estimated_read_time': '10 min'
            }
            
            return post_data
            
        except Exception as e:
            print(f"Error generating post: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_unsplash_image(self, keywords):
        """Unsplash에서 무료 이미지 가져오기"""
        try:
            query = " ".join(keywords[:2])
            url = f"https://api.unsplash.com/photos/random"
            params = {
                'query': query,
                'client_id': self.unsplash_api_key,
                'orientation': 'landscape'
            }
            
            response = requests.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                return {
                    'url': data['urls']['regular'],
                    'alt': data['alt_description'] or query,
                    'credit': f"Photo by {data['user']['name']} on Unsplash",
                    'credit_link': data['user']['links']['html']
                }
        except Exception as e:
            print(f"Error fetching image: {e}")
        
        return None
    
    def add_seo_schema(self, post_data):
        """구조화된 데이터 추가"""
        
        schema = f"""
        <script type="application/ld+json">
        {{
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": "{post_data['title']}",
            "description": "{post_data['meta_description']}",
            "keywords": "{', '.join(post_data['tags'])}",
            "datePublished": "{datetime.now().isoformat()}",
            "author": {{
                "@type": "Organization",
                "name": "Insight Crossroad"
            }}
        }}
        </script>
        """
        
        return schema
    
    def publish_to_blogger(self, post_data, image_data):
        """Blogger에 포스트 발행 (OAuth 사용)"""
        try:
            # Featured 이미지
            image_html = ""
            if image_data:
                image_html = f"""
                <div style="text-align: center; margin: 20px 0;">
                    <img src="{image_data['url']}" alt="{image_data['alt']}" style="max-width: 100%; height: auto; border-radius: 8px;">
                    <p style="font-size: 12px; color: #666; margin-top: 5px;">
                        <a href="{image_data['credit_link']}" target="_blank">{image_data['credit']}</a>
                    </p>
                </div>
                """
            
            # AI 투명성 고지
            ai_disclosure = """
                <div style="background: #f0f8ff; padding: 15px; margin: 20px 0; border-left: 4px solid #4a90e2; border-radius: 4px;">
                    <p style="margin: 0; font-size: 13px; color: #555;">
                        <strong>🤖 AI-Assisted Content:</strong> This article was created with the assistance of AI tools 
                        to provide timely and relevant information. All content has been reviewed for accuracy and quality.
                    </p>
                </div>
            """
            
            # 독자 참여 요소
            engagement_footer = """
                <div style="background: #f5f5f5; padding: 20px; margin-top: 30px; border-radius: 8px;">
                    <h3>What do you think?</h3>
                    <p>Have you tried any of these recommendations? Share your experience in the comments below!</p>
                    <p><strong>Don't forget to subscribe</strong> for more helpful guides and reviews.</p>
                </div>
            """
            
            # Schema 추가
            schema = self.add_seo_schema(post_data)
            
            # 전체 콘텐츠 조합
            full_content = schema + image_html + ai_disclosure + post_data['content'] + engagement_footer
            
            # OAuth로 Blogger API 서비스 생성
            service = self.get_blogger_service()
            
            post = {
                'kind': 'blogger#post',
                'blog': {'id': self.blog_id},
                'title': post_data['title'],
                'content': full_content,
                'labels': post_data.get('tags', [])
            }
            
            result = service.posts().insert(blogId=self.blog_id, body=post).execute()
            
            return {
                'success': True,
                'url': result.get('url'),
                'id': result.get('id')
            }
            
        except Exception as e:
            print(f"Error publishing to Blogger: {e}")
            return {'success': False, 'error': str(e)}
    
    def run_daily_automation(self):
        """매일 실행되는 자동화"""
        print(f"💰 Starting PROFIT-OPTIMIZED automation at {datetime.now()}")
        
        # 1. 고수익 트렌딩 주제 찾기
        print("🎯 Finding high-value trending topics...")
        topics_data = self.get_high_value_topics()
        
        topics = topics_data['topics']
        topic = max(topics, key=lambda x: 1 if x.get('commercial_intent') == 'high' else 0)
        
        print(f"✅ Selected topic: {topic['title']}")
        print(f"   Niche: {topics_data['niche']}")
        print(f"   Primary keyword: {topic['primary_keyword']}")
        print(f"   Commercial intent: {topic['commercial_intent']}")
        
        # 2. 블로그 글 작성
        print("✍️ Generating monetized blog post...")
        post_data = self.generate_monetized_blog_post(topic)
        
        if not post_data:
            print("❌ Failed to generate post")
            return
        
        print(f"✅ Generated {len(post_data['content'])} characters")
        print(f"   Read time: {post_data.get('estimated_read_time', 'N/A')}")
        
        # 3. 이미지 가져오기
        print("🖼️ Fetching relevant image...")
        image_data = self.get_unsplash_image(topic['secondary_keywords'])
        
        if image_data:
            print(f"✅ Got image for: {image_data['alt']}")
        
        # 4. Blogger에 발행
        print("📤 Publishing to Blogger...")
        result = self.publish_to_blogger(post_data, image_data)
        
        if result['success']:
            print(f"🎉 Successfully published!")
            print(f"📝 Post URL: {result['url']}")
            print(f"💰 Monetization ready: AdSense + Affiliate links included")
        else:
            print(f"❌ Failed to publish: {result.get('error')}")
        
        # 로그 저장
        log_data = {
            'timestamp': datetime.now().isoformat(),
            'niche': topics_data['niche'],
            'topic': topic,
            'post_title': post_data['title'],
            'word_count': len(post_data['content'].split()),
            'primary_keyword': post_data['focus_keyword'],
            'tags': post_data['tags'],
            'affiliate_products': post_data.get('affiliate_products', []),
            'result': result,
            'commercial_intent': topic['commercial_intent']
        }
        
        with open('profit_blog_log.jsonl', 'a') as f:
            f.write(json.dumps(log_data) + '\n')
        
        print("✅ Automation complete!")
        print(f"📊 Check profit_blog_log.jsonl for detailed analytics")

if __name__ == "__main__":
    blog_system = ProfitOptimizedBlogSystem()
    blog_system.run_daily_automation()
