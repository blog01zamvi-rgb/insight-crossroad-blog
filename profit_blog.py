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

# MODEL: 사용자가 요청한 원본 모델명으로 복구
CLAUDE_MODEL_NAME = "claude-sonnet-4-20250514"

class SecurityValidator:
    """보안 및 데이터 검증 클래스"""
    @staticmethod
    def sanitize_html(content):
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
        if not url: return False
        try:
            parsed = urlparse(url)
            return parsed.scheme == 'https' and ('unsplash.com' in parsed.netloc)
        except: return False

class ProBlogBot:
    def __init__(self):
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
        print(f"🧠 [1/4] Planning content for '{keyword}'...")
        
        prompt = f"""
        You are a senior content strategist.
        Task: Create a blog outline for "{keyword}".
        Target: US-based audience.
        Mode: {'Helpful/Educational' if CURRENT_MODE == 'APPROVAL' else 'Commercial/Review'}.
        
        Return JSON format ONLY:
        {{
            "title": "Catchy Title",
            "sections": ["Header 1", "Header 2", "Header 3"],
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
        """2단계: 본문 작성 (HTML 포맷)"""
        print(f"✍️ [2/4] Writing content...")
        
        prompt = f"""
        Write a blog post based on:
        Title: {plan['title']}
        Sections: {', '.join(plan['sections'])}
        
        **Instructions:**
        1. Language: Native American English.
        2. Format: HTML <body> content only (use <h2>, <p>, <ul>, <table>).
        3. Insert Markers: Place [IMAGE: {plan['image_keywords'][0]}] and [IMAGE: {plan['image_keywords'][1]}] naturally.
        4. Style: {'Personal & Empathetic' if CURRENT_MODE == 'APPROVAL' else 'Professional & Analytical'}.
        5. Length: 1500+ words.
        """
        
        msg = self.claude.messages.create(
            model=CLAUDE_MODEL_NAME, max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )
        return self.validator.sanitize_html(msg.content[0].text)

    def step_3_designer(self, content):
        """3단계: 이미지 검색 및 삽입"""
        print(f"🎨 [3/4] Processing images...")
        markers = re.findall(r'\[IMAGE:.*?\]', content)
        
        for marker in markers:
            query = marker.replace('[IMAGE:', '').replace(']', '').strip()
            try:
                res = requests.get(
                    "https://api.unsplash.com/photos/random",
                    params={'query': query, 'client_id': self.unsplash_key, 'orientation': 'landscape'},
                    timeout=5
                )
                if res.status_code == 200:
                    data = res.json()
                    if isinstance(data, list): data = data[0]
                    img_html = f"""<div style="margin:30px 0;text-align:center;"><img src="{data['urls']['regular']}" style="width:100%;max-width:800px;border-radius:8px;"><p style="color:#666;font-size:12px">Photo by {data['user']['name']}</p></div>"""
                    content = content.replace(marker, img_html, 1)
                else:
                    content = content.replace(marker, "", 1)
            except:
                content = content.replace(marker, "", 1)
        return content

    def step_4_publisher(self, title, content, category):
        """4단계: 발행"""
        print(f"🚀 [4/4] Publishing...")
        
        css = """<style>body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;line-height:1.8;color:#333;font-size:18px}h2{margin-top:40px;color:#1a1a1a}table{width:100%;border-collapse:collapse;margin:30px 0}th,td{border:1px solid #ddd;padding:12px}th{background:#f8f9fa}</style>"""
        final_html = f"{css}<div>{content}</div>"
        
        body = {
            'title': title,
            'content': final_html,
            'labels': [CURRENT_MODE, category]
        }
        
        try:
            service = self.get_blogger_service()
            res = service.posts().insert(blogId=self.blog_id, body=body, isDraft=True).execute()
            print(f"✅ Published: {res.get('url')}")
        except Exception as e:
            print(f"❌ Error: {e}")

    def run(self):
        niche_dict = self.niche_approval if CURRENT_MODE == 'APPROVAL' else self.niche_money
        category = random.choice(list(niche_dict.keys()))
        keyword = random.choice(niche_dict[category])
        
        plan = self.step_1_planner(category, keyword)
        if plan:
            content = self.step_2_writer(plan, keyword)
            content = self.step_3_designer(content)
            self.step_4_publisher(plan['title'], content, category)

if __name__ == "__main__":
    bot = ProBlogBot()
    bot.run()
