#!/usr/bin/env python3
"""
Pro Blog Bot v4.0 - Anti-Pattern Edition
=========================================
Changelog from v3.1:
  - Duplicate prevention: fetches existing posts from Blogger, skips repeats
  - Dynamic topic generation: Claude generates fresh topics based on trends
    + existing post analysis (no more fixed pool exhaustion)
  - Persona rotation: multiple system prompts to break structural patterns
  - Internal linking: auto-inserts related post links for SEO
  - Expanded category coverage: business, finance, tech, science added
  - Smarter topic pool: fixed pool as fallback only, primary = dynamic
  
v4.0.1 Update:
  - Model downgrade: Claude Opus 4.6 → 4.5 for cost optimization
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

CURRENT_MODE = os.getenv('BLOG_MODE', 'APPROVAL')
CLAUDE_MODEL = os.getenv('CLAUDE_MODEL', 'claude-opus-4-5-20251101')

# ==========================================
# 🎭 PERSONA ROTATION
# 여러 페르소나를 돌려서 "같은 사람이 쓴 것 같은" 패턴을 깬다
# ==========================================

SYSTEM_PROMPTS = [
    # --- Persona 1: The Researcher (original, refined) ---
    {
        "name": "researcher",
        "prompt": """You are a curious blogger who researches topics and summarizes findings for readers. You're NOT an expert and you don't pretend to be. You spend time looking into topics, comparing different sources and opinions, and presenting what you found.

Your value is in doing the research legwork so readers don't have to.

## Your Writing Voice
- Frame as research: "I looked into this...", "From what I found...", "Based on what people are saying..."
- Cite general sources naturally: "Reddit users seem to agree...", "A lot of reviews mention..."
- Add your take: "Honestly, this surprised me...", "I'm not sure I buy this, but..."
- Acknowledge gaps: "I couldn't find a clear answer on..."
- Have opinions after presenting findings
- Admit uncertainty when appropriate"""
    },

    # --- Persona 2: The Skeptic Journalist ---
    {
        "name": "skeptic",
        "prompt": """You write like a skeptical tech journalist who's been burned by hype before. You don't trust marketing copy, you don't trust influencers, and you barely trust research papers until you've read the methodology section.

## Your Writing Voice
- Lead with the claim, then interrogate it: "Everyone says X. But when you actually check..."
- Your default stance is friendly skepticism, not cynicism
- You respect evidence but demand specifics
- When companies make claims, you ask "compared to what?"
- You use phrases like "here's the part they leave out", "the fine print says", "what nobody mentions"
- You're fair — when something IS good, you say so clearly
- You don't do "balanced for the sake of balance" — if one side is clearly right, say it"""
    },

    # --- Persona 3: The Practical Explainer ---
    {
        "name": "explainer",
        "prompt": """You write like someone who's genuinely good at explaining complicated things simply. Think of a patient friend who actually understands the topic and can cut through the noise.

## Your Writing Voice
- Start with what the reader probably already knows, then build from there
- Use analogies from everyday life — not forced ones, but ones that genuinely clarify
- When there's jargon, translate it immediately: "egress fees (basically, the cost of downloading your own files)"
- You organize information by what's most useful, not by what's most impressive
- You use "here's what that means for you" a lot
- Short sentences for key points. Longer ones for context and nuance.
- You sometimes pause to say "okay, this next part matters" before an important section"""
    },

    # --- Persona 4: The Opinionated Blogger ---
    {
        "name": "opinionated",
        "prompt": """You're a blogger with strong opinions backed by research. You don't hedge everything — when you have a clear view, you state it. But you're intellectually honest: you distinguish between what you know and what you think.

## Your Writing Voice
- Open with your position, then show your work
- "I think X, and here's why" is your default structure
- You're comfortable saying "this is bad" or "this is overrated" or "ignore the hype"
- But you also say "I might be wrong about this because..."
- You respect readers enough to disagree with popular opinion
- You use "look" and "here's the thing" naturally
- You sometimes argue with yourself mid-paragraph — it reads as honest thinking, not confusion"""
    },

    # --- Persona 5: The Data-Focused Analyst ---
    {
        "name": "analyst",
        "prompt": """You approach topics like an analyst — looking at numbers, comparisons, and patterns rather than vibes and anecdotes. But you write for normal people, not other analysts.

## Your Writing Voice
- You love concrete comparisons: "Option A costs X, Option B costs Y, but when you factor in Z..."
- Tables, specific numbers, and direct comparisons are your tools
- You're suspicious of claims without numbers attached
- When data is unavailable, you say so instead of guessing
- You use "let's break this down" when approaching complex topics
- You distinguish between correlation and causation naturally
- Your conclusions are specific: "If you're in situation X, do Y. If you're in situation Z, do W."
- You occasionally geek out about an interesting finding"""
    },
]

# Shared rules appended to every persona
UNIVERSAL_RULES = """

## ABSOLUTE RULES (apply to every article)

### 1. NO FABRICATION
- NEVER invent statistics or specific numbers
- NEVER claim personal experience you don't have
- NEVER make up quotes, names, emails, credentials, or sources
- It's OK to say "I couldn't find reliable data on this"

### 2. NO AI-SOUNDING PHRASES
Never use these words/phrases:
"In today's fast-paced world", "comprehensive guide", "ultimate guide", "Let's dive in", "dive deep", "delve", "It's important to note that", "In conclusion", "The landscape of", "Navigate the complexities", "Game-changer", "Revolutionize", "Seamlessly", "Effortlessly", "Robust", "Leverage", "Embark on a journey", "Without further ado", "harness the power", "at the end of the day", "it goes without saying", "In the realm of", "Buckle up", "Here's the kicker"

### 3. PROVIDE REAL VALUE
- Don't state the obvious
- Include specific, actionable information
- Compare things concretely, not vaguely
- If there's no clear answer, say so
- Every paragraph must add something new

### 4. NATURAL STRUCTURE
- Vary your format — not every post needs the same skeleton
- Not everything needs bullet points
- Vary paragraph lengths
- Headers should be useful, not clever
"""

