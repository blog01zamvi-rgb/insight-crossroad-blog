#!/usr/bin/env python3
"""
Pro Blog Bot v3.0 - Opus 4.6 Optimized
=======================================
Changelog from v2.1:
  - Model: claude-opus-4-6 (simplified ID, no date suffix)
  - Adaptive thinking: Claude decides when/how much to reason
  - Effort parameter per stage (medium→plan, high→write, max→critique)
  - Structured JSON output via output_config.format for reliable parsing
  - 128K max output support
  - Improved prompts leveraging deeper reasoning
  - Proper thinking block handling in multi-turn conversations
  - Removed deprecated: budget_tokens, interleaved-thinking beta header
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

# Opus 4.6: simplified model ID (no date suffix)
# Fallback: claude-opus-4-5-20251101 or claude-sonnet-4-5-20250929
CLAUDE_MODEL = os.getenv('CLAUDE_MODEL', 'claude-opus-4-6')

# ==========================================
# 🎭 PERSONA - Research-based Curator
# ==========================================

SYSTEM_PROMPT = """You are a curious blogger who researches topics and summarizes findings for readers. You're NOT an expert and you don't pretend to be. You don't claim personal experience you don't have. Instead, you spend time looking into topics, comparing different sources and opinions, and presenting what you found in a clear, organized way.

Your value is in doing the research legwork so readers don't have to. You're like a friend who says "I looked into this for you, here's what I found."

## Your Writing Voice
- Frame as research: "I looked into this...", "From what I found...", "Based on what people are saying..."
- Cite general sources naturally: "Reddit users seem to agree...", "A lot of reviews mention...", "The common advice is..."
- Add your take: "Honestly, this surprised me...", "I'm not sure I buy this, but...", "This makes sense to me because..."
- Acknowledge gaps: "I couldn't find a clear answer on...", "Opinions are split on this..."
- Be practical: Focus on actionable takeaways, not fluff
- Show your work: Mention what you compared, what sources you looked at (generally)
- Have opinions: After presenting findings, share what YOU think makes most sense
- Admit uncertainty: "Take this with a grain of salt", "Your situation might be different"

## ABSOLUTE RULES

### 1. NO FABRICATION
- NEVER invent statistics or specific numbers
- NEVER claim personal experience you don't have
- NEVER make up quotes, names, emails, credentials, or sources
- Frame everything as research: "From what I found...", "People seem to say..."
- It's OK to say "I couldn't find reliable data on this"

### 2. NO AI-SOUNDING PHRASES
Never use these words/phrases:
"In today's fast-paced world", "comprehensive guide", "ultimate guide", "Let's dive in", "dive deep", "delve", "It's important to note that", "In conclusion", "The landscape of", "Navigate the complexities", "Game-changer", "Revolutionize", "Seamlessly", "Effortlessly", "Robust", "Leverage", "Embark on a journey", "Without further ado", "harness the power", "at the end of the day", "it goes without saying"

### 3. PROVIDE REAL VALUE
- Don't state the obvious
- Include specific, actionable information
- Compare things concretely, not vaguely
- If there's no clear answer, say so
- Every paragraph must add something new

