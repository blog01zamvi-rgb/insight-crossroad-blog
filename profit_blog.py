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
        
        # from_authorized_user_info에 필요한 정확한 딕셔너리 형식
        authorized_user_info = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'refresh_token': self.refresh_token,
            'token_uri': 'https://oauth2.googleapis.com/token'  # 필수!
        }
        
        print("\n🔐 Credentials 생성 중...")
        
        try:
            # Credentials 생성 (scopes는 별도 파라미터로)
            creds = Credentials.from_authorized_user_info(
                authorized_user_info,
                scopes=['https://www.googleapis.com/auth/blogger']
            )
            print("✓ Credentials 객체 생성 성공")
            
            # Access token 받기
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
            
            # 상세 에러 정보
            if hasattr(e, 'error_details'):
                print(f"에러 상세: {e.error_details}")
            
            import traceback
            print("\n상세 스택 트레이스:")
            traceback.print_exc()
            print("="*60 + "\n")
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
        
        Requirements:
        - Topics that people actively search for (high search volume)
        - Commercial intent keywords (people ready to buy/click ads)
        - Evergreen + trending combination
        - Suitable for affiliate marketing and AdSense
        - Use {current_year} in titles (e.g., "Best Tools for {current_year}")
        
        For each topic provide:
        1. Title: Clickable, SEO-optimized with {current_year} (include "best", "top", "guide", "review")
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
            
            # 모든 제목에서 2024, 2025를 현재 연도로 강제 변경
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

🚨 CRITICAL RULES - VIOLATIONS ARE SERIOUS 🚨

1. FACTS ONLY - ZERO TOLERANCE FOR FABRICATION:
   ❌ DO NOT invent statistics ("73% of users..." - NO!)
   ❌ DO NOT make up pricing (if unsure, say "pricing available on their website")
   ❌ DO NOT create fake testimonials or quotes
   ❌ DO NOT guess at features - only mention what you KNOW exists
   ❌ DO NOT invent case studies or success stories
   ❌ DO NOT make claims like "saves 10 hours per week" without real data
   
   ✅ DO use general statements: "can help save time", "many users find helpful"
   ✅ DO say "as of {current_year}" when mentioning anything time-sensitive
   ✅ DO admit limitations: "specific features may vary", "check official website for current pricing"
   ✅ DO focus on well-known, publicly documented facts

2. CURRENT & ACCURATE INFORMATION:
   - Update ALL years to {current_year}
   - Use "as of {current_month}" for time-sensitive info
   - Only mention tools/features that exist in {current_year}
   - If a tool launched recently, say "recently launched" not specific dates unless certain
   - Pricing: use "approximately" or "starting from" - never exact unless 100% sure

3. VERIFIABLE CLAIMS ONLY:
   ✅ "ChatGPT is developed by OpenAI" (known fact)
   ✅ "Many businesses use AI for automation" (general truth)
   ✅ "Google Workspace integrates with various AI tools" (known fact)
   ❌ "87% of small businesses saw 40% productivity increase" (unless you have the source!)
   ❌ "This tool reduced email time by 5.3 hours weekly" (too specific without source)

4. HONESTY WHEN UNCERTAIN:
   - "This tool is known for [general capability]" (safe)
   - "Features and pricing available on official website" (honest)
   - "Many tools in this category offer similar functionality" (true)
   - "Specific capabilities may vary by plan" (accurate)

5. TONE & STYLE (Still Natural, But Factual):
   - Write conversationally but stick to facts
   - Use "can", "may", "often", "typically" instead of absolute claims
   - Include opinions on general usefulness, not fake metrics
   - Be helpful without exaggerating