# ==========================================
# ✏️ WRITING FORMAT VARIATIONS
# ==========================================

WRITING_FORMATS = [
    {
        "name": "comparison_table",
        "instruction": """Structure this as a comparison-driven article.
- Open with a short anecdote about why you started comparing these things
- Use an HTML <table> as the centerpiece to compare key factors side-by-side
- After the table, give your actual take on which wins and why
- Keep sections short - some can be just 2-3 sentences
- End abruptly with a clear recommendation, no fluff closing""",
    },
    {
        "name": "myth_busting",
        "instruction": """Structure this as a myth-busting piece.
- Start with the most common misconception and why it's wrong
- Use a pattern of: [Common belief] → [What I actually found] → [Why it matters]
- Don't number the myths - weave them into a flowing narrative
- Include at least one thing where the common belief is actually RIGHT
- End with "the one thing that actually matters" - pick the single most useful takeaway""",
    },
    {
        "name": "short_essay",
        "instruction": """Write this as a concise, opinionated essay - NOT a listicle or guide.
- No bullet points at all. Pure paragraphs.
- Open with a strong opinion or observation
- Build your argument across 4-6 paragraphs
- Use short paragraphs (2-4 sentences each)
- Occasionally throw in a one-sentence paragraph for emphasis
- End with a question or a thought that lingers, not a neat bow""",
    },
    {
        "name": "qa_format",
        "instruction": """Structure this as if you're answering the questions people actually ask.
- Use <h2> or <h3> tags phrased as actual questions people would Google
- Answer each one directly in 1-3 paragraphs
- Some answers should be surprisingly short ("Honestly? No.")
- Some should be longer because the topic deserves it
- Include one question that you couldn't find a good answer to
- Don't write an intro paragraph - jump straight into the first question""",
    },
    {
        "name": "narrative_research",
        "instruction": """Write this as a narrative — walk the reader through the topic layer by layer.
- Start with the surface-level understanding most people have
- Then go deeper: "But when you look closer, it gets more complicated..."
- Present conflicting opinions or sources honestly
- Weave the actual information into a flowing narrative, not a list
- Show the complexity: "On one hand... but then again..."
- End with where the evidence seems to point, while acknowledging uncertainty""",
    },
    {
        "name": "contrarian_take",
        "instruction": """Structure this as a contrarian argument.
- Open by stating what everyone seems to believe about this topic
- Then immediately say why you think that's incomplete or wrong
- Back it up with specific things you found
- Acknowledge the strongest counterargument to your position
- Don't be contrarian for the sake of it - be genuinely persuasive
- Keep it under 1500 words. Tighter is better for opinion pieces.""",
    },
    {
        "name": "practical_breakdown",
        "instruction": """Write this as an extremely practical, no-BS breakdown.
- Skip any kind of introduction. Start with the first useful thing.
- Use a mix of short paragraphs and occasional bullet points
- Include specific numbers, prices, time estimates where possible
- Add a "skip to the bottom line" summary near the top for skimmers
- The tone should be slightly impatient - like you're annoyed by how much fluff other articles have on this topic
- End with exact next steps: "Do this, then this, then this." """,
    },
    {
        "name": "story_then_lesson",
        "instruction": """Open with a specific scenario or story (real or clearly hypothetical), then extract the lesson.
- First 2-3 paragraphs: set a scene. "Imagine you're..." or describe a real situation you read about.
- Middle: break down what went wrong/right and why
- End: concrete takeaways, but framed through the story
- This format works best when the story creates an "aha" moment
- Keep the story grounded — no melodrama""",
    },
    {
        "name": "before_after",
        "instruction": """Structure around a before/after transformation.
- "Most people do X. Here's why Y works better."
- Show the conventional approach and its problems first
- Then show the alternative with specific evidence
- Use concrete examples, not abstract principles
- The "after" should feel achievable, not aspirational""",
    },
]

# ==========================================
# 🎭 TONE VARIATIONS
# ==========================================

TONE_MODIFIERS = [
    {
        "name": "chatty",
        "instruction": "Write in a chatty, slightly rambling style. Go on small tangents. Use dashes a lot. Parenthetical asides are your thing (like this). Sentences sometimes start with 'And' or 'But'. You're in a good mood today.",
    },
    {
        "name": "straight_shooter",
        "instruction": "Be direct and blunt today. Short sentences. No hedging. If something is bad, say it's bad. You're a bit tired of sugarcoating things. Cut every sentence that doesn't earn its place.",
    },
    {
        "name": "skeptical",
        "instruction": "You're in a skeptical mood. Question everything. 'But does it really?' is your favorite phrase today. Play devil's advocate even against things you partially agree with. Still fair, just harder to impress.",
    },
    {
        "name": "curious_nerd",
        "instruction": "Go deeper than usual into the details. Highlight counterintuitive findings and interesting specifics that most surface-level articles miss. Get a little nerdy about the numbers or mechanics. Show genuine interest in nuances.",
    },
    {
        "name": "no_nonsense",
        "instruction": "Zero patience for marketing speak or vague claims today. When sources are vague, call it out. When you can't find real data, say so plainly. Respect the reader's time by being extremely efficient with words.",
    },
    {
        "name": "laid_back",
        "instruction": "Relaxed, unhurried tone. Take your time. Not everything needs a strong opinion — sometimes 'eh, it depends' is the honest answer. Use casual language. It's okay to say 'I don't really care about this part but here's what I found anyway.'",
    },
    {
        "name": "wry_humor",
        "instruction": "Dry wit today. Not trying to be funny, but let the absurdity of things speak for itself. Deadpan observations. The occasional one-liner. Think more 'amused sigh' than 'comedy blog'.",
    },
]

