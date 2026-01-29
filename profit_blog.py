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
# 🎭 PERSONA SYSTEM - 핵심 차별화 요소
# ==========================================

PERSONAS = {
    'tech_pragmatist': {
        'name': 'Alex',
        'background': """You are Alex, a 36-year-old senior product manager who spent 9 years at mid-size B2B SaaS companies before going independent as a consultant. You've shipped 12 products, killed 4 that weren't working, and learned more from failures than successes. You write like you're explaining things to a smart colleague over coffee - direct, practical, occasionally sarcastic but never mean. You have strong opinions loosely held.""",
        'voice_traits': [
            "Uses 'Look,' or 'Here's the thing:' to start contrarian points",
            "Admits uncertainty with 'I might be wrong, but...' or 'In my experience...'",
            "References specific (but anonymized) past projects: 'At a fintech startup I consulted for...'",
            "Occasionally self-deprecating: 'I learned this the hard way when I...'",
            "Ends sections with actionable takeaways, not fluff"
        ],
        'categories': ['Productivity', 'Tech_Tips', 'SaaS_Review']
    },
    'wellness_realist': {
        'name': 'Jordan',
        'background': """You are Jordan, a 41-year-old former HR director turned wellness coach. You spent 15 years in corporate environments watching people burn out, including yourself once. You're skeptical of hustle culture and "productivity porn." You write with warmth but don't sugarcoat things. You believe sustainable habits beat dramatic transformations.""",
        'voice_traits': [
            "Starts with relatable struggles: 'I used to think...' or 'Like most people, I...'",
            "Challenges common advice: 'Contrary to what most gurus say...'",
            "Grounds advice in psychology without being academic",
            "Uses 'we' to create solidarity: 'We've all been there'",
            "Acknowledges that not everything works for everyone"
        ],
        'categories': ['Wellness', 'Work_Life']
    },
    'finance_skeptic': {
        'name': 'Sam',
        'background': """You are Sam, a 44-year-old CPA who left Big 4 accounting to run a small advisory practice. You've seen every financial mistake in the book and made a few yourself. You're deeply skeptical of get-rich-quick schemes and "passive income" hype. You explain complex topics simply without being condescending.""",
        'voice_traits': [
            "Leads with 'Let me be direct:' or 'The honest truth is...'",
            "Uses real-world examples: 'I had a client who...' (anonymized)",
            "Warns about common pitfalls before giving advice",
            "Distinguishes between 'what works in theory' and 'what I've seen work'",
            "Always mentions risks alongside opportunities"
        ],
        'categories': ['Finance', 'Hosting', 'Business']
    }
}

# ==========================================
# 📝 TOPIC POOLS
# ==========================================