### 4. NATURAL STRUCTURE
- Vary your format - not every post needs the same skeleton
- Not everything needs bullet points
- Vary paragraph lengths
- Write like you're explaining to a friend
- Headers should be useful, not clever
"""

# ==========================================
# ✏️ WRITING FORMAT VARIATIONS
# 매번 다른 글 구조를 사용해서 패턴 반복을 깨뜨림
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
]

# ==========================================
# 🎭 TONE VARIATIONS
# 같은 사람이라도 글마다 기분이 다름
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
        "instruction": "Go deeper than usual into the details on this topic. Highlight counterintuitive findings and interesting specifics that most surface-level articles miss. Get a little nerdy about the numbers or mechanics. Show genuine interest in the nuances.",
    },
    {
        "name": "no_nonsense",
        "instruction": "Zero patience for marketing speak or vague claims today. When sources are vague, call it out. When you can't find real data, say so plainly. Respect the reader's time by being extremely efficient with words.",
    },
    {
        "name": "laid_back",
        "instruction": "Relaxed, unhurried tone. Take your time. Not everything needs a strong opinion - sometimes 'eh, it depends' is the honest answer. Use casual language. It's okay to say 'I don't really care about this part but here's what I found anyway.'",
    },
]

# ==========================================
# 🧬 HUMAN QUIRKS
# AI 글에 부족한 "불완전한 인간다움"을 주입하는 지시
# ==========================================

HUMAN_QUIRKS = [
    "Include exactly one parenthetical aside that's slightly off-topic but relatable.",
    "Start one paragraph with 'Look,' or 'Here's the thing' or 'Okay so' - something conversational.",
    "Have one sentence that's just 2-5 words. Fragment is fine.",
    "Mention one aspect of this topic that seems under-discussed.",
    "Include a brief moment of self-correction: 'Actually, wait — ' or 'Though now that I think about it...'",
    "Use one slightly informal word choice: 'kinda', 'tbh', 'nope', 'meh', 'sorta'",
    "Have one place where you visibly reconsider your position mid-paragraph.",
    "Include a sentence that starts with 'The weird thing is...' or 'What stands out here is...'",
    "End one section a bit abruptly, like there's not much more to say on that point.",
    "Ask the reader a rhetorical question somewhere - just one.",
]

# ==========================================
# 📝 TOPIC POOLS
# ==========================================

TOPICS = {
    'APPROVAL': {
        'Productivity': [
            'Pomodoro vs Time Blocking: I Compared What Actually Works',
            'Why Do Some People Swear by 5AM Routines? I Looked Into It',
            'Notion vs Obsidian: What Reddit Actually Says',
            'The Real Reason Most To-Do Lists Fail (According to Research)',
            'I Read 20 Articles on Deep Work - Here Are the Parts That Actually Matter',
            'Digital Minimalism: What Happens When You Actually Try It',
            'The Second Brain Method: Overhyped or Actually Useful?',
            'Why Most Habit Trackers Get Abandoned (And What Might Work Instead)',
        ],
        'Wellness': [
            'Standing Desks: Hype or Legit? What the Studies Say',
            'I Compared 5 Sleep Tracking Methods - Here\'s What I Found',
            'What Actually Helps With Burnout (And What Doesn\'t)',
            'Blue Light Glasses: I Looked Into Whether They\'re Worth It',
            'The Science Behind Why Walking Meetings Might Work',
            'Cold Showers for Health: What Does the Research Actually Show?',
            'Meditation Apps Compared: Do Any of Them Actually Work?',
            'Ergonomic Keyboards: Worth the Investment or Marketing Trick?',
        ],
        'Tech_Tips': [
            'Password Managers Compared: What Users Actually Complain About',
            'VPN Services: Cutting Through the Marketing BS',
            'Why Tech People Keep Recommending Linux (And Why You Probably Shouldn\'t Switch)',
            'Cloud Storage Pricing is Confusing - I Broke It Down',
            'Ad Blockers in 2025: What Still Works and What Got Broken',
            'Browser Extensions That Are Actually Worth Installing',
            'Email Providers Beyond Gmail: What Are the Real Options?',
            'Two-Factor Authentication: The Options Ranked by Actual Security',
        ],
        'Learning': [
            'Online Course Completion Rates Are Terrible - Here\'s Why',
            'Spaced Repetition: The Study Method Nobody Talks About',
            'Free Coding Resources: Which Ones Are Actually Good?',
            'Language Learning Apps: What Linguists Think About Them',
            'YouTube vs Paid Courses: When Free is Actually Better',
        ],
    },
    'MONEY': {
        'SaaS_Review': [
            'Asana vs Monday vs ClickUp: What Teams Actually Say After 6 Months',
            'CRM Software: The Hidden Costs Nobody Mentions Upfront',
            'Email Marketing Tools: I Compared Pricing For a 10K List',
            'Project Management Tools: Feature Comparison That Actually Matters',
            'Why Some Companies Ditch Slack for Discord (And Vice Versa)',
            'Note-Taking Apps for Teams: Beyond the Feature Lists',
        ],
        'Hosting': [
            'Cheap Web Hosting: What You Actually Get for $3/Month',
            'WordPress Hosting Compared: Shared vs Managed vs VPS',
            'The Real Cost of "Unlimited" Hosting Plans',
            'Website Builders vs Custom Sites: When Each Makes Sense',
            'CDN Pricing Explained: Do Small Sites Even Need One?',
        ],
        'Finance': [
            'Budgeting Apps: Which Ones People Actually Keep Using',
            'Investing Apps for Beginners: Fees Compared Simply',
            'Credit Card Rewards: When They\'re Worth It vs When They\'re Not',
            'Side Hustle Tax Stuff: What I Found Out The Hard Way (Research Edition)',
            'Buy Now Pay Later Services: The Fine Print Nobody Reads',
            'High-Yield Savings Accounts: Are They Really Worth Switching For?',
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
        # Remove markdown code blocks
        content = re.sub(r'^```html?\s*\n?', '', content, flags=re.IGNORECASE)
        content = re.sub(r'\n?```\s*$', '', content)
        # Also catch mid-content code blocks
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

class ProBlogBotV3:
    """Opus 4.6 최적화 블로그 봇"""

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
        self.writing_format = random.choice(WRITING_FORMATS)
        self.tone = random.choice(TONE_MODIFIERS)
        self.quirks = random.sample(HUMAN_QUIRKS, 3)  # 3개만 선택

    # ------------------------------------------
    # API call helpers
    # ------------------------------------------

    def _call_claude(self, messages, effort="high", max_tokens=4096, use_json_output=False, json_schema=None):
        """
        Opus 4.6 API 호출 - adaptive thinking + effort parameter 활용

        Args:
            messages: 대화 히스토리
            effort: "low" | "medium" | "high" | "max" (4.6 신규)
            max_tokens: 최대 출력 토큰
            use_json_output: JSON structured output 사용 여부
            json_schema: JSON 스키마 (use_json_output=True일 때)
        """
        kwargs = {
            "model": CLAUDE_MODEL,
            "max_tokens": max_tokens,
            "system": SYSTEM_PROMPT,
            "messages": messages,
            # Opus 4.6: adaptive thinking (replaces type:"enabled" + budget_tokens)
            "thinking": {"type": "adaptive"},
            # Opus 4.6: effort is GA (no beta header needed)
            "output_config": {"effort": effort},
        }

        # Opus 4.6: structured JSON output via output_config.format
        if use_json_output and json_schema:
            kwargs["output_config"]["format"] = {
                "type": "json_schema",
                "schema": json_schema,
            }

        response = self.claude.messages.create(**kwargs)
        return response

    def _extract_text(self, response):
        """
        Adaptive thinking 응답에서 텍스트만 추출.
        response.content에 thinking/text 블록이 섞여 있을 수 있음.
        """
        text_parts = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
        return "\n".join(text_parts)

    def _append_to_history(self, role, response_or_text):
        """
        Multi-turn 대화 히스토리 관리.
        Opus 4.6 adaptive thinking에서는 thinking 블록을
        그대로 다시 보내야 reasoning flow가 유지됨.
        """
        if role == "user":
            self.conversation_history.append({"role": "user", "content": response_or_text})
        elif role == "assistant":
            # response 객체의 전체 content를 보존 (thinking blocks 포함)
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
    # Pipeline stages
    # ------------------------------------------

    def step_1_plan(self, topic):
        """
        1단계: 기획 (effort: medium)
        - medium effort로 빠르게 구조 잡기
        - Structured JSON output으로 안정적 파싱
        """
        print(f"🧠 [1/6] Planning article angle...")

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
                effort="medium",  # Planning doesn't need max effort
                max_tokens=2000,
                use_json_output=True,
                json_schema=plan_schema,
            )

            self._append_to_history("assistant", response)
            text = self._extract_text(response)
            plan = json.loads(text)

            # Ensure image_queries has exactly 2 items
            if len(plan.get("image_queries", [])) < 2:
                plan["image_queries"] = ["workspace productivity", "research notes"]

            return plan

        except Exception as e:
            print(f"⚠️ Planning failed: {e}")
            # Fallback: try without structured output
            return self._plan_fallback(topic)

    def _plan_fallback(self, topic):
        """Structured output 실패시 일반 JSON 파싱으로 fallback"""
        print("   ↳ Trying fallback planning...")
        self.conversation_history = []  # Reset

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

            # Try to extract JSON
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            return json.loads(text.strip())

        except Exception as e:
            print(f"⚠️ Fallback planning also failed: {e}")
            return None

    def step_2_write_draft(self, plan):
        """
        2단계: 초안 작성 (effort: high)
        - 매 실행마다 다른 포맷/톤/퀴크 조합 적용
        """
        print(f"✍️ [2/6] Writing first draft...")
        print(f"   📐 Format: {self.writing_format['name']}")
        print(f"   🎭 Tone: {self.tone['name']}")

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
- Frame as research/curation, not personal expertise
- Include specific comparisons and concrete details
- NO fake experiences, stats, emails, names, or credentials
- NO generic filler paragraphs"""

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
        """
        3단계: 자기 비평 + 개선 (effort: max)
        - Opus 4.6의 'max' effort로 가장 깊은 분석
        - 포맷/톤 일관성도 체크
        """
        print(f"🔍 [3/6] Self-critique and improvement (max effort)...")

        critique_and_fix_prompt = f"""Review the draft you just wrote, then produce an improved version.

## Critique Checklist (be ruthless)
1. AI PHRASES: Any "dive deep", "comprehensive", "landscape", "embark", "leverage", "harness", "in today's", "game-changer", "it's worth noting", "without further ado"?
2. FABRICATION: Any invented stats, fake experiences, made-up sources, fake emails or names?
3. FLUFF: Any paragraphs that don't add real information? Obvious statements?
4. VALUE: Does every section teach something specific and new?
5. TONE CHECK: Does it match the intended tone ({self.tone['name']})? Or did it slip into generic AI voice?
6. FORMAT CHECK: Does it follow the intended format ({self.writing_format['name']})? Or did it default to the same old intro-body-conclusion template?
7. PATTERN DETECTION: Read the article as if you're a skeptical reader. Does anything feel template-y, repetitive, or like "AI wrote this"?
8. CLAIMS: Anything stated as fact that should be framed as "from what I found"?

## Your Task
Rewrite the COMPLETE article fixing all problems. Make sure it genuinely follows the {self.writing_format['name']} format and {self.tone['name']} tone throughout.

Output ONLY the improved HTML. No commentary, no issue list, no markdown code blocks. Just the final clean HTML article."""

        self._append_to_history("user", critique_and_fix_prompt)

        try:
            response = self._call_claude(
                messages=self.conversation_history,
                effort="max",  # 4.6 new: deepest reasoning for quality check
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
        """
        4단계: 사람다움 후처리 (effort: high)
        - 별도 대화로 "편집자" 역할을 수행
        - 글의 내용은 유지하면서 AI 냄새를 제거
        """
        print(f"🧑 [4/6] Humanizing pass...")

        # 새 대화 (기존 히스토리와 분리 - 신선한 눈으로 봐야 함)
        humanize_prompt = f"""You are a human editor, not a writer. Your job is to take this article and make small edits so it reads less like AI output and more like a real person's blog post.

## What to do:
- Vary sentence length MORE. Mix 5-word sentences with 25-word ones. AI tends to keep everything medium-length.
- Break up any paragraph that's more than 4 sentences.
- If the opening sentence is generic or throat-clearing, cut it or replace it with something specific.
- Swap a few "proper" words for casual ones (e.g. "utilize" → "use", "purchase" → "buy", "numerous" → "a lot of")
- Add 1-2 sentence fragments. Not every sentence needs a verb.
- Make sure transitions between sections aren't all smooth. Real writing sometimes jumps.
- If every section is about the same length, make one noticeably shorter or longer.
- Remove any sentence that's just restating what was already said in different words.

## What NOT to do:
- Don't change the facts or claims
- Don't add fake personal experiences
- Don't make it worse or less informative
- Don't add emojis or excessive exclamation marks
- Don't change the overall structure or format
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
        print(f"🎨 [5/6] Adding images...")

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

    def step_6_publish(self, title, content, category):
        """6단계: Blogger 발행"""
        print(f"🚀 [6/6] Publishing to Blogger...")

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

    # ------------------------------------------
    # Main
    # ------------------------------------------

    def run(self):
        """메인 파이프라인"""
        print(f"""
╔═══════════════════════════════════════════════════════════════╗
║  Pro Blog Bot v3.1 - Opus 4.6 + Human Touch Edition         ║
║  Mode: {CURRENT_MODE:10s} | Model: {CLAUDE_MODEL:28s}   ║
║  Features: Adaptive Thinking · Effort Scaling · Humanizer    ║
╠═══════════════════════════════════════════════════════════════╣
║  Format: {self.writing_format['name']:15s} | Tone: {self.tone['name']:20s} ║
╚═══════════════════════════════════════════════════════════════╝
""")

        topic_pool = TOPICS[CURRENT_MODE]
        category = random.choice(list(topic_pool.keys()))
        topic = random.choice(topic_pool[category])

        print(f"📁 Category: {category}")
        print(f"📝 Topic: {topic}")
        print("-" * 60)

        self.conversation_history = []

        # Step 1: Plan (medium effort - fast)
        plan = self.step_1_plan(topic)
        if not plan:
            print("❌ Planning failed - aborting")
            return

        print(f"   📌 Title: {plan['working_title']}")
        print(f"   💡 Angle: {plan['contrarian_angle']}")

        # Step 2: Write (high effort - quality + format/tone)
        draft = self.step_2_write_draft(plan)
        if not draft:
            print("❌ Draft failed - aborting")
            return

        # Step 3: Critique + Improve (max effort - deepest reasoning)
        improved = self.step_3_self_critique(draft)
        if not improved:
            improved = draft

        # Step 4: Humanize (high effort - fresh perspective)
        humanized = self.step_4_humanize(improved)

        # Step 5: Images
        final_content = self.step_5_add_images(humanized)

        # Step 6: Publish
        self.step_6_publish(
            plan['working_title'],
            final_content,
            category,
        )

        print("\n✅ Pipeline complete!")


if __name__ == "__main__":
    bot = ProBlogBotV3()
    bot.run()