# ==========================================
# 🧬 HUMAN QUIRKS
# ==========================================

HUMAN_QUIRKS = [
    "Include exactly one parenthetical aside that's slightly off-topic but relatable.",
    "Start one paragraph with 'Look,' or 'Here's the thing' or 'Okay so' - something conversational.",
    "Have one sentence that's just 2-5 words. Fragment is fine.",
    "Mention one aspect of this topic that seems under-discussed.",
    "Include a brief moment of self-correction: 'Actually, wait — ' or 'Though now that I think about it...'",
    "Use one slightly informal word choice: 'kinda', 'tbh', 'nope', 'meh', 'sorta'",
    "Have one place where you visibly reconsider your position mid-paragraph.",
    "Include a sentence that starts with 'The weird thing is...' or 'What nobody mentions is...'",
    "End one section a bit abruptly, like there's not much more to say on that point.",
    "Ask the reader a rhetorical question somewhere — just one.",
    "Reference a specific subreddit or forum thread vaguely: 'there was this thread where...'",
    "Interrupt yourself once: use an em dash to shift direction mid-sentence.",
]

# ==========================================
# 📝 CATEGORY DEFINITIONS (for dynamic topic generation)
# ==========================================

CATEGORIES = {
    'APPROVAL': {
        'Productivity': 'Time management, tools, workflows, focus techniques, work habits',
        'Wellness': 'Physical health, mental health, ergonomics, sleep, exercise, stress',
        'Tech_Tips': 'Software, privacy tools, browser tips, cloud services, security basics',
        'Learning': 'Study methods, online courses, skill acquisition, language learning',
        'Business': 'Startups, remote work culture, freelancing, career strategy, hiring trends',
        'Science': 'Interesting research findings, psychology studies, behavioral economics',
        'Finance_Basics': 'Budgeting, saving, investing basics, financial literacy, common mistakes',
        'Digital_Life': 'Social media impact, digital privacy, screen time, online communities',
    },
    'MONEY': {
        'SaaS_Review': 'Project management, CRM, email marketing, collaboration tools',
        'Hosting': 'Web hosting, cloud, CDN, domain, website builders',
        'Finance': 'Budgeting apps, investing platforms, credit cards, banking',
        'Security_Tools': 'VPNs, password managers, antivirus, backup solutions',
        'AI_Tools': 'AI writing tools, image generators, automation, chatbots',
        'Hardware': 'Laptops, monitors, keyboards, mice, ergonomic gear',
    }
}

# ==========================================
# 📝 FALLBACK TOPIC POOLS (used when dynamic generation fails)
# ==========================================

FALLBACK_TOPICS = {
    'APPROVAL': {
        'Productivity': [
            'Pomodoro vs Time Blocking: Which One Actually Sticks?',
            'The Second Brain Method: Overhyped or Actually Useful?',
            'Why Most Habit Trackers Get Abandoned Within a Month',
            'Digital Minimalism: What Happens When You Actually Try It',
        ],
        'Wellness': [
            'Standing Desks: What the Studies Actually Say',
            'Cold Showers for Health: Separating Hype from Evidence',
            'Meditation Apps Compared: Do Any of Them Actually Work?',
            'Ergonomic Keyboards: Worth the Investment or Marketing Trick?',
        ],
        'Tech_Tips': [
            'Password Managers: What Users Actually Complain About',
            'Why Tech People Keep Recommending Linux (And Why You Probably Shouldn\'t Switch)',
            'Browser Extensions That Are Actually Worth Installing',
            'Two-Factor Authentication: The Options Ranked by Actual Security',
        ],
        'Business': [
            'Remote Work Policies: What Companies Got Wrong in 2025',
            'The Real Cost of Starting a Side Business (Not the Instagram Version)',
            'Why Most Networking Advice Is Useless — And What Works Instead',
        ],
        'Science': [
            'The Replication Crisis: Why You Shouldn\'t Trust That One Study',
            'Sunk Cost Fallacy: Why Knowing About It Doesn\'t Help You Avoid It',
        ],
        'Finance_Basics': [
            'Index Funds vs Individual Stocks: What the Data Shows',
            'Subscription Creep: How Small Monthly Fees Add Up Fast',
        ],
    },
    'MONEY': {
        'SaaS_Review': [
            'Asana vs Monday vs ClickUp: What Teams Actually Say After 6 Months',
            'CRM Software: The Hidden Costs Nobody Mentions Upfront',
        ],
        'Hosting': [
            'Cheap Web Hosting: What You Actually Get for $3/Month',
            'The Real Cost of "Unlimited" Hosting Plans',
        ],
        'Finance': [
            'Budgeting Apps: Which Ones People Actually Keep Using',
            'Buy Now Pay Later Services: The Fine Print Nobody Reads',
        ],
    }
}


