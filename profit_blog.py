import os
import json
import random
import re
import sys
import time
from datetime import datetime, timedelta
from urllib.parse import urlparse
import requests
from google import genai
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

class SecurityValidator:
    """보안 검증 클래스"""
    
    @staticmethod
    def sanitize_html(content):
        """위험한 HTML 태그 제거"""
        if not content:
            return content
        
        # 위험한 태그/속성 목록
        dangerous_patterns = [
            r'<script[^>]*>.*?</script>',
            r'<iframe[^>]*>.*?</iframe>',
            r'javascript:',
            r'onerror\s*=',
            r'onclick\s*=',
            r'onload\s*=',
            r'<object[^>]*>',
            r'<embed[^>]*>',
        ]
        
        cleaned = content
        for pattern in dangerous_patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE | re.DOTALL)
        
        return cleaned
    
    @staticmethod
    def validate_image_url(url):
        """이미지 URL 안전성 검증"""
        if not url:
            return False
        
        try:
            parsed = urlparse(url)
            
            # HTTPS만 허용
            if parsed.scheme != 'https':
                print(f"⚠️  보안: HTTP URL 차단됨")
                return False
            
            # Unsplash 도메인만 허용
            if 'unsplash.com' not in parsed.netloc and 'images.unsplash.com' not in parsed.netloc:
                print(f"⚠️  보안: 알 수 없는 이미지 소스 차단됨")
                return False
            
            return True
        except Exception as e:
            print(f"⚠️  보안: URL 검증 실패 - {e}")
            return False
    
    @staticmethod
    def validate_title(title):
        """제목 검증 및 정제"""
        if not title:
            return "Untitled Post"
        
        # 길이 제한 (200자)
        if len(title) > 200:
            title = title[:200]
        
        # 위험한 문자 제거
        title = re.sub(r'<[^>]+>', '', title)  # HTML 태그 제거
        title = title.replace('javascript:', '')
        title = title.replace('<script', '')
        
        return title.strip()
    
    @staticmethod
    def validate_json_size(text, max_size=500000):
        """응답 크기 검증 (500KB 제한)"""
        if not text:
            return False
        
        if len(text) > max_size:
            print(f"⚠️  보안: 응답이 너무 큼 ({len(text)} bytes)")
            return False
        
        return True

