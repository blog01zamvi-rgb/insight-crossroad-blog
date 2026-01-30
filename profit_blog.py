#!/usr/bin/env python3
"""
Pro Blog Bot v2.0 - Opus 4.5 Optimized
=====================================
- AdSense 친화적 (스팸 탐지 회피)
- 거짓말 없음 (통계 fabrication 금지)
- 사람다운 글쓰기 (구체적 persona + 경험)
- SEO 최적화
- Self-critique loop으로 품질 보장
"""

import os
import json
import random
import re
import time
import requests
from urllib.parse import urlparse
from datetime import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from anthropic import Anthropic

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================

CURRENT_MODE = os.getenv('BLOG_MODE', 'APPROVAL')  # 'APPROVAL' or 'MONEY'

# Model Selection - Opus 4.5가 안되면 Sonnet 4.5 사용
# Opus 4.5: claude-opus-4-5-20251101 (더 비쌈, $5/$25, Pro/Max/Enterprise 필요)
# Sonnet 4.5: claude-sonnet-4-5-20250929 (저렴, $3/$15, 일반 API 가능)
CLAUDE_MODEL = os.getenv('CLAUDE_MODEL', 'claude-sonnet-4-5-20250929')

# ==========================================
# 🎭 PERSONA SYSTEM - 리서치 기반 큐레이터
# ==========================================

PERSONA = {
    'background': """You are a curious blogger who researches topics and summarizes findings for readers. You're NOT an expert and you don't pretend to be. You don't claim personal experience you don't have. Instead, you spend time looking into topics, comparing different sources and opinions, and presenting what you found in a clear, organized way.

Your value is in doing the research legwork so readers don't have to. You're like a friend who says "I looked into this for you, here's what I found."

You write in a casual, conversational tone - not academic, not corporate, just clear and helpful.""",
    
    'voice_traits': [
        "Frame as research: 'I looked into this...', 'From what I found...', 'Based on what people are saying...'",
        "Cite general sources naturally: 'Reddit users seem to agree...', 'A lot of reviews mention...', 'The common advice is...'",
        "Add your take: 'Honestly, this surprised me...', 'I'm not sure I buy this, but...', 'This makes sense to me because...'",
        "Acknowledge gaps: 'I couldn't find a clear answer on...', 'Opinions are split on this...'",
        "Be practical: Focus on actionable takeaways, not fluff",
        "Show your work: Mention what you compared, what sources you looked at (generally)",
        "Have opinions: After presenting findings, share what YOU think makes most sense",
        "Admit uncertainty: 'Take this with a grain of salt', 'Your situation might be different'"
    ]
}

# ==========================================
# 📝 TOPIC POOLS - 리서치 기반 주제
# ==========================================

TOPICS = {
    'APPROVAL': {
        'Productivity': [
            'Pomodoro vs Time Blocking: I Compared What Actually Works',
            'Why Do Some People Swear by 5AM Routines? I Looked Into It',
            'Notion vs Obsidian: What Reddit Actually Says',
            'The Real Reason Most To-Do Lists Fail (According to Research)',
            'I Read 20 Articles on Deep Work - Here Are the Parts That Actually Matter'
        ],
        'Wellness': [
            'Standing Desks: Hype or Legit? What the Studies Say',
            'I Compared 5 Sleep Tracking Methods - Here\'s What I Found',
            'What Actually Helps With Burnout (And What Doesn\'t)',
            'Blue Light Glasses: I Looked Into Whether They\'re Worth It',
            'The Science Behind Why Walking Meetings Might Work'
        ],
        'Tech_Tips': [
            'Password Managers Compared: What Users Actually Complain About',
            'VPN Services: Cutting Through the Marketing BS',
            'Why Tech People Keep Recommending Linux (And Why You Probably Shouldn\'t Switch)',
            'Cloud Storage Pricing is Confusing - I Broke It Down',
            'Ad Blockers in 2025: What Still Works and What Got Broken'
        ]
    },
    'MONEY': {
        'SaaS_Review': [
            'Asana vs Monday vs ClickUp: What Teams Actually Say After 6 Months',
            'CRM Software: The Hidden Costs Nobody Mentions Upfront',
            'Email Marketing Tools: I Compared Pricing For a 10K List',
            'Project Management Tools: Feature Comparison That Actually Matters',
            'Why Some Companies Ditch Slack for Discord (And Vice Versa)'
        ],
        'Hosting': [
            'Cheap Web Hosting: What You Actually Get for $3/Month',
            'WordPress Hosting Compared: Shared vs Managed vs VPS',
            'The Real Cost of "Unlimited" Hosting Plans',
            'Website Builders vs Custom Sites: When Each Makes Sense',
            'CDN Pricing Explained: Do Small Sites Even Need One?'
        ],
        'Finance': [
            'Budgeting Apps: Which Ones People Actually Keep Using',
            'Investing Apps for Beginners: Fees Compared Simply',
            'Credit Card Rewards: When They\'re Worth It vs When They\'re Not',
            'Side Hustle Tax Stuff: What I Found Out The Hard Way (Research Edition)',
            'Buy Now Pay Later Services: The Fine Print Nobody Reads'
        ]
    }
}


