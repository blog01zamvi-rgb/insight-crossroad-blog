import os
import json
import random
import re
import time
import requests
from urllib.parse import urlparse
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from anthropic import Anthropic

# ==========================================
# ⚙️ SYSTEM CONFIGURATION
# ==========================================
# MODE: 'APPROVAL' (승인용: 일상/정보) vs 'MONEY' (수익용: 고단가/리뷰)
CURRENT_MODE = 'APPROVAL' 

# MODEL: 최신 Claude 모델 (비용 대비 성능 최적)
CLAUDE_MODEL_NAME = "claude-3-5-sonnet-20240620"

class SecurityValidator:
    """보안 및 데이터 검증 클래스"""
    @staticmethod
    def sanitize_html(content):
        """악성 스크립트 제거"""
        if not content: return ""
        dangerous = [
            r'<script[^>]*>.*?</script>', r'<iframe[^>]*>.*?</iframe>',
            r'javascript:', r'onclick=', r'onload=', r'<object', r'<embed'
        ]
        cleaned = content
        for pattern in dangerous:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE | re.DOTALL)
        return cleaned

    @staticmethod
    def validate_image_url(url):
        """이미지 URL 유효성 검사"""
        if not url: return False
        try:
            parsed = urlparse(url)
            return parsed.scheme == 'https' and ('unsplash.com' in parsed.netloc)
        except: return False

