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
# ⚙️ SYSTEM CONFIGURATION (설정)
# ==========================================

# 1. 모드 설정
# - 'APPROVAL': 승인 받기 전 (안전, 정보성, 에세이)
# - 'MONEY': 승인 받은 후 (수익형, 리뷰, 고단가 키워드)
CURRENT_MODE = 'APPROVAL' 

# 2. 모델 설정 (사용자 지정 모델명)
CLAUDE_MODEL_NAME = "claude-opus-4-5-20251101"

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
        """이미지 URL 안전성 검증"""
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
            raise ValueError("❌ 오류: ANTHROPIC_API_KEY가 없습니다.")
        if not self.unsplash_key:
            print("⚠️ 경고: UNSPLASH_API_KEY가 없어 이미지가 제외됩니다.")

        self.claude = Anthropic(api_key=self.anthropic_key)
        self.validator = SecurityValidator()

        # 🟢 승인 모드 주제 (안전함, 정보성)
        self.niche_approval = {
            'Productivity': ['Deep Work Strategies', 'Digital Minimalism Guide', 'Morning Routine for Success'],
            'Wellness': ['Mindfulness at Work', 'Ergonomic Home Office Setup', 'Avoiding Burnout'],
            'Tech_Tips': ['Cybersecurity Basics', 'Data Backup Best Practices', 'Keyboard Shortcuts Guide']
        }

        # 💰 수익 모드 주제 (고단가, 리뷰)
        self.niche_money = {
            'SaaS_Review': ['Best CRM Software 2026', 'Project Management Tools Comparison', 'Email Marketing Platforms'],
            'Hosting': ['Best Web Hosting for Startups', 'Cloud Storage Pricing', 'WordPress Hosting Review'],
            'Finance': ['Personal Finance Apps', 'Investment Platforms for Beginners', 'Crypto Exchange Comparison']
        }

    def get_blogger_service(self):
        """Blogger API 인증"""
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
        """1단계: 글 기획 (JSON)"""
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
        
        Return JSON format ONLY:
        {{
            "title": "Catchy Title Here (No Clickbait)",
            "hook": "Opening sentence concept",
            "sections": ["Section 1 Header", "Section 2 Header", "Section 3 Header"],
            "image_keywords": ["visual keyword 1", "visual keyword 2"]
        }}
        """
        
        try:
            msg = self.claude.messages.create(
                model=CLAUDE_MODEL_NAME, max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
            text = msg.content[0].text
            if "```json" in text: text = text.split("```json")[1].split("```")[0]
            elif "```" in text: text = text.split("```")[1].split("```")[0]
            return json.loads(text.strip())
        except Exception as e:
            print(f"⚠️ Planning Failed: {e}")
            return None

    def step_2_writer(self, plan, keyword):
        """2단계: 본문 작성 (HTML)"""
        print(f"✍️ [2/4] Writing content...")
        
        system = "You are a professional native English blogger. You write in valid HTML format."
        
        prompt = f"""
        Write a full blog post based on this plan:
        Title: {plan['title']}
        Sections: {', '.join(plan['sections'])}
        
        **CRITICAL WRITING RULES:**
        1. **Language:** Native American English (US).
        2. **Format:** Use HTML tags (<h2>, <h3>, <p>, <ul>, <li>, <table>).
        3. **Images:** Insert exactly 2 markers: [IMAGE: {plan['image_keywords'][0]}] and [IMAGE: {plan['image_keywords'][1]}].
        4. **Length:** 1500+ words.
        5. **No Citations:** DO NOT use citation numbers like [1], [2]. Incorporate facts naturally.
        6. **No Fluff:** Do not use "In conclusion", "Delve", "Landscape".
        
        Output ONLY the HTML <body> content.
        """
        
        try:
            msg = self.claude.messages.create(
                model=CLAUDE_MODEL_NAME, max_tokens=4000, system=system,
                messages=[{"role": "user", "content": prompt}]
            )
            return self.validator.sanitize_html(msg.content[0].text)
        except Exception as e:
            print(f"⚠️ Writing Failed: {e}")
            return None

    def step_3_designer(self, content):
        """3단계: 이미지 검색 및 삽입 (Unsplash 링크 포함)"""
        print(f"🎨 [3/4] Processing images...")
        
        if not self.unsplash_key: return content
        markers = re.findall(r'\[IMAGE:.*?\]', content)
        
        for marker in markers:
            query = marker.replace('[IMAGE:', '').replace(']', '').strip()
            print(f"   🔍 Searching: {query}")
            try:
                res = requests.get(
                    "https://api.unsplash.com/photos/random",
                    params={'query': query, 'client_id': self.unsplash_key, 'orientation': 'landscape'},
                    timeout=5
                )
                if res.status_code == 200:
                    data = res.json()
                    if isinstance(data, list): data = data[0]
                    
                    img_url = data['urls']['regular']
                    user_name = data['user']['name']
                    user_link = f"https://unsplash.com/@{data['user']['username']}?utm_source=BlogBot&utm_medium=referral"
                    unsplash_link = "https://unsplash.com/?utm_source=BlogBot&utm_medium=referral"
                    
                    img_html = f"""
                    <div style="margin:40px 0; text-align:center;">
                        <img src="{img_url}" alt="{query}" 
                             style="width:100%; max-width:800px; border-radius:8px; box-shadow:0 4px 15px rgba(0,0,0,0.1);">
                        <p style="color:#888; font-size:13px; margin-top:10px; font-style:italic;">
                            Photo by <a href="{user_link}" target="_blank" style="color:#888; text-decoration:none; border-bottom:1px dotted #888;">{user_name}</a> 
                            on <a href="{unsplash_link}" target="_blank" style="color:#888; text-decoration:none; border-bottom:1px dotted #888;">Unsplash</a>
                        </p>
                    </div>
                    """
                    content = content.replace(marker, img_html, 1)
                else:
                    content = content.replace(marker, "", 1)
            except:
                content = content.replace(marker, "", 1)
        return content

    def step_4_publisher(self, title, content, category):
        """4단계: 최종 발행 (태그 세탁 적용)"""
        print(f"🚀 [4/4] Publishing to Blogger...")
        
        css = """
        <style>
            .post-body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif; line-height: 1.8; color: #333; font-size: 18px; }
            h2 { font-size: 28px; font-weight: 700; color: #1a1a1a; margin-top: 50px; margin-bottom: 20px; letter-spacing: -0.5px; border-bottom: 2px solid #f1f3f5; padding-bottom: 10px; }
            h3 { font-size: 22px; font-weight: 600; color: #2d3436; margin-top: 35px; margin-bottom: 15px; }
            p { margin-bottom: 24px; }
            ul, ol { margin-bottom: 24px; padding-left: 20px; }
            li { margin-bottom: 12px; }
            table { width: 100%; border-collapse: collapse; margin: 35px 0; font-size: 16px; }
            th { background: #f8f9fa; font-weight: 600; text-align: left; padding: 15px; border-bottom: 2px solid #dee2e6; }
            td { padding: 15px; border-bottom: 1px solid #eee; }
            blockquote { border-left: 5px solid #339af0; padding: 15px 20px; background: #f8f9fa; color: #555; font-style: italic; margin: 35px 0; border-radius: 0 5px 5px 0; }
            .disclaimer { background: #fff5f5; padding: 20px; border-radius: 8px; font-size: 15px; color: #c92a2a; margin-top: 60px; border: 1px solid #ffa8a8; }
        </style>
        """
        
        disclaimer = ""
        if CURRENT_MODE == 'MONEY':
            disclaimer = """
            <div class="disclaimer">
                <strong>Disclaimer:</strong> This article is for informational purposes only. 
                Some links may be affiliate links. Always do your own research before making financial decisions.
            </div>
            """

        final_html = f"{css}<div class='post-body'>{content}{disclaimer}</div>"
        
        # 🏷️ 태그 세탁 로직 (APPROVAL/MONEY 숨기기)
        public_tags = [category]
        if CURRENT_MODE == 'APPROVAL':
            public_tags.extend(['Guide', 'Tips', 'Life Hacks'])
        else:
            public_tags.extend(['Review', 'Business', 'Software', 'Best of 2026'])
            
        public_tags = list(set(public_tags)) # 중복 제거

        body = {
            'title': title,
            'content': final_html,
            'labels': public_tags
        }
        
        try:
            service = self.get_blogger_service()
            res = service.posts().insert(blogId=self.blog_id, body=body, isDraft=True).execute()
            print(f"✅ SUCCESS! Draft created: {res.get('url')}")
            print(f"🏷️ Tags: {public_tags}")
        except Exception as e:
            print(f"❌ Publish Error: {e}")

    def run(self):
        print(f"🔥 Starting BlogBot in [{CURRENT_MODE}] Mode (Model: {CLAUDE_MODEL_NAME})")
        
        niche_dict = self.niche_approval if CURRENT_MODE == 'APPROVAL' else self.niche_money
        category = random.choice(list(niche_dict.keys()))
        keyword = random.choice(niche_dict[category])
        
        plan = self.step_1_planner(category, keyword)
        if plan:
            content = self.step_2_writer(plan, keyword)
            if content:
                content = self.step_3_designer(content)
                self.step_4_publisher(plan['title'], content, category)

if __name__ == "__main__":
    bot = ProBlogBot()
    bot.run()