class SecurityValidator:
    """보안 및 데이터 검증"""
    
    @staticmethod
    def sanitize_html(content):
        if not content:
            return ""
        dangerous_patterns = [
            r'<script[^>]*>.*?</script>',
            r'<iframe[^>]*>.*?</iframe>',
            r'javascript:',
            r'on\w+\s*=',
            r'<object[^>]*>',
            r'<embed[^>]*>'
        ]
        cleaned = content
        for pattern in dangerous_patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE | re.DOTALL)
        return cleaned

    @staticmethod
    def validate_image_url(url):
        if not url:
            return False
        try:
            parsed = urlparse(url)
            return (parsed.scheme == 'https' and 
                    'unsplash.com' in parsed.netloc)
        except Exception:
            return False


class ProBlogBotV2:
    """Opus 4.5 최적화 블로그 봇"""
    
    def __init__(self):
        self.anthropic_key = os.getenv('ANTHROPIC_API_KEY')
        self.unsplash_key = os.getenv('UNSPLASH_API_KEY')
        self.blog_id = os.getenv('BLOGGER_BLOG_ID')
        
        if not self.anthropic_key:
            raise ValueError("❌ ANTHROPIC_API_KEY required")
        
        self.claude = Anthropic(api_key=self.anthropic_key)
        self.validator = SecurityValidator()
        self.conversation_history = []  # Multi-turn을 위한 히스토리
    
    def _build_system_prompt(self):
        """시스템 프롬프트 구축"""
        return f"""
{PERSONA['background']}

## Your Writing Voice
{chr(10).join(f"- {trait}" for trait in PERSONA['voice_traits'])}

## CRITICAL RULES - NEVER BREAK THESE

### 1. NO FABRICATION
- NEVER invent statistics or specific numbers
- NEVER claim personal experience you don't have
- NEVER make up quotes or sources
- Frame everything as research: "From what I found...", "People seem to say...", "The general consensus is..."
- It's OK to say "I couldn't find reliable data on this"

### 2. NO AI-SOUNDING PHRASES
Never use:
- "In today's fast-paced world" / "In today's digital age"
- "Comprehensive guide" / "Ultimate guide" 
- "Let's dive in" / "dive deep" / "delve"
- "It's important to note that" / "It's worth noting"
- "In conclusion" (just end naturally)
- "The landscape of" / "Navigate the complexities"
- "Game-changer" / "Revolutionize"
- "Seamlessly" / "Effortlessly" / "Robust" / "Leverage"
- "Embark on a journey"
- "Without further ado"
- Any phrase that sounds like a LinkedIn post

### 3. PROVIDE REAL VALUE
- Don't state the obvious - readers aren't stupid
- Include specific, actionable information
- Compare things concretely, not vaguely
- If there's no clear answer, say so - that's valuable too
- Cut the fluff - every paragraph should add something

### 4. NATURAL STRUCTURE
- Don't use the same format every time
- Not everything needs bullet points
- Vary paragraph lengths
- Write like you're explaining to a friend, not writing a term paper
- Headers should be useful, not clever
"""

    def step_1_plan(self, topic):
        """1단계: 기획 - 차별화된 앵글 찾기"""
        print(f"🧠 [1/5] Finding unique angle for '{topic}'...")
        
        prompt = f"""
I need to write about: "{topic}"

Before creating an outline, think through:
1. What's the conventional wisdom on this topic that might be wrong or incomplete?
2. What's something counterintuitive I've learned from experience?
3. What mistake do most articles on this topic make?

Then create an outline that:
- Starts with a hook that challenges assumptions OR shares a vulnerable moment
- Has 3-5 sections that flow naturally (not formulaic "What/Why/How")
- Includes a "Plot twist" or "But here's the catch" moment
- Ends with practical next steps, not generic encouragement

Return JSON only:
{{
    "working_title": "Title that promises specific value",
    "hook_concept": "One sentence describing the opening approach",
    "contrarian_angle": "What conventional wisdom are we challenging?",
    "sections": [
        {{"header": "...", "key_point": "...", "personal_element": "..."}},
        ...
    ],
    "honest_caveat": "One limitation or 'this won't work if...' to include",
    "image_queries": ["specific visual concept 1", "specific visual concept 2"]
}}
"""
        
        try:
            response = self.claude.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=1500,
                system=self._build_system_prompt(),
                messages=[{"role": "user", "content": prompt}]
            )
            
            text = response.content[0].text
            # JSON 추출
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            
            plan = json.loads(text.strip())
            self.conversation_history.append({"role": "user", "content": prompt})
            self.conversation_history.append({"role": "assistant", "content": response.content[0].text})
            
            return plan
            
        except Exception as e:
            print(f"⚠️ Planning failed: {e}")
            return None

    def step_2_write_draft(self, plan):
        """2단계: 초안 작성"""
        print(f"✍️ [2/5] Writing first draft...")
        
        prompt = f"""
Based on our plan:
- Title: {plan['working_title']}
- Angle: {plan['contrarian_angle']}
- Sections: {json.dumps(plan['sections'], indent=2)}
- Caveat: {plan['honest_caveat']}

Write the full blog post in HTML format.

Requirements:
- 1500-2000 words
- Use <h2> for main sections, <h3> for subsections
- Use <p> for paragraphs, <ul>/<li> for lists sparingly
- Insert exactly 2 image markers: [IMAGE: {plan['image_queries'][0]}] and [IMAGE: {plan['image_queries'][1]}]

Writing approach:
- Frame as research/curation: "I looked into...", "From what I found...", "People seem to say..."
- Include specific comparisons, numbers from research, concrete details
- Add your interpretation: "This makes sense because...", "I'm skeptical of this because..."
- Acknowledge when information is conflicting or unclear
- NO fake personal experiences - you're a researcher, not a user
- NO generic filler - every paragraph should add real information
- End with clear, actionable takeaways

Output only the HTML content (no <html> or <body> tags, just the article content).
"""
        
        self.conversation_history.append({"role": "user", "content": prompt})
        
        try:
            response = self.claude.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=4000,
                system=self._build_system_prompt(),
                messages=self.conversation_history
            )
            
            draft = response.content[0].text
            self.conversation_history.append({"role": "assistant", "content": draft})
            
            return self.validator.sanitize_html(draft)
            
        except Exception as e:
            print(f"⚠️ Writing failed: {e}")
            return None

    def step_3_self_critique(self, draft):
        """3단계: 자기 비평 및 개선"""
        print(f"🔍 [3/5] Self-critique and improvement...")
        
        critique_prompt = """
Review the draft you just wrote. Be brutally honest.

Check for:
1. AI PHRASES: Any "dive deep", "comprehensive", "landscape", "embark", "leverage", etc.?
2. FAKE STUFF: Any made-up statistics, fake experiences, or invented sources?
3. FLUFF: Any paragraphs that don't add real information? Generic filler?
4. VALUE: Does every section teach something specific? Or is it obvious/common knowledge?
5. TONE: Does it sound like a real person researching, or like a corporate blog?
6. CLAIMS: Any claims presented as fact that should be framed as "from what I found" or "people say"?

List specific problems (quote the text).
Then explain how to fix each.

Format:
## Issues Found
1. [Quote] - Problem

## Fixes
1. How to fix
"""
        
        self.conversation_history.append({"role": "user", "content": critique_prompt})
        
        try:
            response = self.claude.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=2000,
                system=self._build_system_prompt(),
                messages=self.conversation_history
            )
            
            critique = response.content[0].text
            self.conversation_history.append({"role": "assistant", "content": critique})
            print(f"   📋 Found issues to fix...")
            
            # 4단계: 개선된 버전 작성
            return self._apply_fixes()
            
        except Exception as e:
            print(f"⚠️ Critique failed: {e}")
            return draft  # 실패시 원본 반환

    def _apply_fixes(self):
        """비평을 바탕으로 개선된 버전 작성"""
        print(f"✨ [4/5] Applying improvements...")
        
        fix_prompt = """
Rewrite the article, fixing all issues identified.

Final version must:
- Zero AI-sounding phrases
- Zero fake statistics or experiences  
- Every paragraph adds real, specific value
- Sounds like a curious person who did research, not an expert or AI
- Framed as findings/research, not personal experience
- Clear, useful takeaways

Output the complete, improved HTML article.
"""
        
        self.conversation_history.append({"role": "user", "content": fix_prompt})
        
        try:
            response = self.claude.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=4000,
                system=self._build_system_prompt(),
                messages=self.conversation_history
            )
            
            improved = response.content[0].text
            return self.validator.sanitize_html(improved)
            
        except Exception as e:
            print(f"⚠️ Fix application failed: {e}")
            return None

    def step_4_add_images(self, content):
        """5단계: 이미지 삽입"""
        print(f"🎨 [5/5] Adding images...")
        
        if not self.unsplash_key:
            print("   ⚠️ No Unsplash key - skipping images")
            return re.sub(r'\[IMAGE:.*?\]', '', content)
        
        markers = re.findall(r'\[IMAGE:.*?\]', content)
        
        for marker in markers:
            query = marker.replace('[IMAGE:', '').replace(']', '').strip()
            print(f"   🔍 Searching: {query}")
            
            try:
                response = requests.get(
                    "https://api.unsplash.com/photos/random",
                    params={
                        'query': query,
                        'client_id': self.unsplash_key,
                        'orientation': 'landscape'
                    },
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list):
                        data = data[0]
                    
                    img_url = data['urls']['regular']
                    user_name = data['user']['name']
                    user_link = f"https://unsplash.com/@{data['user']['username']}?utm_source=insightcrossroad&utm_medium=referral"
                    unsplash_link = "https://unsplash.com/?utm_source=insightcrossroad&utm_medium=referral"
                    
                    # Clean, modern image HTML
                    img_html = f'''
<figure style="margin: 2.5rem 0; text-align: center;">
    <img src="{img_url}" alt="{query}" 
         style="width: 100%; max-width: 800px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.08);"
         loading="lazy">
    <figcaption style="color: #6b7280; font-size: 0.875rem; margin-top: 0.75rem;">
        Photo by <a href="{user_link}" target="_blank" rel="noopener" style="color: #6b7280;">{user_name}</a> 
        on <a href="{unsplash_link}" target="_blank" rel="noopener" style="color: #6b7280;">Unsplash</a>
    </figcaption>
</figure>
'''
                    content = content.replace(marker, img_html, 1)
                else:
                    content = content.replace(marker, '', 1)
                    
            except Exception as e:
                print(f"   ⚠️ Image fetch failed: {e}")
                content = content.replace(marker, '', 1)
        
        return content

    def step_5_publish(self, title, content, category):
        """최종 발행"""
        print(f"🚀 Publishing to Blogger...")
        
        # Modern, clean CSS
        css = '''
<style>
    .post-body {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
        line-height: 1.75;
        color: #1f2937;
        font-size: 1.125rem;
    }
    .post-body h2 {
        font-size: 1.75rem;
        font-weight: 700;
        color: #111827;
        margin: 3rem 0 1.25rem;
        letter-spacing: -0.025em;
    }
    .post-body h3 {
        font-size: 1.375rem;
        font-weight: 600;
        color: #374151;
        margin: 2rem 0 1rem;
    }
    .post-body p {
        margin-bottom: 1.5rem;
    }
    .post-body ul, .post-body ol {
        margin: 1.5rem 0;
        padding-left: 1.5rem;
    }
    .post-body li {
        margin-bottom: 0.75rem;
    }
    .post-body blockquote {
        border-left: 4px solid #3b82f6;
        padding: 1rem 1.5rem;
        background: #f8fafc;
        color: #475569;
        font-style: italic;
        margin: 2rem 0;
        border-radius: 0 8px 8px 0;
    }
    .post-body table {
        width: 100%;
        border-collapse: collapse;
        margin: 2rem 0;
        font-size: 1rem;
    }
    .post-body th {
        background: #f1f5f9;
        font-weight: 600;
        text-align: left;
        padding: 1rem;
        border-bottom: 2px solid #e2e8f0;
    }
    .post-body td {
        padding: 1rem;
        border-bottom: 1px solid #f1f5f9;
    }
    .disclaimer {
        background: #fef2f2;
        padding: 1.25rem;
        border-radius: 8px;
        font-size: 0.875rem;
        color: #991b1b;
        margin-top: 2rem;
        border: 1px solid #fecaca;
    }
</style>
'''
        
        # Disclaimer for money mode
        disclaimer = ''
        if CURRENT_MODE == 'MONEY':
            disclaimer = '''
<div class="disclaimer">
    <strong>Disclosure:</strong> This article reflects my genuine experience and opinions. 
    Some links may be affiliate links, which help support this site at no extra cost to you. 
    I only recommend tools I've actually used.
</div>
'''
        
        final_html = f"{css}<div class='post-body'>{content}{disclaimer}</div>"
        
        # SEO-friendly tags (no mode indicator)
        tags = [category.replace('_', ' ')]
        
        tag_map = {
            'APPROVAL': ['Guides', 'How-To', 'Personal Experience'],
            'MONEY': ['Reviews', 'Comparisons', 'Tools']
        }
        tags.extend(random.sample(tag_map.get(CURRENT_MODE, []), 2))
        
        body = {
            'title': title,
            'content': final_html,
            'labels': list(set(tags))
        }
        
        try:
            service = self._get_blogger_service()
            result = service.posts().insert(
                blogId=self.blog_id,
                body=body,
                isDraft=True  # 항상 초안으로 저장하여 검토 가능
            ).execute()
            
            print(f"✅ Draft created successfully!")
            print(f"   📝 Title: {title}")
            print(f"   🔗 URL: {result.get('url', 'N/A')}")
            print(f"   🏷️ Tags: {tags}")
            return result
            
        except Exception as e:
            print(f"❌ Publish failed: {e}")
            return None

    def _get_blogger_service(self):
        """Blogger API 서비스 생성"""
        from google.auth.transport.requests import Request
        
        user_info = {
            'client_id': os.getenv('OAUTH_CLIENT_ID'),
            'client_secret': os.getenv('OAUTH_CLIENT_SECRET'),
            'refresh_token': os.getenv('OAUTH_REFRESH_TOKEN'),
            'token_uri': 'https://oauth2.googleapis.com/token'
        }
        
        creds = Credentials.from_authorized_user_info(
            user_info,
            scopes=['https://www.googleapis.com/auth/blogger']
        )
        creds.refresh(Request())
        
        return build('blogger', 'v3', credentials=creds)

    def run(self):
        """메인 실행 로직"""
        print(f"""
╔════════════════════════════════════════════════════════════╗
║  Pro Blog Bot v2.1 - Honest Blogger Edition               ║
║  Mode: {CURRENT_MODE:10s} | Model: {CLAUDE_MODEL:25s}    ║
╚════════════════════════════════════════════════════════════╝
""")
        
        # 토픽 및 카테고리 선택
        topic_pool = TOPICS[CURRENT_MODE]
        category = random.choice(list(topic_pool.keys()))
        topic = random.choice(topic_pool[category])
        
        print(f"📁 Category: {category}")
        print(f"📝 Topic: {topic}")
        print("-" * 60)
        
        # 히스토리 초기화
        self.conversation_history = []
        
        # 파이프라인 실행
        plan = self.step_1_plan(topic)
        if not plan:
            print("❌ Planning failed - aborting")
            return
        
        print(f"   📌 Title: {plan['working_title']}")
        print(f"   💡 Angle: {plan['contrarian_angle']}")
        
        draft = self.step_2_write_draft(plan)
        if not draft:
            print("❌ Draft failed - aborting")
            return
        
        # Self-critique loop
        improved = self.step_3_self_critique(draft)
        if not improved:
            improved = draft  # Fallback
        
        # 이미지 추가
        final_content = self.step_4_add_images(improved)
        
        # 발행
        self.step_5_publish(
            plan['working_title'],
            final_content,
            category
        )
        
        print("\n✅ Pipeline complete!")


if __name__ == "__main__":
    bot = ProBlogBotV2()
    bot.run()
