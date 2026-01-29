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
from anthropic import Anthropic

class SecurityValidator:
    """보안 검증 클래스"""
    
    @staticmethod
    def sanitize_html(content):
        """위험한 HTML 태그 제거"""
        if not content:
            return content
        
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
            
            if parsed.scheme != 'https':
                print(f"⚠️  보안: HTTP URL 차단됨")
                return False
            
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
        
        if len(title) > 200:
            title = title[:200]
        
        title = re.sub(r'<[^>]+>', '', title)
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
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        self.anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
        self.unsplash_api_key = os.getenv('UNSPLASH_API_KEY')
        self.blog_id = os.getenv('BLOGGER_BLOG_ID')
        
        if not self.anthropic_api_key:
            print("❌ 오류: ANTHROPIC_API_KEY가 설정되지 않았습니다.")
            sys.exit(1)

        # Claude: 주제 + 본문 생성 (품질 최고)
        self.claude_client = Anthropic(api_key=self.anthropic_api_key)
        
        self.profitable_niches = {
            'technology': ['AI', 'SaaS', 'Gadgets', 'Software', 'Cloud Computing'],
            'finance': ['Stocks', 'Crypto', 'Passive Income', 'Investing', 'Personal Finance'],
            'business': ['Productivity', 'Marketing', 'Entrepreneurship', 'Remote Work'],
            'health': ['Fitness', 'Nutrition', 'Mental Health', 'Wellness'],
            'education': ['Online Courses', 'Learning Platforms', 'Certifications', 'Study Tools', 'E-learning']
        }

    def get_blogger_service(self):
        """OAuth로 Blogger API 서비스 생성"""
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

    def generate_single_post(self, validator):
        """단일 글 생성 (주제 + 본문 + 이미지 + 발행)"""
        print(f"\n{'='*60}")
        print(f"📝 글 생성 시작...")
        print(f"{'='*60}\n")
        
        # 1. 주제 생성 (Claude)
        try:
            niche = random.choice(list(self.profitable_niches.keys()))
            keywords = self.profitable_niches[niche]
            
            domain_map = {
                'technology': 'enterprise SaaS and technology',
                'finance': 'financial services and investment',
                'business': 'business operations and strategy',
                'health': 'health and wellness',
                'education': 'online learning and education technology'
            }
            domain = domain_map.get(niche, 'business')
            
            topic_prompt = f"""You are a critical content strategist for {domain} writing in 2026.

Generate ONE contrarian, data-driven blog topic that challenges conventional wisdom.

Context:
- Domain: {domain}
- Keywords: {', '.join(keywords)}
- Year: 2026 (post-hype era, focus on what actually works)

Requirements:
1. Title must start with a number, question, or "Why/How"
2. Include a specific problem or surprising data point
3. Avoid hype words: "revolutionary", "game-changing", "unlock"
4. Make it sound critical and practical, not promotional

Examples of GOOD titles:
- "Why 70% of Online Courses Fail: The 5-Hour Reality Check"
- "The $200/Month SaaS Trap: When Free Tools Outperform"
- "How Top Investors Lost 40% in 2025: Three Mistakes to Avoid"

Examples of BAD titles:
- "The Future of AI in Education"
- "Revolutionizing Your Investment Strategy"
- "10 Amazing Tools You Must Try"

Return ONLY valid JSON (no markdown, no explanation):
{{"title": "specific contrarian title", "keyword": "main keyword from list", "description": "one sentence hook"}}"""
            
            print("📝 Claude로 주제 생성 중...")
            topic_response = self.claude_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                messages=[{"role": "user", "content": topic_prompt}]
            )
            
            topic_text = topic_response.content[0].text.strip()
            print(f"✅ Claude 주제 생성 완료")
            
            # JSON 파싱
            if "```json" in topic_text:
                topic_text = topic_text.split("```json")[1].split("```")[0]
            elif "```" in topic_text:
                topic_text = topic_text.split("```")[1].split("```")[0]
            
            topic_data = json.loads(topic_text.strip())
            
            # 보안: 제목 검증
            topic_data['title'] = validator.validate_title(topic_data.get('title', 'Untitled'))
            
            print(f"📝 주제: {topic_data['title']}")
            
        except Exception as e:
            print(f"❌ 1단계(주제생성) 실패: {str(e)}")
            import traceback
            traceback.print_exc()
            return

        # 2. 본문 생성 (Claude)
        try:
            keyword = topic_data.get('keyword', '')
            
            # 카테고리별 핵심 인사이트
            insights_map = {
                'technology': """
- 30-50% of enterprise tool licenses remain unused (up to 70% in some audits)
- Only adopt tools for tasks consuming 5+ hours per week per person (rule of thumb)
- Implementation: typically 10-18 hours per workflow setup (varies by complexity)
- ROI breakeven: generally 3 months for teams with 50+ monthly instances
- Below 50 instances/month: Setup overhead often exceeds time savings
- Context switching cost: studies suggest up to 20-23 minutes to regain focus
""",
                'education': """
- 60-70% of online course enrollments go uncompleted (industry average)
- Effective learning requires consistent 5+ hours per week commitment (minimum threshold)
- Completion rates vary: Self-paced 10-20%, cohort-based 60-70%, mentored 75-85%
- ROI typically appears after 3-6 months of consistent practice
- Stackable credentials work best for career transitions (6-12 month timeline)
""",
                'finance': """
- 70-90% of retail investors underperform index funds over 10+ years (historical data)
- Successful active investing requires 5-10+ hours per week of research
- Diversification beats individual stock picking for most investors (studies show)
- Common mistake: Reacting emotionally to short-term moves (behavioral finance research)
- Cost of frequent trading: typically 1-2% annual returns lost to fees and timing
""",
                'business': """
- 50-60% of productivity tools see declining usage after 3 months (common pattern)
- Effective adoption requires 5+ hours per week of team engagement (minimum)
- ROI threshold: Tool must save more time than it takes to learn and maintain
- Implementation cost: typically 2-4 hours per person for training
- Success factor: Management buy-in and consistent usage patterns (organizational behavior)
""",
                'health': """
- 70-80% of fitness programs are abandoned within 3 months (industry data)
- Sustainable results require 3-5+ hours per week commitment (evidence-based)
- Quick fixes rarely work: studies show 80-95% regain weight within 2 years
- Effective approach: Small, consistent changes over 6+ months (research-backed)
- Key factor: Lifestyle integration, not temporary diets (behavior change science)
"""
            }
            
            key_insights = insights_map.get(niche, insights_map['business'])
            
            post_prompt = f"""You are a senior expert in {domain} writing a critical, practical article in 2026.

Title: {topic_data['title']}

**Critical Data Points to Integrate:**
{key_insights}

**Strict Rules:**
1. BANNED WORDS: "landscape", "revolutionize", "unlock", "game-changing", "unprecedented", "delve", "robust", "leverage"
2. NO generic openings like "In today's world..." or "The rise of..."
3. START with a specific problem, surprising stat, or contrarian opinion
4. Include 2-3 realistic scenarios or case examples (hypothetical is fine, but mark as "example" or "typical scenario")
5. Discuss what DOESN'T work, not just what works
6. Admit limitations and trade-offs

**Data Accuracy Rules (CRITICAL):**
- When citing statistics, use ranges: "30-50% (up to 70% in some cases)"
- Add qualifiers: "studies suggest", "research shows", "industry data indicates", "typically", "often"
- For hypothetical examples, say: "realistic example", "typical scenario", "common pattern I see"
- Never claim "I consulted with" or "in my experience with specific company X" unless marking as hypothetical
- When uncertain, use hedging: "can take", "often requires", "generally"

**Structure:**
- <h1> for title
- 4-6 <h2> sections with specific, opinionated headings
- Use <h3> for subsections
- Include 2-3 [IMAGE: specific visual description] markers
- 1200-1800 words

**Style:**
- Write for skeptical professionals who hate BS
- Mix short punchy sentences with longer analytical ones
- Use "you" to speak directly to reader
- Strong opinions are good: "Most people get this wrong"
- Use keyword "{keyword}" naturally 3-5 times

**End with a brief caveat paragraph:**
"What this doesn't cover: [mention 1-2 exceptions or edge cases, e.g., security/compliance tools may have different ROI calculus]"

**Context:**
Current year: 2026. The hype cycle is over. Focus on what actually works based on real-world data.

Write the complete article starting with <h1>:"""

            print("📝 Claude Sonnet 4로 본문 생성 중...")
            
            claude_response = self.claude_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                messages=[
                    {"role": "user", "content": post_prompt}
                ]
            )
            
            content = claude_response.content[0].text
            print(f"✅ Claude 본문 생성 완료 ({len(content)} 문자)")
            
            # 보안: 응답 크기 검증
            if not validator.validate_json_size(content):
                print("❌ 2단계(본문생성) 실패: 응답이 너무 큼")
                return
            
            if "```html" in content: 
                content = content.split("```html")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            content = validator.sanitize_html(content)
            
            # 이미지 교체
            image_markers = re.findall(r'\[IMAGE:.*?\]', content)
            image_count = 0
            
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
                marker_text = marker.replace('[IMAGE:', '').replace(']', '').strip()
                query = marker_text if len(marker_text) > 3 else base_queries[i % len(base_queries)]
                
                print(f"🖼️  이미지 {i+1} 검색: {query}")
                
                try:
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
                        if isinstance(data, list):
                            data = data[0]
                        
                        img_url = data['urls']['regular']
                        
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

        # 3. 발행
        try:
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
                    'labels': keywords[:5]
                },
                isDraft=True
            ).execute()
            
            print(f"\n{'='*60}")
            print(f"🎉 글 발행 완료!")
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

    def run_manual_post(self):
        """수동 실행 시 글 1개 생성"""
        print(f"🚀 글 생성 시작: {datetime.now()}")
        print("=" * 60)
        
        validator = SecurityValidator()
        
        # 글 1개 생성
        try:
            self.generate_single_post(validator)
        except Exception as e:
            print(f"❌글 생성 실패: {e}")
            import traceback
            traceback.print_exc()
        
        print(f"\n{'='*60}")
        print(f"🎉 작업 완료!")
        print(f"📅 완료 시간: {datetime.now()}")
        print(f"{'='*60}\n")

if __name__ == "__main__":
    blog_system = ProfitOptimizedBlogSystem()
    blog_system.run_manual_post()