TOPICS = {
    'APPROVAL': {
        'Productivity': [
            'Why Most Productivity Systems Fail (And What Actually Works)',
            'The Case Against Morning Routines',
            'Deep Work Is Overrated for Most Jobs',
            'How I Finally Fixed My Email Overwhelm',
            'The Hidden Cost of Context Switching'
        ],
        'Wellness': [
            'Burnout Recovery Takes Longer Than You Think',
            'Why "Work-Life Balance" Is the Wrong Goal',
            'The Ergonomic Setup That Actually Helped My Back',
            'Mindfulness Apps Didn\'t Work for Me Until I Changed This',
            'Sleep Optimization Without the Obsession'
        ],
        'Tech_Tips': [
            'Password Managers: What I Wish I Knew Sooner',
            'The Backup Strategy That Saved My Business',
            'Browser Extensions I Actually Use Daily',
            'Why I Switched to a Simpler Note-Taking System',
            'Two-Factor Authentication: A Practical Guide'
        ]
    },
    'MONEY': {
        'SaaS_Review': [
            'I Tested 7 Project Management Tools - Here\'s What I Found',
            'CRM Software: The Features That Actually Matter',
            'Email Marketing Platforms Compared (A Practitioner\'s View)',
            'The Accounting Software Decision Framework',
            'Collaboration Tools: Cutting Through the Hype'
        ],
        'Hosting': [
            'Web Hosting for Small Business: An Honest Assessment',
            'Cloud Storage Pricing: What You\'re Really Paying For',
            'Managed WordPress Hosting: When It\'s Worth It',
            'VPS vs Shared Hosting: A Decision Guide',
            'CDN Services Compared for Non-Technical Users'
        ],
        'Finance': [
            'Budgeting Apps: What Works Beyond the First Month',
            'Investment Platforms for Beginners: Realistic Expectations',
            'Business Credit Cards: Understanding the Fine Print',
            'Expense Tracking Tools: A Practical Comparison',
            'Tax Software Limitations You Should Know'
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
        
    def _select_persona(self, category):
        """카테고리에 맞는 persona 선택"""
        for persona_key, persona in PERSONAS.items():
            if category in persona['categories']:
                return persona
        # 기본값
        return PERSONAS['tech_pragmatist']
    
    def _build_system_prompt(self, persona):
        """Persona 기반 시스템 프롬프트 구축"""
        return f"""
{persona['background']}

## Your Writing Voice
{chr(10).join(f"- {trait}" for trait in persona['voice_traits'])}

## CRITICAL RULES - NEVER BREAK THESE

### 1. NO FABRICATED STATISTICS
- NEVER write specific numbers like "73% of users" or "studies show that 8 out of 10..."
- NEVER cite fake research papers, surveys, or reports
- Instead use: "many users report...", "research suggests...", "in my experience...", "I've noticed that..."
- When uncertain, frame it as opinion: "I believe...", "My take is..."

### 2. NO AI-SOUNDING PHRASES
Never use these phrases:
- "In today's fast-paced world"
- "In this comprehensive guide"
- "Let's dive in" / "dive deep"
- "At the end of the day"
- "It's important to note that"
- "In conclusion" (just conclude naturally)
- "Delve into"
- "The landscape of"
- "Revolutionize" / "game-changer"
- "Seamlessly" / "effortlessly"
- "Robust" / "leverage"
- "Take your X to the next level"

### 3. AUTHENTICITY MARKERS
Every post MUST include:
- At least one "I was wrong about..." or "I used to think..." moment
- A specific (anonymized) example from your experience
- One genuine limitation or caveat about your advice
- A "what I'm still figuring out" mention

### 4. STRUCTURE VARIETY
Don't always use the same structure. Mix it up:
- Sometimes start with a story, sometimes with a hot take
- Vary section lengths - not everything needs to be perfectly balanced
- Include occasional asides or parenthetical thoughts (like this)
- Not every point needs a subheader
"""

    def step_1_plan(self, topic, persona):
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
                system=self._build_system_prompt(persona),
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

    def step_2_write_draft(self, plan, persona):
        """2단계: 초안 작성"""
        print(f"✍️ [2/5] Writing first draft...")
        
        prompt = f"""
Based on our plan:
- Title: {plan['working_title']}
- Contrarian angle: {plan['contrarian_angle']}
- Sections: {json.dumps(plan['sections'], indent=2)}
- Caveat to include: {plan['honest_caveat']}

Write the full blog post in HTML format.

Requirements:
- 1500-2000 words
- Use <h2> for main sections, <h3> for subsections
- Use <p> for paragraphs, <ul>/<li> for lists
- Insert exactly 2 image markers: [IMAGE: {plan['image_queries'][0]}] and [IMAGE: {plan['image_queries'][1]}]
- First image after the opening section
- Second image before the conclusion

Remember:
- Write as {persona['name']} with your unique voice
- Include specific examples from your experience
- No fabricated statistics - use qualitative language
- Vary sentence length and structure
- Include at least one self-deprecating moment
- End with actionable steps, not generic motivation

Output only the HTML content (no <html> or <body> tags, just the article content).
"""
        
        self.conversation_history.append({"role": "user", "content": prompt})
        
        try:
            response = self.claude.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=4000,
                system=self._build_system_prompt(persona),
                messages=self.conversation_history
            )
            
            draft = response.content[0].text
            self.conversation_history.append({"role": "assistant", "content": draft})
            
            return self.validator.sanitize_html(draft)
            
        except Exception as e:
            print(f"⚠️ Writing failed: {e}")
            return None

    def step_3_self_critique(self, draft, persona):
        """3단계: 자기 비평 및 개선 (Opus 4.5 강점 활용)"""
        print(f"🔍 [3/5] Self-critique and improvement...")
        
        critique_prompt = f"""
Review the draft you just wrote. Be brutally honest.

Check for:
1. AI-SOUNDING PHRASES: Any "dive deep", "in today's world", "comprehensive guide", etc.?
2. FAKE STATISTICS: Any specific percentages or numbers that sound made up?
3. GENERIC ADVICE: Any sections that could appear in any article on this topic?
4. VOICE CONSISTENCY: Does it sound like {persona['name']} throughout?
5. AUTHENTICITY: Are the personal examples specific enough? Or too vague?
6. FLOW: Any awkward transitions or repetitive structures?

List specific problems you found (be specific - quote the problematic text).
Then explain how you'll fix each one.

Format:
## Issues Found
1. [Quote problematic text] - Why it's a problem

## Fixes
1. [How you'll fix it]
"""
        
        self.conversation_history.append({"role": "user", "content": critique_prompt})
        
        try:
            response = self.claude.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=2000,
                system=self._build_system_prompt(persona),
                messages=self.conversation_history
            )
            
            critique = response.content[0].text
            self.conversation_history.append({"role": "assistant", "content": critique})
            print(f"   📋 Found issues to fix...")
            
            # 4단계: 개선된 버전 작성
            return self._apply_fixes(persona)
            
        except Exception as e:
            print(f"⚠️ Critique failed: {e}")
            return draft  # 실패시 원본 반환

    def _apply_fixes(self, persona):
        """비평을 바탕으로 개선된 버전 작성"""
        print(f"✨ [4/5] Applying improvements...")
        
        fix_prompt = """
Now rewrite the entire article, applying all the fixes you identified.

This is your final version - make it count. Ensure:
- Every AI-sounding phrase is replaced with natural language
- All fake statistics are converted to qualitative statements
- Personal examples are specific and believable
- The voice is consistent and human throughout
- Transitions feel natural, not formulaic

Output the complete, improved HTML article.
"""
        
        self.conversation_history.append({"role": "user", "content": fix_prompt})
        
        try:
            response = self.claude.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=4000,
                system=self._build_system_prompt(persona),
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

    def step_5_publish(self, title, content, category, persona):
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
║  Pro Blog Bot v2.0 - Opus 4.5 Optimized                   ║
║  Mode: {CURRENT_MODE:10s} | Model: {CLAUDE_MODEL:25s}    ║
╚════════════════════════════════════════════════════════════╝
""")
        
        # 토픽 및 카테고리 선택
        topic_pool = TOPICS[CURRENT_MODE]
        category = random.choice(list(topic_pool.keys()))
        topic = random.choice(topic_pool[category])
        
        # Persona 선택
        persona = self._select_persona(category)
        print(f"👤 Persona: {persona['name']}")
        print(f"📁 Category: {category}")
        print(f"📝 Topic: {topic}")
        print("-" * 60)
        
        # 히스토리 초기화
        self.conversation_history = []
        
        # 파이프라인 실행
        plan = self.step_1_plan(topic, persona)
        if not plan:
            print("❌ Planning failed - aborting")
            return
        
        print(f"   📌 Title: {plan['working_title']}")
        print(f"   💡 Angle: {plan['contrarian_angle']}")
        
        draft = self.step_2_write_draft(plan, persona)
        if not draft:
            print("❌ Draft failed - aborting")
            return
        
        # Self-critique loop (Opus 4.5 강점)
        improved = self.step_3_self_critique(draft, persona)
        if not improved:
            improved = draft  # Fallback
        
        # 이미지 추가
        final_content = self.step_4_add_images(improved)
        
        # 발행
        self.step_5_publish(
            plan['working_title'],
            final_content,
            category,
            persona
        )
        
        print("\n✅ Pipeline complete!")


if __name__ == "__main__":
    bot = ProBlogBotV2()
    bot.run()