class ProfitOptimizedBlogSystem:
    def __init__(self):
        # 환경 변수 로드 확인
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        self.unsplash_api_key = os.getenv('UNSPLASH_API_KEY')
        self.blog_id = os.getenv('BLOGGER_BLOG_ID')
        
        if not self.gemini_api_key:
            print("❌ 오류: GEMINI_API_KEY가 설정되지 않았습니다.")
            sys.exit(1)

        self.client = genai.Client(api_key=self.gemini_api_key)
        
        self.profitable_niches = {
            'technology': ['AI', 'SaaS', 'Gadgets', 'Software', 'Cloud Computing'],
            'finance': ['Stocks', 'Crypto', 'Passive Income', 'Investing', 'Personal Finance'],
            'business': ['Productivity', 'Marketing', 'Entrepreneurship', 'Remote Work'],
            'health': ['Fitness', 'Nutrition', 'Mental Health', 'Wellness'],
            'education': ['Online Courses', 'Learning Platforms', 'Certifications', 'Study Tools', 'E-learning']
        }

    def get_blogger_service(self):
        from google.auth.transport.requests import Request
        authorized_user_info = {
            'client_id': os.getenv('OAUTH_CLIENT_ID'),
            'client_secret': os.getenv('OAUTH_CLIENT_SECRET'),
            'refresh_token': os.getenv('OAUTH_REFRESH_TOKEN'),
            'token_uri': 'https://oauth2.googleapis.com/token'
        }
        creds = Credentials.from_authorized_user_info(
            authorized_user_info, 
            scopes=['https://www.googleapis.com/auth/blogger']
        )
        creds.refresh(Request())
        return build('blogger', 'v3', credentials=creds)

    def run_daily_automation(self):
        # 짧은 랜덤 지연 (5~30분) - 자동화 티 안 나게, 무료 플랜 고려
        delay_minutes = random.randint(5, 30)
        print(f"⏰ 랜덤 대기 시작: {delay_minutes}분")
        print(f"🕐 예상 시작 시간: {datetime.now() + timedelta(minutes=delay_minutes)}")
        time.sleep(delay_minutes * 60)
        
        print(f"\n🚀 자동화 실제 시작: {datetime.now()}")
        print("=" * 60)
        
        # 보안 검증 인스턴스
        validator = SecurityValidator()
        
        # 1. 주제 생성
        try:
            niche = random.choice(list(self.profitable_niches.keys()))
            keywords = self.profitable_niches[niche]
            
            prompt = f"""Find 1 trending blog topic for {niche} in 2026. 
            Use keywords: {', '.join(keywords)}
            Return ONLY JSON like {{"title": "...", "keyword": "...", "description": "..."}}"""
            
            response = self.client.models.generate_content(
                model='gemini-2.5-flash', 
                contents=prompt
            )
            print("✅ Gemini 주제 생성 응답 수신 성공")
            
            text = response.text
            if "```json" in text: 
                text = text.split("```json")[1].split("```")[0]
            topic_data = json.loads(text.strip())
            
            # 보안: 제목 검증
            topic_data['title'] = validator.validate_title(topic_data.get('title', 'Untitled'))
            
            print(f"📝 주제: {topic_data['title']}")
            
        except Exception as e:
            print(f"❌ 1단계(주제생성) 실패: {str(e)}")
            return

        # 2. 본문 생성
        try:
            # 도메인 결정
            # 핵심 인사이트 정의
            key_insights = """
- 60% of enterprise AI tool licenses remain unused after the first quarter
- The 5+ hour rule: Only adopt AI for tasks consuming 5+ hours per week per person
- Implementation cost: 2-3 hours per workflow for initial setup
- ROI breakeven point: 3 months for teams with 50+ monthly instances
- Below 50 instances/month: Setup overhead typically exceeds time savings
- Success pattern: Task identification first, then tool selection (not reversed)
"""
            
            post_prompt = f"""You are a top-tier industry strategist and pragmatic operator writing in 2026.

Your task is to write a high-impact, "Definitive Guide" style article.

**Target Context:**
- **Title:** {topic_data['title']}
- **Domain:** {domain}
- **Length:** Minimum 1200 words. Achieve this by deep-diving into the *implications* and *mechanisms* of the problem, not by fluff.
- **Current Era:** It is 2026. The initial AI hype cycle has crashed. We are in the "Era of Disillusionment & Real Utility." Write with this mature, skeptical perspective.

**The "Proprietary Insights" (Your Anchor Data):**
Integrate the following specific data points. Treat these as "observed patterns from high-performing teams," not necessarily universal laws.

{key_insights}

**Safety & Verification Protocol:**
1. **Frame the Data:** Present numbers as "In our analysis of enterprise deployments..." or "We typically see that..." This ensures accuracy even if exact global stats vary.
2. **2026 Context Injection:** Use your knowledge of the 2026 business landscape to explain *why* these patterns make sense (e.g., tightening budgets, mature market).
3. **No Fabricated Facts:** Do not invent company names, fake studies, or specific dates not provided. Stick to the logic and scenarios.

**Structure for Depth (The 1200+ Word Strategy):**

1. **The Cold Hard Truth (The Hook):**
   - Start immediately with the problem: Companies are buying AI backwards
   - Use the "60% unused" metric as shocking evidence
   - Set the 2026 context: Post-hype reality

2. **The Root Cause Analysis (Why We Fail):**
   - Analyze the psychology of "Tool-First" adoption
   - Why do smart leaders make this mistake? (FOMO, board pressure, vendor hype)
   - Explain the consequence: The "Trough of Disillusionment" when tools sit idle

3. **The Protocol: The 5+ Hour Rule (The Solution):**
   - Deeply unpack the methodology: "Identify repetitive cognitive tasks consuming 5+ hours/week"
   - **Crucial:** Create a detailed *Hypothetical Audit Scenario*
   - Example: Marketing Manager named 'Alex' audits her team's time to find these 5 hours
   - This narrative adds realistic length and value

4. **The Litmus Test: Classification vs. Context:**
   - Expand with concrete examples
   - **Case Study A (Pass):** Simple inquiry categorization - explain why LLMs excel here
   - **Case Study B (Fail):** Nuanced customer complaints - explain why LLMs hallucinate
   - Recommend the "Knowledge Base" approach as the correct alternative

5. **The ROI Blueprint (The Math):**
   - Detail the "2-3 hours implementation" vs "3-month break-even"
   - Walk through the math: Show that for low-volume teams (<50/month), setup time isn't worth it
   - Be the honest accountant - include the numbers that don't work

**Tone & Style:**
- Professional, critical, empathetic
- Use **bolding** for emphasis
- Use bullet points for steps
- **Strictly No Clichés:** Ban "game-changer", "unprecedented", "landscape", "unlock", "supercharge", "delve"
- Mix short punchy sentences with longer analytical ones
- It's acceptable to use strong opinions: "Most teams get this backwards"

**HTML Format:**
- Use <h1> for title
- Use <h2> for main sections (aim for 5-6 distinct sections)
- Use <h3> for subsections where appropriate
- Use <p> for paragraphs
- Use <strong> for emphasis within text
- Use <ul>/<ol> and <li> for lists
- Include 2-3 [IMAGE: specific, detailed description] markers where visuals would clarify concepts

**SEO:**
- Primary keyword: "{keyword}"
- Use naturally 4-6 times throughout the article
- Variations are acceptable (e.g., "AI tools" → "AI solutions", "automation tools")
- Include keyword in introduction
- If natural, include in 1-2 section headings

**Final Output Requirement:**
Produce a polished, ready-to-publish HTML article that feels like it was written by a human expert with 10+ years of experience, updated for the 2026 reality. Every paragraph should provide genuine value.

Current year: 2026. Write in present tense.

Begin with <h1> and write the complete article:"""

            # 강화된 프롬프트 + 안정적인 Flash 모델
            post_response = self.client.models.generate_content(
                model='gemini-2.5-flash',  # 안정적, 할당량 충분
                contents=post_prompt
            )
            
            # 보안: 응답 크기 검증
            if not validator.validate_json_size(post_response.text):
                print("❌ 2단계(본문생성) 실패: 응답이 너무 큼")
                return
            
            content = post_response.text
            
            if "```html" in content: 
                content = content.split("```html")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            # 보안: HTML 콘텐츠 정제
            content = validator.sanitize_html(content)
            
            print(f"✅ 본문 생성 완료 ({len(content)} 문자)")
            
            # 이미지 교체 (각기 다른 사진)
            image_markers = re.findall(r'\[IMAGE:.*?\]', content)
            image_count = 0
            
            # 기본 검색어 리스트 (마커가 부족할 경우 대비)
            base_queries = [
                topic_data.get('keyword', 'business'),
                f"{topic_data.get('keyword', 'business')} technology",
                "modern workspace",
                "business productivity",
                "professional office",
                "team collaboration",
                "digital transformation"
            ]
            
            for i, marker in enumerate(image_markers):
                # 마커에서 설명 추출 또는 기본 검색어 사용
                marker_text = marker.replace('[IMAGE:', '').replace(']', '').strip()
                query = marker_text if len(marker_text) > 3 else base_queries[i % len(base_queries)]
                
                print(f"🖼️  이미지 {i+1} 검색: {query}")
                
                try:
                    # Unsplash API 호출
                    img_res = requests.get(
                        "https://api.unsplash.com/photos/random",
                        params={
                            'query': query,
                            'client_id': self.unsplash_api_key,
                            'orientation': 'landscape'
                        },
                        timeout=10
                    )
                    
                    if img_res.status_code == 200:
                        data = img_res.json()
                        # 배열로 반환될 수도 있음
                        if isinstance(data, list):
                            data = data[0]
                        
                        img_url = data['urls']['regular']
                        
                        # 보안: 이미지 URL 검증
                        if not validator.validate_image_url(img_url):
                            print(f"   ⚠️  이미지 {i+1} URL 검증 실패")
                            content = content.replace(marker, '', 1)
                            continue
                        
                        photographer = data['user']['name']
                        
                        img_html = f"""
                        <div style="text-align:center; margin:50px 0;">
                            <img src="{img_url}" 
                                 alt="{query}" 
                                 style="width:100%; max-width:800px; height:auto; border-radius:8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);">
                            <p style="font-size:0.85em; color:#666; margin-top:8px;">
                                Photo by {photographer} on Unsplash
                            </p>
                        </div>
                        """
                        content = content.replace(marker, img_html, 1)
                        image_count += 1
                        print(f"   ✓ 이미지 {i+1} 추가 성공")
                    else:
                        print(f"   ⚠️  이미지 {i+1} 실패 (상태: {img_res.status_code})")
                        content = content.replace(marker, '', 1)
                    
                    # API 제한 방지
                    time.sleep(1)
                    
                except Exception as img_err:
                    print(f"   ⚠️  이미지 {i+1} 에러: {img_err}")
                    content = content.replace(marker, '', 1)
            
            print(f"✅ 이미지 {image_count}개 매핑 완료")
            
        except Exception as e:
            print(f"❌ 2단계(본문생성) 실패: {str(e)}")
            import traceback
            traceback.print_exc()
            return

        # 3. 발행 (데스크탑 최적화 레이아웃)
        try:
            # 전문적인 블로그 스타일
            final_html = f"""
            <style>
                .blog-post {{
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 60px 30px;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                    line-height: 1.8;
                    color: #2c3e50;
                    background: #fff;
                }}
                .blog-post h1 {{
                    font-size: 2.8em;
                    font-weight: 700;
                    margin-bottom: 30px;
                    color: #1a1a1a;
                    line-height: 1.2;
                }}
                .blog-post h2 {{
                    font-size: 2em;
                    font-weight: 600;
                    margin-top: 50px;
                    margin-bottom: 20px;
                    color: #34495e;
                    border-bottom: 2px solid #3498db;
                    padding-bottom: 10px;
                }}
                .blog-post h3 {{
                    font-size: 1.5em;
                    font-weight: 600;
                    margin-top: 35px;
                    margin-bottom: 15px;
                    color: #34495e;
                }}
                .blog-post p {{
                    font-size: 1.1em;
                    margin-bottom: 25px;
                    line-height: 1.9;
                }}
                .blog-post ul, .blog-post ol {{
                    font-size: 1.1em;
                    margin-bottom: 25px;
                    padding-left: 30px;
                }}
                .blog-post li {{
                    margin-bottom: 12px;
                }}
                .blog-post strong {{
                    color: #2c3e50;
                    font-weight: 600;
                }}
                .blog-post a {{
                    color: #3498db;
                    text-decoration: none;
                }}
                .blog-post a:hover {{
                    text-decoration: underline;
                }}
                @media (max-width: 768px) {{
                    .blog-post {{
                        padding: 30px 20px;
                    }}
                    .blog-post h1 {{
                        font-size: 2em;
                    }}
                    .blog-post h2 {{
                        font-size: 1.6em;
                    }}
                    .blog-post h3 {{
                        font-size: 1.3em;
                    }}
                    .blog-post p, .blog-post ul, .blog-post ol {{
                        font-size: 1em;
                    }}
                }}
            </style>
            <div class="blog-post">
                {content}
                
                <div style="margin-top:60px; padding-top:30px; border-top:1px solid #ddd;">
                    <p style="font-size:0.95em; color:#7f8c8d;">
                        <strong>💡 What do you think?</strong> Share your thoughts in the comments below!
                    </p>
                </div>
            </div>
            """
            
            service = self.get_blogger_service()
            result = service.posts().insert(
                blogId=self.blog_id,
                body={
                    'title': topic_data['title'], 
                    'content': final_html,
                    'labels': keywords[:5] if 'keywords' in locals() else []
                },
                isDraft=True  # DRAFT 모드
            ).execute()
            
            print(f"\n{'='*60}")
            print(f"🎉 모든 프로세스 완료!")
            print(f"{'='*60}")
            print(f"📝 제목: {topic_data['title']}")
            print(f"🆔 드래프트 ID: {result.get('id')}")
            print(f"🔗 URL: {result.get('url', 'N/A')}")
            print(f"📅 작성 시간: {datetime.now()}")
            print(f"{'='*60}\n")
            
        except Exception as e:
            print(f"❌ 3단계(발행) 실패: {str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    blog_system = ProfitOptimizedBlogSystem()
    blog_system.run_daily_automation()