6. STRUCTURE:
   - Introduction: Real problem statement (150 words)
   - 5-7 tool sections (focus on well-known tools you're certain about)
   - For each tool:
     * What it is (factual)
     * General capabilities (known features only)
     * Who it's for (general use cases)
     * Note to check official site for current details
   - Conclusion: Practical advice (100 words)

7. HTML & IMAGES:
   - Use <h2> for 5-7 sections
   - Add [IMAGE: description] 3-4 times
   - 2000-2500 words
   - <p>, <ul>, <li> formatting

EXAMPLE OF GOOD (FACTUAL) WRITING:

❌ BAD (Fabricated):
"According to a 2024 study, 82% of users saved exactly 7.3 hours per week using this tool, with ROI of 340% in the first month."

✅ GOOD (Factual):
"This tool helps automate routine tasks. Many users report time savings, though specific results vary by use case. Pricing and feature details are available on the official website."

❌ BAD (Made up):
"Launched in March 2024 with revolutionary AI that increased productivity by 500% for Fortune 500 companies."

✅ GOOD (Honest):
"This AI tool has gained popularity in {current_year} for its automation capabilities. It's used by various businesses, from small teams to larger organizations."

REMEMBER:
- If you don't know → Don't write it
- If you're unsure → Use general language
- If it's time-sensitive → Add "as of {current_year}"
- Focus on established, well-known facts

OUTPUT: Complete HTML blog post. Factual, current, honest. Start with <h1>. Include [IMAGE: desc] markers.
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
            
            # H1 태그에서 제목 추출 및 연도 업데이트
            title = topic['title'].replace('2024', str(current_year)).replace('2025', str(current_year))
            
            if '<h1>' in content:
                import re
                h1_match = re.search(r'<h1>(.*?)</h1>', content, re.DOTALL)
                if h1_match:
                    title = h1_match.group(1).strip().replace('2024', str(current_year)).replace('2025', str(current_year))
            
            # 콘텐츠에서 연도 업데이트
            content = content.replace('2024', str(current_year)).replace('2025', str(current_year))
            
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
        # 🔥 이미지 플레이스홀더 자동 교체 🔥
        content = content.replace(
            '[IMAGE:', 
            f'<img src="https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=800" alt="'
        ).replace(
            ']',
            '" style="max-width:100%;height:auto;border-radius:8px;margin:20px 0;">'
        )
        post_data['content'] = content  # 업데이트
            return post_data
            
        except Exception as e:
            print(f"Error generating post: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_unsplash_image(self, keywords):
        """Unsplash에서 무료 이미지 여러 개 가져오기"""
        try:
            query = " ".join(keywords[:2])
            url = f"https://api.unsplash.com/photos/random"
            params = {
                'query': query,
                'client_id': self.unsplash_api_key,
                'orientation': 'landscape',
                'count': 1  # 일단 1개만
            }
            
            response = requests.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                # 배열로 반환되므로 첫번째 항목 사용
                if isinstance(data, list):
                    data = data[0]
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
        """Blogger에 포스트 발행 (OAuth 사용) - 이미지 여러 개 삽입"""
        try:
            print("\n" + "="*60)
            print("📤 Blogger 발행 프로세스 시작")
            print("="*60)
            
            # 여러 이미지 가져오기 (3-4개)
            import time
            images = []
            if image_data:
                images.append(image_data)
                print(f"✓ Featured 이미지: {image_data['alt'][:50]}")
            
            # 추가 이미지 2-3개 더 가져오기
            for i in range(2):
                try:
                    time.sleep(1)  # API 제한 방지
                    query = post_data.get('tags', ['business', 'technology'])[i % len(post_data.get('tags', ['business']))]
                    url = f"https://api.unsplash.com/photos/random"
                    params = {
                        'query': query,
                        'client_id': self.unsplash_api_key,
                        'orientation': 'landscape'
                    }
                    response = requests.get(url, params=params)
                    if response.status_code == 200:
                        data = response.json()
                        if isinstance(data, list):
                            data = data[0]
                        images.append({
                            'url': data['urls']['regular'],
                            'alt': data['alt_description'] or query,
                            'credit': f"Photo by {data['user']['name']} on Unsplash",
                            'credit_link': data['user']['links']['html']
                        })
                        print(f"✅ Got additional image {i+2}")
                except Exception as e:
                    print(f"⚠️ Failed to get additional image {i+2}: {e}")
            
            print(f"\n📊 총 {len(images)}개 이미지 준비됨")
            
            # Featured 이미지 (맨 위)
            image_html = ""
            if images and images[0]:
                img = images[0]
                image_html = f"""
                <div style="text-align: center; margin: 20px 0;">
                    <img src="{img['url']}" alt="{img['alt']}" style="max-width: 100%; height: auto; border-radius: 8px;">
                    <p style="font-size: 12px; color: #666; margin-top: 5px;">
                        <a href="{img['credit_link']}" target="_blank">{img['credit']}</a>
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
            
            # 콘텐츠를 섹션으로 나누고 중간에 이미지 삽입
            content = post_data['content']
            
            print("📝 콘텐츠 처리 중...")
            
            # H2 태그로 섹션 나누기
            import re
            sections = re.split(r'(<h2>.*?</h2>)', content)
            
            # 중간 이미지들을 섹션 사이에 삽입
            enhanced_content = ""
            image_index = 1  # 첫 번째 이미지는 이미 사용
            section_count = 0
            
            for section in sections:
                enhanced_content += section
                
                # H2 태그마다 섹션 카운트
                if '<h2>' in section:
                    section_count += 1
                    
                    # 3번째, 5번째 섹션 뒤에 이미지 삽입
                    if section_count in [3, 5] and image_index < len(images) and images[image_index]:
                        img = images[image_index]
                        enhanced_content += f"""
                        <div style="text-align: center; margin: 30px 0;">
                            <img src="{img['url']}" alt="{img['alt']}" style="max-width: 100%; height: auto; border-radius: 8px;">
                            <p style="font-size: 12px; color: #666; margin-top: 5px;">
                                <a href="{img['credit_link']}" target="_blank">{img['credit']}</a>
                            </p>
                        </div>
                        """
                        print(f"✓ 이미지 {image_index+1} 삽입 (섹션 {section_count} 뒤)")
                        image_index += 1
            
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
            full_content = schema + image_html + ai_disclosure + enhanced_content + engagement_footer
            
            print(f"✓ 최종 콘텐츠 길이: {len(full_content)} 문자")
            print(f"✓ 제목: {post_data['title']}")
            print(f"✓ 태그: {', '.join(post_data.get('tags', []))}")
            
            # OAuth로 Blogger API 서비스 생성
            print("\n🔐 OAuth 인증 시작...")
            service = self.get_blogger_service()
            
            print("\n📮 Blogger API 호출 준비...")
            print(f"✓ Blog ID: {self.blog_id}")
            print(f"✓ Post Title: {post_data['title'][:50]}...")
            
            post = {
                'kind': 'blogger#post',
                'blog': {'id': self.blog_id},
                'title': post_data['title'],
                'content': full_content,
                'labels': post_data.get('tags', []),
                'status': 'DRAFT'
            }
            
            print("\n🚀 Blogger API 호출 중...")
            result = service.posts().insert(blogId=self.blog_id, body=post).execute()
            
            print("✅ 발행 성공!")
            print(f"URL: {result.get('url')}")
            print("="*60 + "\n")
            
            return {
                'success': True,
                'url': result.get('url'),
                'id': result.get('id')
            }
            
        except Exception as e:
            print(f"\n❌ Blogger 발행 에러!")
            print(f"에러 타입: {type(e).__name__}")
            print(f"에러 메시지: {e}")
            
            # HTTP 에러 상세 정보
            if hasattr(e, 'resp'):
                print(f"HTTP 상태 코드: {e.resp.status}")
                print(f"응답 내용: {e.resp.get('content', 'N/A')}")
            
            import traceback
            print("\n상세 스택 트레이스:")
            traceback.print_exc()
            print("="*60 + "\n")
            
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