class ProBlogBot:
    def __init__(self):
        # API 키 로드
        self.anthropic_key = os.getenv('ANTHROPIC_API_KEY')
        self.unsplash_key = os.getenv('UNSPLASH_API_KEY')
        self.blog_id = os.getenv('BLOGGER_BLOG_ID')
        
        if not self.anthropic_key:
            raise ValueError("❌ ANTHROPIC_API_KEY Missing")

        self.claude = Anthropic(api_key=self.anthropic_key)
        self.validator = SecurityValidator()

        # 🟢 승인 모드 데이터 (안전, 에세이, 정보성)
        self.niche_approval = {
            'Productivity': ['Deep Work Strategies', 'Digital Minimalism Guide', 'Morning Routine for Success'],
            'Wellness': ['Mindfulness at Work', 'Ergonomic Home Office Setup', 'Avoiding Burnout'],
            'Tech_Tips': ['Cybersecurity Basics', 'Data Backup Best Practices', 'Keyboard Shortcuts Guide']
        }

        # 💰 수익 모드 데이터 (고단가, 리뷰, 비교)
        self.niche_money = {
            'SaaS_Review': ['Best CRM Software 2026', 'Project Management Tools Comparison', 'Email Marketing Platforms'],
            'Hosting': ['Best Web Hosting for Startups', 'Cloud Storage Pricing', 'WordPress Hosting Review'],
            'Finance': ['Personal Finance Apps', 'Investment Platforms for Beginners', 'Crypto Exchange Comparison']
        }

    def get_blogger_service(self):
        """구글 블로거 API 인증"""
        from google.auth.transport.requests import Request
        user_info = {
            'client_id': os.getenv('OAUTH_CLIENT_ID'),
            'client_secret': os.getenv('OAUTH_CLIENT_SECRET'),
            'refresh_token': os.getenv('OAUTH_REFRESH_TOKEN'),
            'token_uri': 'https://oauth2.googleapis.com/token'
        }
        creds = Credentials.from_authorized_user_info(
            user_info, scopes=['https://www.googleapis.com/auth/blogger']
        )
        creds.refresh(Request())
        return build('blogger', 'v3', credentials=creds)

    def step_1_planner(self, category, keyword):
        """1단계: 글 기획 (뼈대 만들기)"""
        print(f"🧠 [1/4] Planning content for '{keyword}' ({CURRENT_MODE} Mode)...")
        
        if CURRENT_MODE == 'APPROVAL':
            role = "You are a helpful, empathetic life coach and tech enthusiast."
            goal = "Focus on personal experience (E-E-A-T), helpfulness, and engagement."
        else:
            role = "You are a sharp, analytical business consultant."
            goal = "Focus on feature comparison, pros/cons, and persuasive recommendations."

        prompt = f"""
        {role}
        Task: Create a detailed outline for a blog post about "{keyword}".
        Target Audience: US-based English speakers.
        Goal: {goal}
        
        Return JSON format:
        {{
            "title": "Catchy Title Here",
            "hook": "Opening sentence concept",
            "sections": ["Section 1 Header", "Section 2 Header", "Section 3 Header"],
            "image_keywords": ["keyword1", "keyword2"]
        }}
        """
        
        try:
            msg = self.claude.messages.create(
                model=CLAUDE_MODEL_NAME, max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
            text = msg.content[0].text
            # JSON 파싱
            if "```json" in text: text = text.split("```json")[1].split("```")[0]
            elif "```" in text: text = text.split("```")[1].split("```")[0]
            return json.loads(text.strip())
        except Exception as e:
            print(f"⚠️ Planning Failed: {e}")
            return None

    def step_2_writer(self, plan, keyword):
        """2단계: 본문 작성 (HTML 포맷)"""
        print(f"✍️ [2/4] Writing content...")
        
        system = "You are a professional native English blogger. You write in valid HTML format."
        
        prompt = f"""
        Write a full blog post based on this plan:
        Title: {plan['title']}
        Sections: {', '.join(plan['sections'])}
        
        **CRITICAL INSTRUCTIONS:**
        1. **Language:** Native American English.
        2. **Format:** Use HTML tags (<h2>, <h3>, <p>, <ul>, <li>, <table>).
        3. **Images:** Insert exactly 2 markers: [IMAGE: {plan['image_keywords'][0]}] and [IMAGE: {plan['image_keywords'][1]}] at appropriate places.
        4. **Length:** 1500+ words.
        5. **No Fluff:** Do not use "In conclusion", "Delve", "Landscape".
        
        **Mode Specifics:**
        - If making a claim, say "Research suggests" or "In my experience".
        - If comparing tools, use a <table>.
        
        Output ONLY the HTML <body> content.
        """
        
        msg = self.claude.messages.create(
            model=CLAUDE_MODEL_NAME, max_tokens=4000, system=system,
            messages=[{"role": "user", "content": prompt}]
        )
        return self.validator.sanitize_html(msg.content[0].text)

    def step_3_designer(self, content):
        """3단계: 이미지 검색 및 삽입 (Unsplash)"""
        print(f"🎨 [3/4] Designing visuals...")
        
        markers = re.findall(r'\[IMAGE:.*?\]', content)
        
        for marker in markers:
            query = marker.replace('[IMAGE:', '').replace(']', '').strip()
            print(f"   🔍 Searching image for: {query}")
            
            try:
                res = requests.get(
                    "https://api.unsplash.com/photos/random",
                    params={'query': query, 'client_id': self.unsplash_key, 'orientation': 'landscape'},
                    timeout=5
                )
                if res.status_code == 200:
                    data = res.json()
                    if isinstance(data, list): data = data[0]
                    
                    img_html = f"""
                    <div class="blog-image-wrapper" style="margin: 30px 0; text-align: center;">
                        <img src="{data['urls']['regular']}" alt="{query}" 
                             style="width: 100%; max-width: 800px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
                        <p style="font-size: 0.8em; color: #666; margin-top: 8px;">Photo by {data['user']['name']} on Unsplash</p>
                    </div>
                    """
                    content = content.replace(marker, img_html, 1)
                else:
                    content = content.replace(marker, "", 1)
            except:
                content = content.replace(marker, "", 1)
                
        return content

    def step_4_publisher(self, title, content, category):
        """4단계: 최종 스타일링 및 발행"""
        print(f"🚀 [4/4] Publishing to Blogger...")
        
        # 전문적인 잡지 스타일 CSS
        css = """
        <style>
            .post-body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif; line-height: 1.8; color: #333; font-size: 18px; }
            h2 { font-size: 28px; font-weight: 700; color: #1a1a1a; margin-top: 50px; margin-bottom: 20px; letter-spacing: -0.5px; }
            h3 { font-size: 22px; font-weight: 600; color: #2d3436; margin-top: 30px; }
            p { margin-bottom: 24px; }
            ul, ol { margin-bottom: 24px; padding-left: 20px; }
            li { margin-bottom: 10px; }
            table { width: 100%; border-collapse: collapse; margin: 30px 0; font-size: 16px; }
            th { background: #f1f3f5; font-weight: 600; text-align: left; padding: 12px; border-bottom: 2px solid #dee2e6; }
            td { padding: 12px; border-bottom: 1px solid #eee; }
            blockquote { border-left: 4px solid #339af0; padding-left: 20px; color: #495057; font-style: italic; margin: 30px 0; }
            .disclaimer { background: #fff5f5; padding: 15px; border-radius: 6px; font-size: 14px; color: #c92a2a; margin-top: 50px; }
        </style>
        """
        
        disclaimer = ""
        if CURRENT_MODE == 'MONEY':
            disclaimer = """
            <div class="disclaimer">
                <strong>Disclaimer:</strong> This article contains information for educational purposes. 
                Financial decisions should be made with professional advice. 
                Some links may be affiliate links.
            </div>
            """

        final_html = f"{css}<div class='post-body'>{content}{disclaimer}</div>"
        
        body = {
            'title': title,
            'content': final_html,
            'labels': [CURRENT_MODE, category, '2026 Guide']
        }
        
        try:
            service = self.get_blogger_service()
            # 안전하게 Draft(초안) 상태로 업로드
            res = service.posts().insert(blogId=self.blog_id, body=body, isDraft=True).execute()
            print(f"✅ Success! Draft URL: {res.get('url')}")
            return True
        except Exception as e:
            print(f"❌ Publish Error: {e}")
            return False

    def run(self):
        """메인 실행 함수"""
        print(f"🔥 Starting ProBlogBot in [{CURRENT_MODE}] Mode")
        
        # 1. 주제 선정
        niche_dict = self.niche_approval if CURRENT_MODE == 'APPROVAL' else self.niche_money
        category = random.choice(list(niche_dict.keys()))
        keyword = random.choice(niche_dict[category])
        
        # 2. 파이프라인 실행
        plan = self.step_1_planner(category, keyword)
        if not plan: return
        
        content = self.step_2_writer(plan, keyword)
        if not content: return
        
        content = self.step_3_designer(content)
        
        self.step_4_publisher(plan['title'], content, category)

if __name__ == "__main__":
    bot = ProBlogBot()
    bot.run()
