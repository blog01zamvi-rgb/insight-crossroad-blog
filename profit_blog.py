import os
import json
import random
import re
import sys
import time
from datetime import datetime
import requests
from google import genai
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

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
            'health': ['Fitness', 'Nutrition', 'Mental Health', 'Wellness']
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
        print(f"🚀 자동화 시작 시간: {datetime.now()}")
        
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
            
            print(f"📝 주제: {topic_data['title']}")
            
        except Exception as e:
            print(f"❌ 1단계(주제생성) 실패: {str(e)}")
            return

        # 2. 본문 생성
        try:
            post_prompt = f"""Write a comprehensive, professional blog post about: {topic_data['title']}

Requirements:
- 2000+ words
- Use proper HTML tags: <h1>, <h2>, <p>, <ul>, <li>
- Include 3-5 [IMAGE: description] markers with DIFFERENT descriptions
- Write in engaging, natural style
- Current year is 2026
- Focus on factual, helpful information

Example image markers:
[IMAGE: modern workspace with laptop]
[IMAGE: business meeting discussion]
[IMAGE: analytics dashboard on screen]

Start with <h1> title, then write the full article."""

            post_response = self.client.models.generate_content(
                model='gemini-2.5-flash', 
                contents=post_prompt
            )
            content = post_response.text
            
            if "```html" in content: 
                content = content.split("```html")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
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
                body={{
                    'title': topic_data['title'], 
                    'content': final_html,
                    'labels': keywords[:5] if 'keywords' in locals() else []
                }},
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