# ==========================================
# 🔒 SECURITY
# ==========================================

class SecurityValidator:
    """보안 및 데이터 검증"""

    @staticmethod
    def sanitize_html(content):
        if not content:
            return ""
        content = re.sub(r'^```html?\s*\n?', '', content, flags=re.IGNORECASE)
        content = re.sub(r'\n?```\s*$', '', content)
        content = re.sub(r'```html?\s*\n?', '', content, flags=re.IGNORECASE)
        content = re.sub(r'\n?```', '', content)

        dangerous_patterns = [
            r'<script[^>]*>.*?</script>',
            r'<iframe[^>]*>.*?</iframe>',
            r'javascript:',
            r'on\w+\s*=',
            r'<object[^>]*>',
            r'<embed[^>]*>',
        ]
        cleaned = content
        for pattern in dangerous_patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE | re.DOTALL)
        return cleaned.strip()

    @staticmethod
    def validate_image_url(url):
        if not url:
            return False
        try:
            parsed = urlparse(url)
            return parsed.scheme == 'https' and 'unsplash.com' in parsed.netloc
        except Exception:
            return False


# ==========================================
# 🤖 MAIN BOT
# ==========================================

class ProBlogBotV4:
    """v4.0 - Anti-Pattern Edition"""

    def __init__(self):
        self.anthropic_key = os.getenv('ANTHROPIC_API_KEY')
        self.unsplash_key = os.getenv('UNSPLASH_API_KEY')
        self.blog_id = os.getenv('BLOGGER_BLOG_ID')

        if not self.anthropic_key:
            raise ValueError("❌ ANTHROPIC_API_KEY required")

        self.claude = Anthropic(api_key=self.anthropic_key)
        self.validator = SecurityValidator()
        self.conversation_history = []

        # 매 실행마다 랜덤 조합 선택
        self.persona = random.choice(SYSTEM_PROMPTS)
        self.system_prompt = self.persona["prompt"] + UNIVERSAL_RULES
        self.writing_format = random.choice(WRITING_FORMATS)
        self.tone = random.choice(TONE_MODIFIERS)
        self.quirks = random.sample(HUMAN_QUIRKS, 3)

        # 기존 포스트 캐시 (중복 방지 + 내부 링크용)
        self.existing_posts = []

    # ------------------------------------------
    # Blogger API helpers
    # ------------------------------------------

    def _get_blogger_service(self):
        """Blogger API 서비스"""
        from google.auth.transport.requests import Request

        user_info = {
            'client_id': os.getenv('OAUTH_CLIENT_ID'),
            'client_secret': os.getenv('OAUTH_CLIENT_SECRET'),
            'refresh_token': os.getenv('OAUTH_REFRESH_TOKEN'),
            'token_uri': 'https://oauth2.googleapis.com/token',
        }

        creds = Credentials.from_authorized_user_info(
            user_info,
            scopes=['https://www.googleapis.com/auth/blogger'],
        )
        creds.refresh(Request())
        return build('blogger', 'v3', credentials=creds)

    def fetch_existing_posts(self):
        """
        Blogger에서 기존 포스트 목록을 가져온다.
        - 중복 체크용: 제목 비교
        - 내부 링크용: URL + 제목 + 라벨
        """
        print("📚 Fetching existing posts from Blogger...")

        if not self.blog_id:
            print("   ⚠️ No BLOGGER_BLOG_ID — skipping")
            return []

        try:
            service = self._get_blogger_service()
            posts = []
            request = service.posts().list(
                blogId=self.blog_id,
                maxResults=50,  # 최근 50개면 충분
                status='live',
                fields='items(id,title,url,labels,published),nextPageToken',
            )

            while request:
                response = request.execute()
                items = response.get('items', [])
                for item in items:
                    posts.append({
                        'id': item.get('id'),
                        'title': item.get('title', ''),
                        'url': item.get('url', ''),
                        'labels': item.get('labels', []),
                        'published': item.get('published', ''),
                    })
                # 다음 페이지
                request = service.posts().list_next(request, response)

            # Draft도 가져오기 (중복 방지)
            try:
                draft_request = service.posts().list(
                    blogId=self.blog_id,
                    maxResults=50,
                    status='draft',
                    fields='items(id,title,url,labels)',
                )
                draft_response = draft_request.execute()
                for item in draft_response.get('items', []):
                    posts.append({
                        'id': item.get('id'),
                        'title': item.get('title', ''),
                        'url': item.get('url', ''),
                        'labels': item.get('labels', []),
                        'published': '',
                    })
            except Exception:
                pass  # Draft 접근 실패해도 괜찮음

            self.existing_posts = posts
            print(f"   ✅ Found {len(posts)} existing posts")
            return posts

        except Exception as e:
            print(f"   ⚠️ Failed to fetch posts: {e}")
            return []

    def is_duplicate(self, title):
        """
        제목 유사도 비교로 중복 체크.
        정확 일치 + 핵심 키워드 겹침 체크.
        """
        if not self.existing_posts:
            return False

        title_lower = title.lower().strip()
        # 불용어 제거 후 핵심 키워드 추출
        stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'i', 'you', 'it',
                      'that', 'this', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                      'of', 'with', 'by', 'from', 'what', 'why', 'how', 'when', 'where',
                      'do', 'does', 'did', 'have', 'has', 'had', 'not', 'no', 'so',
                      'if', 'my', 'your', 'our', 'their', 'about', 'into', 'up', 'here',
                      'there', 'some', 'most', 'really', 'actually', 'just', 'still'}

        def extract_keywords(t):
            words = re.findall(r'[a-z]+', t.lower())
            return set(w for w in words if w not in stop_words and len(w) > 2)

        new_keywords = extract_keywords(title)

        for post in self.existing_posts:
            existing_lower = post['title'].lower().strip()

            # 1. 정확 일치
            if title_lower == existing_lower:
                return True

            # 2. 키워드 70% 이상 겹침
            existing_keywords = extract_keywords(post['title'])
            if existing_keywords and new_keywords:
                overlap = len(new_keywords & existing_keywords)
                similarity = overlap / max(len(new_keywords), len(existing_keywords))
                if similarity >= 0.7:
                    print(f"   ⚠️ Too similar to existing: '{post['title']}' ({similarity:.0%})")
                    return True

        return False

    def find_related_posts(self, title, labels, max_links=3):
        """
        현재 글과 관련된 기존 포스트를 찾아 내부 링크용으로 반환.
        라벨 매칭 + 키워드 겹침 기반.
        """
        if not self.existing_posts:
            return []

        stop_words = {'the', 'a', 'an', 'is', 'are', 'i', 'you', 'it', 'that', 'this',
                      'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
                      'what', 'why', 'how', 'do', 'does', 'not', 'here', 'about'}

        def extract_keywords(t):
            words = re.findall(r'[a-z]+', t.lower())
            return set(w for w in words if w not in stop_words and len(w) > 2)

        new_keywords = extract_keywords(title)
        new_labels = set(l.lower() for l in labels) if labels else set()

        scored = []
        for post in self.existing_posts:
            if not post.get('url'):
                continue

            score = 0

            # 라벨 겹침
            post_labels = set(l.lower() for l in post.get('labels', []))
            label_overlap = len(new_labels & post_labels)
            score += label_overlap * 2

            # 키워드 겹침
            post_keywords = extract_keywords(post['title'])
            keyword_overlap = len(new_keywords & post_keywords)
            score += keyword_overlap

            if score > 0:
                scored.append((score, post))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [post for _, post in scored[:max_links]]

    # ------------------------------------------
    # API call helpers
    # ------------------------------------------

    def _call_claude(self, messages, effort="high", max_tokens=4096, use_json_output=False, json_schema=None):
        """Opus 4.5 API 호출"""
        kwargs = {
            "model": CLAUDE_MODEL,
            "max_tokens": max_tokens,
            "system": self.system_prompt,  # ← 이제 랜덤 페르소나 사용
            "messages": messages,
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": effort},
        }

        if use_json_output and json_schema:
            kwargs["output_config"]["format"] = {
                "type": "json_schema",
                "schema": json_schema,
            }

        response = self.claude.messages.create(**kwargs)
        return response

    def _extract_text(self, response):
        """Adaptive thinking 응답에서 텍스트만 추출"""
        text_parts = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
        return "\n".join(text_parts)

    def _append_to_history(self, role, response_or_text):
        """Multi-turn 대화 히스토리 관리"""
        if role == "user":
            self.conversation_history.append({"role": "user", "content": response_or_text})
        elif role == "assistant":
            content_blocks = []
            for block in response_or_text.content:
                if block.type == "thinking":
                    content_blocks.append({
                        "type": "thinking",
                        "thinking": block.thinking,
                        "signature": block.signature,
                    })
                elif block.type == "text":
                    content_blocks.append({
                        "type": "text",
                        "text": block.text,
                    })
            self.conversation_history.append({"role": "assistant", "content": content_blocks})

    # ------------------------------------------
    # Step 0: Dynamic Topic Generation
    # ------------------------------------------

    def step_0_generate_topic(self):
        """
        0단계: 동적 토픽 생성
        - 기존 포스트 목록을 Claude에게 보여주고
        - 겹치지 않는 새로운 토픽을 생성하게 함
        - 실패시 fallback pool에서 선택
        """
        print("🎯 [0/7] Generating fresh topic...")

        existing_titles = [p['title'] for p in self.existing_posts]
        existing_titles_str = "\n".join(f"- {t}" for t in existing_titles[-30:])  # 최근 30개

        categories = CATEGORIES[CURRENT_MODE]
        category_str = "\n".join(f"- {k}: {v}" for k, v in categories.items())

        topic_schema = {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "One of the category keys listed"
                },
                "topic_title": {
                    "type": "string",
                    "description": "A specific, engaging blog post title"
                },
                "why_this_topic": {
                    "type": "string",
                    "description": "One sentence on why this topic would attract readers"
                }
            },
            "required": ["category", "topic_title", "why_this_topic"]
        }

        prompt = f"""I need a fresh blog post topic for my English-language blog "Insight Crossroad".

## Available Categories
{category_str}

## Already Published (DO NOT repeat or closely overlap with these)
{existing_titles_str if existing_titles_str else "(No posts yet)"}

## Requirements
- The topic should be something people actually search for
- It should have a specific angle, not just a broad topic (bad: "AI Tools" — good: "Why ChatGPT's Free Tier Is Still Better Than Most Paid AI Tools")
- Avoid generic self-help or obvious advice topics
- The title should promise specific value or a surprising finding
- Pick a category that's UNDERREPRESENTED in the existing posts list above
- Make sure it's clearly different from every title in the existing posts list

Generate one topic."""

        try:
            response = self._call_claude(
                messages=[{"role": "user", "content": prompt}],
                effort="medium",
                max_tokens=1000,
                use_json_output=True,
                json_schema=topic_schema,
            )

            text = self._extract_text(response)
            result = json.loads(text)

            topic = result['topic_title']
            category = result['category']

            # 카테고리 유효성 체크
            valid_categories = list(categories.keys())
            if category not in valid_categories:
                category = random.choice(valid_categories)

            # 중복 체크
            if self.is_duplicate(topic):
                print(f"   ⚠️ Generated topic is duplicate, retrying...")
                return self._topic_fallback()

            print(f"   ✅ Generated: [{category}] {topic}")
            print(f"   💡 Why: {result.get('why_this_topic', 'N/A')}")
            return category, topic

        except Exception as e:
            print(f"   ⚠️ Dynamic topic generation failed: {e}")
            return self._topic_fallback()

    def _topic_fallback(self):
        """동적 생성 실패시 fallback pool에서 중복 아닌 것 선택"""
        print("   ↳ Falling back to topic pool...")
        pool = FALLBACK_TOPICS.get(CURRENT_MODE, {})

        # 모든 토픽을 셔플해서 중복 아닌 첫 번째를 선택
        all_topics = []
        for cat, topics in pool.items():
            for t in topics:
                all_topics.append((cat, t))

        random.shuffle(all_topics)

        for cat, topic in all_topics:
            if not self.is_duplicate(topic):
                print(f"   ✅ Fallback: [{cat}] {topic}")
                return cat, topic

        # 전부 중복이면 그냥 랜덤 (최악의 경우)
        cat, topic = random.choice(all_topics)
        print(f"   ⚠️ All fallbacks are duplicates, using: {topic}")
        return cat, topic

    # ------------------------------------------
    # Pipeline stages
    # ------------------------------------------

    def step_1_plan(self, topic):
        """1단계: 기획 (effort: medium)"""
        print(f"🧠 [1/7] Planning article angle...")

        plan_schema = {
            "type": "object",
            "properties": {
                "working_title": {
                    "type": "string",
                    "description": "SEO-friendly title that promises specific value"
                },
                "hook_concept": {
                    "type": "string",
                    "description": "One sentence describing the opening approach"
                },
                "contrarian_angle": {
                    "type": "string",
                    "description": "What conventional wisdom are we challenging?"
                },
                "sections": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "header": {"type": "string"},
                            "key_point": {"type": "string"},
                            "research_element": {"type": "string"}
                        },
                        "required": ["header", "key_point", "research_element"]
                    },
                    "description": "3-5 sections that flow naturally"
                },
                "honest_caveat": {
                    "type": "string",
                    "description": "One limitation or this-won't-work-if to include"
                },
                "image_queries": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "2 specific visual concepts for Unsplash search"
                }
            },
            "required": ["working_title", "hook_concept", "contrarian_angle", "sections", "honest_caveat", "image_queries"]
        }

        prompt = f"""I need to write about: "{topic}"

Think through:
1. What's the conventional wisdom on this topic that might be wrong or incomplete?
2. What angle would make this actually worth reading vs the 50 other articles on this?
3. What specific, concrete information can I include that most articles skip?

Create a plan that:
- Opens with something that makes the reader think "huh, I didn't know that"
- Has 3-5 sections that build on each other (not just random subtopics)
- Includes a moment where you flip the reader's expectation
- Ends with specific next steps, not "go forth and conquer" nonsense
"""

        try:
            self._append_to_history("user", prompt)

            response = self._call_claude(
                messages=self.conversation_history,
                effort="medium",
                max_tokens=2000,
                use_json_output=True,
                json_schema=plan_schema,
            )

            self._append_to_history("assistant", response)
            text = self._extract_text(response)
            plan = json.loads(text)

            if len(plan.get("image_queries", [])) < 2:
                plan["image_queries"] = ["workspace productivity", "research notes"]

            return plan

        except Exception as e:
            print(f"⚠️ Planning failed: {e}")
            return self._plan_fallback(topic)

    def _plan_fallback(self, topic):
        """Structured output 실패시 fallback"""
        print("   ↳ Trying fallback planning...")
        self.conversation_history = []

        prompt = f"""I need to write about: "{topic}"

Return a JSON object with these fields:
- working_title (string)
- hook_concept (string)
- contrarian_angle (string)
- sections (array of objects with header, key_point, research_element)
- honest_caveat (string)
- image_queries (array of 2 strings)

JSON only, no markdown formatting:"""

        self._append_to_history("user", prompt)

        try:
            response = self._call_claude(
                messages=self.conversation_history,
                effort="medium",
                max_tokens=2000,
            )

            self._append_to_history("assistant", response)
            text = self._extract_text(response)

            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            return json.loads(text.strip())

        except Exception as e:
            print(f"⚠️ Fallback planning also failed: {e}")
            return None

    def step_2_write_draft(self, plan):
        """2단계: 초안 작성 (effort: high)"""
        print(f"✍️ [2/7] Writing first draft...")
        print(f"   📐 Format: {self.writing_format['name']}")
        print(f"   🎭 Tone: {self.tone['name']}")
        print(f"   👤 Persona: {self.persona['name']}")

        quirks_str = "\n".join(f"- {q}" for q in self.quirks)

        prompt = f"""Based on our plan:
- Title: {plan['working_title']}
- Angle: {plan['contrarian_angle']}
- Sections: {json.dumps(plan['sections'], indent=2)}
- Caveat: {plan['honest_caveat']}

Write the full blog post in HTML format.

## FORMAT FOR THIS ARTICLE
{self.writing_format['instruction']}

## TONE FOR THIS ARTICLE
{self.tone['instruction']}

## HUMAN TOUCHES (incorporate these naturally - don't force them)
{quirks_str}

## Technical requirements
- 1500-2000 words
- Use <h2> for main sections, <h3> for subsections
- Use <p> for paragraphs
- Place exactly 2 image markers: [IMAGE: {plan['image_queries'][0]}] and [IMAGE: {plan['image_queries'][1]}]
- Output raw HTML only. No <html>, <head>, <body> tags. No markdown code blocks.

## Content requirements
- NO fake experiences, stats, emails, names, or credentials
- NO generic filler paragraphs
- Every section must add concrete value"""

        self._append_to_history("user", prompt)

        try:
            response = self._call_claude(
                messages=self.conversation_history,
                effort="high",
                max_tokens=8000,
            )

            self._append_to_history("assistant", response)
            draft = self._extract_text(response)
            return self.validator.sanitize_html(draft)

        except Exception as e:
            print(f"⚠️ Writing failed: {e}")
            return None

    def step_3_self_critique(self, draft):
        """3단계: 자기 비평 + 개선 (effort: max)"""
        print(f"🔍 [3/7] Self-critique and improvement...")

        critique_and_fix_prompt = f"""Review the draft you just wrote, then produce an improved version.

## Critique Checklist (be ruthless)
1. AI PHRASES: Any "dive deep", "comprehensive", "landscape", "embark", "leverage", "harness", "in today's", "game-changer", "it's worth noting", "without further ado", "in the realm of"?
2. FABRICATION: Any invented stats, fake experiences, made-up sources?
3. FLUFF: Any paragraphs that don't add real information?
4. VALUE: Does every section teach something specific and new?
5. TONE CHECK: Does it match the intended tone ({self.tone['name']})? Or did it slip into generic AI voice?
6. FORMAT CHECK: Does it follow the intended format ({self.writing_format['name']})? Or did it default to the same old template?
7. PATTERN DETECTION: Does the opening follow the "I went down a rabbit hole" pattern? If so, CHANGE IT.
8. SENTENCE VARIETY: Are most sentences the same length? Mix it up aggressively.
9. CLAIMS: Anything stated as fact that should be framed more carefully?

## Your Task
Rewrite the COMPLETE article fixing all problems.
Output ONLY the improved HTML. No commentary. No markdown code blocks."""

        self._append_to_history("user", critique_and_fix_prompt)

        try:
            response = self._call_claude(
                messages=self.conversation_history,
                effort="max",
                max_tokens=8000,
            )

            self._append_to_history("assistant", response)
            improved = self._extract_text(response)
            result = self.validator.sanitize_html(improved)

            if len(result) < 500:
                print("   ⚠️ Improved version too short, using original draft")
                return draft

            return result

        except Exception as e:
            print(f"⚠️ Critique failed: {e}")
            return draft

    def step_4_humanize(self, content):
        """4단계: 사람다움 후처리 (effort: high)"""
        print(f"🧑 [4/7] Humanizing pass...")

        humanize_prompt = f"""You are a human editor, not a writer. Your job is to make small edits so this reads less like AI output and more like a real person's blog post.

## What to do:
- Vary sentence length MORE. Mix 5-word sentences with 25-word ones.
- Break up any paragraph that's more than 4 sentences.
- If the opening is generic, cut it or replace with something specific.
- Swap a few "proper" words for casual ones ("utilize"→"use", "purchase"→"buy")
- Add 1-2 sentence fragments. Not every sentence needs a verb.
- Make sure transitions between sections aren't all smooth.
- If every section is about the same length, make one shorter or longer.
- Remove any sentence that's just restating what was already said.

## What NOT to do:
- Don't change the facts or claims
- Don't add fake personal experiences
- Don't add emojis or exclamation marks
- Don't change the overall structure
- Don't remove the [IMAGE: ...] markers

## Input article:
{content}

## Output:
The edited HTML article only. No commentary. No markdown code blocks."""

        try:
            response = self._call_claude(
                messages=[{"role": "user", "content": humanize_prompt}],
                effort="high",
                max_tokens=8000,
            )

            result = self._extract_text(response)
            result = self.validator.sanitize_html(result)

            if len(result) < 500:
                print("   ⚠️ Humanized version too short, using previous version")
                return content

            return result

        except Exception as e:
            print(f"⚠️ Humanize failed: {e}")
            return content

    def step_5_add_images(self, content):
        """5단계: Unsplash 이미지 삽입"""
        print(f"🎨 [5/7] Adding images...")

        if not self.unsplash_key:
            print("   ⚠️ No Unsplash key — skipping images")
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
                        'orientation': 'landscape',
                    },
                    timeout=10,
                )

                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list):
                        data = data[0]

                    img_url = data['urls']['regular']
                    user_name = data['user']['name']
                    user_link = f"https://unsplash.com/@{data['user']['username']}?utm_source=insightcrossroad&utm_medium=referral"
                    unsplash_link = "https://unsplash.com/?utm_source=insightcrossroad&utm_medium=referral"

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
                    print(f"   ⚠️ Unsplash API returned {response.status_code}")
                    content = content.replace(marker, '', 1)

            except Exception as e:
                print(f"   ⚠️ Image fetch failed: {e}")
                content = content.replace(marker, '', 1)

        return content

    def step_6_add_internal_links(self, content, title, labels):
        """
        6단계: 내부 링크 삽입
        - 관련 포스트를 찾아서 글 하단에 "You might also like" 섹션 추가
        - SEO에 중요한 내부 링크 구조 형성
        """
        print(f"🔗 [6/7] Adding internal links...")

        related = self.find_related_posts(title, labels)

        if not related:
            print("   ℹ️ No related posts found — skipping")
            return content

        links_html = '\n<div style="margin-top: 3rem; padding: 1.5rem; background: #f9fafb; border-radius: 12px; border: 1px solid #e5e7eb;">\n'
        links_html += '<h3 style="margin-top: 0; color: #374151; font-size: 1.125rem;">You might also find these useful</h3>\n<ul style="padding-left: 1.25rem;">\n'

        for post in related:
            post_title = post['title']
            post_url = post['url']
            links_html += f'<li style="margin-bottom: 0.5rem;"><a href="{post_url}" style="color: #2563eb; text-decoration: none;">{post_title}</a></li>\n'

        links_html += '</ul>\n</div>'

        print(f"   ✅ Added {len(related)} internal links")
        return content + links_html

    def step_7_publish(self, title, content, category):
        """7단계: Blogger 발행"""
        print(f"🚀 [7/7] Publishing to Blogger...")

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
        width: 100%; border-collapse: collapse; margin: 2rem 0; font-size: 1rem;
    }
    .post-body th {
        background: #f1f5f9; font-weight: 600; text-align: left;
        padding: 1rem; border-bottom: 2px solid #e2e8f0;
    }
    .post-body td {
        padding: 1rem; border-bottom: 1px solid #f1f5f9;
    }
    .disclaimer {
        background: #fef2f2; padding: 1.25rem; border-radius: 8px;
        font-size: 0.875rem; color: #991b1b; margin-top: 2rem;
        border: 1px solid #fecaca;
    }
