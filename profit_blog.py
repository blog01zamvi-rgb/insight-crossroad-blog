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
            domain_map = {
                'technology': 'enterprise SaaS and technology',
                'finance': 'financial services and investment',
                'business': 'business operations and strategy',
                'health': 'health and wellness',
                'education': 'online learning and education technology'
            }
            domain = domain_map.get(niche, 'business')
            keyword = topic_data.get('keyword', '')
            
            post_prompt = f"""You are a senior industry practitioner writing for a professional audience in {domain}.

Task: Write an in-depth, publication-quality article on:
{topic_data['title']}

Readers:
- Experienced professionals in {domain}
- They understand basic concepts; they want nuanced, practical insight.

Hard constraints:
1. Do NOT invent specific statistics, prices, product features, or company claims.
2. If exact data is unknown, say so explicitly and describe typical ranges or scenarios instead.
3. Prioritize accuracy, clarity, and usefulness over word count. It's fine to be shorter than requested if needed.

Content rules:
1. Open with a concrete problem, decision, or scenario – no generic "In today's world…" intros.
2. For every important claim, explain:
   - WHY it matters
   - WHEN it applies (and when it doesn't)
   - WHAT the trade-offs or risks are
3. Include at least 2–3 realistic examples or mini-case studies.
   - Hypothetical is fine, but mark them clearly as examples.
4. Always cover:
   - Implementation challenges
   - Organisational/process impact
   - Cost/benefit or effort/impact considerations
5. When giving advice, use simple decision rules:
   - "Choose A if X and Y"
   - "Choose B if Z, or if you have constraint C"

Style:
1. Write like a human expert talking to peers, not marketing copy.
2. Avoid AI/consulting clichés: "delve into", "landscape", "game-changing", "revolutionize", "unlock", "supercharge".
3. Mix short, direct sentences with longer analytical ones.
4. Use hedging correctly for uncertain topics: "generally", "often", "in most cases", "as of 2026 data is limited".
5. It's acceptable to say "we don't know yet" and explain why.

Structure:
- Use <h1> for the title.
- Use 4–6 <h2> sections with specific, descriptive headings (not "Introduction", "Conclusion").
- Use <h3> only when it really helps structure a complex section.
- Use proper HTML: <p> for paragraphs, <ul>/<ol> for lists, <li> for items, <strong> for emphasis.
- Include 3–5 [IMAGE: very specific description] markers where a diagram/visual would help understanding.
- Lists are allowed, but each list must be introduced and followed by explanatory prose.

SEO:
- Naturally incorporate the keyword "{keyword}" 3-5 times throughout the article.
- Use variations and related terms as well.

Length:
- Aim for 1800–2300 words.
- If there isn't enough solid content to reach that length without speculation, stop earlier.

Current year: 2026. Write in present tense about the current state unless you're explicitly describing future scenarios.

Begin with the <h1> title and write the complete article:"""

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