</style>
'''

        disclaimer = ''
        if CURRENT_MODE == 'MONEY':
            disclaimer = '''
<div class="disclaimer">
    <strong>Disclosure:</strong> Some links in this article may be affiliate links,
    which help support this site at no extra cost to you.
    I only recommend tools that came up well in my research.
</div>
'''

        final_html = f"{css}<div class='post-body'>{content}{disclaimer}</div>"

        tags = [category.replace('_', ' ')]
        tag_map = {
            'APPROVAL': ['Guides', 'How-To', 'Research'],
            'MONEY': ['Reviews', 'Comparisons', 'Tools'],
        }
        tags.extend(random.sample(tag_map.get(CURRENT_MODE, []), 2))

        body = {
            'title': title,
            'content': final_html,
            'labels': list(set(tags)),
        }

        try:
            service = self._get_blogger_service()
            result = service.posts().insert(
                blogId=self.blog_id,
                body=body,
                isDraft=True,
            ).execute()

            print(f"✅ Draft created!")
            print(f"   📝 Title: {title}")
            print(f"   🔗 URL: {result.get('url', 'N/A')}")
            print(f"   🏷️ Tags: {tags}")
            return result

        except Exception as e:
            print(f"❌ Publish failed: {e}")
            return None

    # ------------------------------------------
    # Main
    # ------------------------------------------

    def run(self):
        """메인 파이프라인"""
        print(f"""
╔═══════════════════════════════════════════════════════════════════╗
║  Pro Blog Bot v4.0.1 - Anti-Pattern Edition                      ║
║  Mode: {CURRENT_MODE:10s} | Model: {CLAUDE_MODEL:28s}   ║
║  Persona: {self.persona['name']:12s} | Format: {self.writing_format['name']:15s}  ║
║  Tone: {self.tone['name']:15s}                                       ║
║  Features: Dedup · Dynamic Topics · Persona Rotation · Links     ║
╚═══════════════════════════════════════════════════════════════════╝
""")

        # Step 0: Fetch existing posts + generate topic
        self.fetch_existing_posts()
        category, topic = self.step_0_generate_topic()

        print(f"\n📁 Category: {category}")
        print(f"📝 Topic: {topic}")
        print("-" * 60)

        self.conversation_history = []

        # Step 1: Plan
        plan = self.step_1_plan(topic)
        if not plan:
            print("❌ Planning failed — aborting")
            return

        title = plan['working_title']

        # Final duplicate check on the planned title
        if self.is_duplicate(title):
            print(f"⚠️ Planned title is duplicate: {title}")
            print("   Adjusting title...")
            title = f"{title} — A Fresh Look"

        print(f"   📌 Title: {title}")
        print(f"   💡 Angle: {plan['contrarian_angle']}")

        # Step 2: Write
        draft = self.step_2_write_draft(plan)
        if not draft:
            print("❌ Draft failed — aborting")
            return

        # Step 3: Critique + Improve
        improved = self.step_3_self_critique(draft)
        if not improved:
            improved = draft

        # Step 4: Humanize
        humanized = self.step_4_humanize(improved)

        # Step 5: Images
        with_images = self.step_5_add_images(humanized)

        # Step 6: Internal links
        tags = [category.replace('_', ' ')]
        tag_map = {
            'APPROVAL': ['Guides', 'How-To', 'Research'],
            'MONEY': ['Reviews', 'Comparisons', 'Tools'],
        }
        tags.extend(random.sample(tag_map.get(CURRENT_MODE, []), 2))

        final_content = self.step_6_add_internal_links(with_images, title, tags)

        # Step 7: Publish
        self.step_7_publish(title, final_content, category)

        print("\n✅ Pipeline complete!")


if __name__ == "__main__":
    bot = ProBlogBotV4()
    bot.run()
