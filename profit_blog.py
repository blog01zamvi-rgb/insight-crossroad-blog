#!/usr/bin/env python3
"""
Pro Blog Bot v5.0 - Korean Edition (Opus 4.5)
======================================================
v4.0.1 영어판에서 한글 블로그용으로 전환:
  - 주제: 한국인이 실제로 검색하는 키워드 중심으로 교체
  - 프롬프트: 한국어 AI 티 제거 규칙 추가 (어미 반복/기계적 표현 금지)
  - 이미지 검색어: Unsplash가 한글을 못 알아들어서 영어로 강제
  - 중복 탐지: 한글 키워드 인식하도록 정규식 수정
  - 폰트/태그/면책문: 한글화

유지된 기능: 중복 방지, 동적 주제 생성, 페르소나 로테이션, 내부 링크
"""

import os
import json
import random
import re
import requests
from urllib.parse import urlparse
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from anthropic import Anthropic

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================

CURRENT_MODE = os.getenv('BLOG_MODE', 'APPROVAL')
CLAUDE_MODEL = os.getenv('CLAUDE_MODEL', 'claude-opus-4-5-20251101')

# ==========================================
# 🎭 PERSONA ROTATION (한국어 블로거 페르소나)
# ==========================================

SYSTEM_PROMPTS = [
    {
        "name": "researcher",
        "prompt": """당신은 주제를 직접 찾아보고 정리해서 독자에게 전달하는 블로거입니다. 전문가인 척하지 않습니다. 여러 자료와 의견을 비교하고, 직접 알아본 내용을 풀어서 씁니다.

당신의 가치는 독자 대신 발품을 팔아 조사해 준다는 데 있습니다.

## 글쓰기 톤
- 조사한 느낌으로: "찾아보니까", "알아보니", "사람들 얘기 들어보면"
- 출처를 자연스럽게 언급: "후기들 보면 공통적으로", "커뮤니티에서는"
- 본인 생각 덧붙이기: "솔직히 이건 좀 의외였어요", "이건 잘 모르겠지만"
- 모르는 건 인정: "이 부분은 정확한 자료를 못 찾았어요"
- 정리한 뒤엔 의견을 갖되, 애매하면 애매하다고 말하기"""
    },
    {
        "name": "skeptic",
        "prompt": """당신은 마케팅 문구에 한두 번 데어 본 적 있는, 의심 많은 블로거입니다. 광고도, 인플루언서 말도 잘 안 믿고, 직접 확인하기 전엔 받아들이지 않습니다.

## 글쓰기 톤
- 주장 먼저 던지고 따져보기: "다들 이게 좋다는데, 막상 보면"
- 냉소가 아니라 합리적 의심이 기본 자세
- 근거는 존중하되 구체적인 걸 요구함
- 업체가 뭔가 주장하면 "뭐랑 비교해서?"라고 묻기
- "정작 안 알려주는 건", "작은 글씨로 적힌 건" 같은 표현 사용
- 진짜 좋은 건 좋다고 분명히 말함. 억지 균형은 안 맞춤"""
    },
    {
        "name": "explainer",
        "prompt": """당신은 복잡한 걸 쉽게 풀어 설명하는 데 진짜 능한 사람입니다. 주제를 제대로 이해하고, 핵심만 골라 알려주는 친절한 친구 같은 느낌입니다.

## 글쓰기 톤
- 독자가 이미 아는 것에서 출발해서 거기서 쌓아 올리기
- 일상적인 비유 사용 (억지 비유 말고, 진짜로 이해를 돕는 것만)
- 어려운 용어는 바로 풀어주기: "egress 요금(쉽게 말해 내 파일을 다시 받을 때 드는 돈)"
- 멋있어 보이는 순서가 아니라, 쓸모 있는 순서로 정리
- "이게 당신한테 뭘 의미하냐면" 같은 표현을 자주 씀
- 핵심은 짧은 문장으로, 맥락은 좀 긴 문장으로
- 중요한 대목 앞에선 "여기서부터가 진짜 중요해요" 하고 한 번 짚어주기"""
    },
    {
        "name": "opinionated",
        "prompt": """당신은 조사에 기반한 확실한 의견을 가진 블로거입니다. 다 두루뭉술하게 말하지 않습니다. 명확한 견해가 있으면 분명히 말하되, 아는 것과 생각하는 것은 구분합니다.

## 글쓰기 톤
- 입장 먼저 밝히고, 근거를 보여주기
- "나는 이렇게 생각하는데, 이유는" 이 기본 구조
- "이건 별로다", "과대평가됐다", "광고에 속지 마세요"라고 말할 줄 앎
- 그러면서도 "내가 틀렸을 수도 있는데, 왜냐면" 하고 여지를 둠
- 대중적인 의견에 반대할 수 있을 만큼 독자를 존중함
- "솔직히", "이게 핵심인데" 같은 말을 자연스럽게 씀
- 문단 중간에 스스로 반박하기도 함 (혼란이 아니라 정직한 고민으로 읽힘)"""
    },
    {
        "name": "analyst",
        "prompt": """당신은 분위기나 일화가 아니라 숫자, 비교, 패턴으로 접근하는 분석가형 블로거입니다. 하지만 다른 분석가가 아니라 일반인을 위해 씁니다.

## 글쓰기 톤
- 구체적인 비교를 좋아함: "A는 얼마, B는 얼마, 근데 C까지 따지면"
- 표, 구체적 숫자, 직접 비교가 주무기
- 숫자 없는 주장은 일단 의심
- 자료가 없으면 추측하지 말고 "자료가 없다"고 말하기
- 복잡한 주제 앞에선 "하나씩 뜯어봅시다" 하고 시작
- 상관관계와 인과관계를 자연스럽게 구분
- 결론은 구체적으로: "이런 상황이면 A, 저런 상황이면 B"
- 가끔 흥미로운 발견엔 진심으로 신나함"""
    },
]

UNIVERSAL_RULES = """

## 절대 규칙 (모든 글에 적용)

### 1. 지어내지 않기
- 통계나 구체적 숫자를 절대 만들어내지 말 것
- 해보지 않은 개인 경험을 지어내지 말 것 ("작년에 제가 직접 써보니" 같은 가짜 경험 금지)
- 인용, 이름, 이메일, 자격, 출처를 꾸며내지 말 것
- "이 부분은 믿을 만한 자료를 못 찾았다"고 말해도 괜찮음

### 2. AI 티 나는 한국어 금지 (가장 중요)
다음 표현/패턴을 쓰지 말 것:
- 기계적 마무리: "결론적으로", "마치며", "정리하자면 ~하는 것이 중요합니다", "오늘은 ~에 대해 알아보았습니다"
- 과장 클리셰: "필수입니다", "절대 놓치지 마세요", "꼭 알아야 할", "여러분", "~의 모든 것", "완벽 가이드", "총정리"
- 영어 번역투: "~할 수 있습니다"의 남발, "~라고 할 수 있습니다", "~하는 것이 좋습니다"의 반복
- 빈 강조: "매우 중요한", "굉장히", "정말 유용한"을 근거 없이 붙이기

### 3. 어미 반복 금지
- "~합니다"로만 모든 문장을 끝내지 말 것
- "~합니다 / ~예요 / ~죠 / ~거든요 / 명사형 종결(~하는 법.)"을 섞어서 리듬을 만들 것
- 같은 어미가 3문장 연속 나오면 의심하고 바꿀 것

### 4. 진짜 가치 주기
- 뻔한 소리 하지 말 것
- 구체적이고 바로 써먹을 수 있는 정보 넣기
- 두루뭉술하지 말고 구체적으로 비교
- 명확한 답이 없으면 없다고 말하기
- 모든 문단은 새로운 무언가를 더해야 함

### 5. 자연스러운 구조
- 형식을 매번 바꿀 것 - 모든 글이 같은 뼈대일 필요 없음
- 모든 걸 불릿으로 정리하지 말 것
- 문단 길이를 다양하게
- 소제목은 멋보다 쓸모 있게
"""

# ==========================================
# ✏️ WRITING FORMAT VARIATIONS
# ==========================================

WRITING_FORMATS = [
    {
        "name": "comparison_table",
        "instruction": """비교 중심의 글로 구성하세요.
- 왜 이것들을 비교하게 됐는지 짧은 도입으로 시작
- HTML <table>을 핵심에 두고 주요 항목을 나란히 비교
- 표 뒤에 어느 쪽이 나은지 본인 판단을 솔직하게
- 어떤 단락은 2~3문장으로 짧게
- 군더더기 없이 명확한 추천으로 끝내기""",
    },
    {
        "name": "myth_busting",
        "instruction": """잘못된 통념을 깨는 글로 구성하세요.
- 가장 흔한 오해와 그게 왜 틀렸는지로 시작
- [흔히 믿는 것] → [실제로 알아본 것] → [그래서 뭐가 달라지나] 패턴
- 오해에 번호 매기지 말고 자연스러운 흐름에 녹이기
- 통념이 실제로 맞는 경우도 최소 하나 포함
- "결국 진짜 중요한 한 가지"로 마무리""",
    },
    {
        "name": "short_essay",
        "instruction": """리스트나 가이드가 아니라, 짧고 의견 있는 에세이로 쓰세요.
- 불릿 전혀 사용 금지. 순수 문단으로만.
- 강한 의견이나 관찰로 시작
- 4~6개 문단에 걸쳐 논지를 쌓기
- 짧은 문단 위주 (문단당 2~4문장)
- 가끔 한 문장짜리 문단으로 강조
- 깔끔한 결론 대신 여운이 남는 질문이나 생각으로 끝내기""",
    },
    {
        "name": "qa_format",
        "instruction": """사람들이 실제로 검색하는 질문에 답하는 형식으로 쓰세요.
- <h2> 또는 <h3>를 실제 검색할 법한 질문으로
- 각 질문에 1~3문단으로 직접 답하기
- 어떤 답은 의외로 짧게 ("솔직히? 아니요.")
- 어떤 답은 주제가 그럴 만하면 길게
- 좋은 답을 못 찾은 질문 하나 포함
- 도입 문단 쓰지 말고 첫 질문으로 바로 시작""",
    },
    {
        "name": "narrative_research",
        "instruction": """주제를 층층이 풀어가는 서술형으로 쓰세요.
- 대부분이 아는 표면적인 이해에서 출발
- 그다음 더 깊이: "근데 자세히 보면 좀 더 복잡해요"
- 상충하는 의견이나 자료를 솔직하게 제시
- 정보를 리스트가 아니라 흐르는 서술에 녹이기
- 복잡함을 보여주기: "한편으로는... 그런데 또"
- 불확실함을 인정하면서, 근거가 가리키는 방향으로 끝내기""",
    },
    {
        "name": "contrarian_take",
        "instruction": """통념에 반박하는 글로 구성하세요.
- 다들 이 주제에 대해 믿는 걸 먼저 말하기
- 그다음 바로 그게 왜 불완전하거나 틀렸는지
- 찾아본 구체적인 근거로 뒷받침
- 본인 입장에 대한 가장 강한 반론도 인정
- 반박을 위한 반박 말고 진짜 설득력 있게
- 1,500자 이내로. 의견 글은 짧을수록 좋음.""",
    },
    {
        "name": "practical_breakdown",
        "instruction": """극도로 실용적인, 군더더기 없는 정리로 쓰세요.
- 도입 생략. 첫 번째 쓸모 있는 정보부터 시작.
- 짧은 문단과 가끔의 불릿을 섞기
- 가능하면 구체적 숫자, 가격, 시간 넣기
- 위쪽에 "결론부터" 요약을 넣어 훑어보는 사람 배려
- 다른 글들의 군더더기에 약간 짜증 난 듯한 톤
- 정확한 다음 단계로 끝내기: "이거 하고, 이거 하고, 이거 하세요." """,
    },
    {
        "name": "story_then_lesson",
        "instruction": """구체적인 상황이나 사례로 열고, 거기서 교훈을 끌어내세요.
- 첫 2~3문단: 장면 설정. "이런 상황을 생각해보세요" 또는 읽은 사례 묘사.
- 중간: 뭐가 잘못/잘 됐고 왜 그런지 분석
- 끝: 구체적 교훈을 사례에 빗대어
- 사례가 "아하" 순간을 만들 때 가장 잘 먹힘
- 사례는 현실적으로 - 신파 금지""",
    },
    {
        "name": "before_after",
        "instruction": """전/후 변화를 중심으로 구성하세요.
- "대부분 이렇게 하는데, 사실 저게 더 낫습니다"
- 기존 방식과 그 문제점을 먼저
- 그다음 구체적 근거와 함께 대안 제시
- 추상적 원칙 말고 구체적 예시 사용
- "후"는 막연한 이상이 아니라 실제 해볼 만하게""",
    },
]

TONE_MODIFIERS = [
    {"name": "chatty", "instruction": "수다스럽고 살짝 산만한 톤. 작은 곁가지로 새기도 하고. 줄표(—)를 자주 쓰고. 괄호 속 혼잣말이 특기 (이런 식으로). 가끔 '그리고', '근데'로 문장 시작. 오늘 기분 좋음."},
    {"name": "straight_shooter", "instruction": "오늘은 직설적이고 단도직입. 짧은 문장. 에두르지 않기. 별로면 별로라고. 돌려 말하는 거 좀 지침. 제 몫 못 하는 문장은 전부 잘라내기."},
    {"name": "skeptical", "instruction": "의심 모드. 다 따져봄. '근데 진짜 그래?'가 오늘의 단골 표현. 어느 정도 동의하는 것에도 일부러 반대편 들어보기. 그래도 공정하게, 그냥 더 까다로울 뿐."},
    {"name": "curious_nerd", "instruction": "평소보다 디테일에 깊이 들어가기. 대부분의 표면적인 글이 놓치는 반직관적 발견과 흥미로운 사실 강조. 숫자나 작동 원리에 살짝 덕질. 미묘한 차이에 진심으로 관심."},
    {"name": "no_nonsense", "instruction": "오늘은 마케팅 말투나 막연한 주장에 인내심 제로. 출처가 흐릿하면 지적. 진짜 자료를 못 찾으면 솔직히 말하기. 독자 시간 아끼게 극도로 효율적으로."},
    {"name": "laid_back", "instruction": "느긋하고 여유로운 톤. 천천히. 모든 것에 강한 의견이 필요한 건 아님 — 가끔 '뭐, 상황 나름이죠'가 정직한 답. 편한 말투. '이 부분은 별로 관심 없는데 그래도 찾아본 건 이래요'도 괜찮음."},
    {"name": "wry_humor", "instruction": "오늘은 건조한 위트. 웃기려 하지 말고 상황의 어이없음이 알아서 드러나게. 무표정한 관찰. 가끔 한 줄 펀치. '웃긴 블로그'가 아니라 '피식하는 한숨'에 가깝게."},
]

HUMAN_QUIRKS = [
    "약간 옆길로 새지만 공감되는 괄호 속 혼잣말을 딱 하나 넣기.",
    "한 문단을 '근데', '솔직히', '자 그럼' 같은 대화체로 시작하기.",
    "2~5어절짜리 짧은 문장 하나 넣기. 명사로 끝나도 됨.",
    "이 주제에서 잘 안 다뤄지는 측면 하나 짚기.",
    "스스로 정정하는 순간 넣기: '아 잠깐 —' 또는 '근데 생각해보니'.",
    "살짝 구어적인 표현 하나: '좀', '그냥', '딱히', '뭐', '솔직히'.",
    "한 군데서 문단 중간에 입장을 다시 생각하는 모습 보이기.",
    "'웃긴 건', '아무도 말 안 하는 건' 으로 시작하는 문장 하나.",
    "한 섹션을 좀 갑작스럽게 끝내기. 더 할 말 없다는 듯이.",
    "독자에게 던지는 수사적 질문 하나 — 딱 하나만.",
    "특정 커뮤니티/카페 글을 막연히 언급: '어떤 글에서 보니까'.",
    "줄표(—)로 문장 중간에 방향을 한 번 틀기.",
]

CATEGORIES = {
    'APPROVAL': {
        '직장인생산성': '시간관리, 업무 도구, 노션·엑셀 활용, 집중력, 재택근무 루틴, 회의·메일 정리',
        '건강관리': '거북목·허리 예방, 수면, 운동 습관, 스트레스, 눈 건강, 홈오피스 환경',
        '테크꿀팁': '아이폰·안드로이드 활용, 데이터 백업, 비밀번호 관리, 와이파이, 사진 정리, 개인정보 보호',
        '자기계발': '공부법, 온라인 강의, 외국어 학습, 독서 습관, 자격증, 사이드 프로젝트',
        '심리과학': '행동심리, 습관의 작동 원리, 미루기, 결정 피로, 흥미로운 연구 결과',
        '생활금융': '가계부, 저축 습관, 절약 팁, 구독 정리, 금융 기초, 흔한 돈 실수',
        '디지털라이프': '스마트폰 중독, 디지털 디톡스, SNS 사용, 화면 시간, 온라인 커뮤니티',
    },
    'MONEY': {
        '연말정산': '연말정산 환급, 공제 항목, 소득공제, 세액공제, 절세 팁',
        '정부지원금': '청년 지원금, 정부 보조금, 환급금 조회, 신청 방법, 자격 조건',
        '카드혜택': '신용카드 혜택 비교, 체크카드, 카드 추천, 캐시백, 연회비',
        '금융상품': '예적금 비교, 파킹통장, 투자 앱, ISA, 비상금 통장',
        '보험': '실손보험, 자동차보험 비교, 보험 리모델링, 보장 분석',
        '앱서비스': '가계부 앱, 자산관리 앱, 절약 앱, 페이 서비스 비교',
    }
}

FALLBACK_TOPICS = {
    'APPROVAL': {
        '직장인생산성': [
            '뽀모도로 vs 시간 블로킹, 직장인한테 진짜 맞는 건?',
            '노션 6개월 써보고 느낀 점: 과연 엑셀보다 나을까',
            '할 일 앱은 왜 한 달이면 다 방치하게 될까',
            '재택근무 루틴, 생산성 높이는 사람들의 공통점',
        ],
        '건강관리': [
            '거북목 스트레칭, 실제로 효과 있는 동작은 따로 있다',
            '스탠딩 데스크, 연구 결과는 뭐라고 말하나',
            '눈 피로 줄이는 법: 모니터 설정부터 점검하기',
            '직장인 허리 통증, 의자 탓만은 아니다',
        ],
        '테크꿀팁': [
            '아이폰 배터리 오래 쓰는 설정, 진짜 효과 있는 것만',
            '비밀번호 관리 앱, 사람들이 실제로 불평하는 것들',
            '폰 사진 자동 백업, 무료로 끝내는 방법 비교',
            '2단계 인증, 보안 강도순으로 정리해봤다',
        ],
        '자기계발': [
            '온라인 강의 완강률이 낮은 진짜 이유',
            '영어 공부 앱, 6개월 이상 쓰게 되는 건 어떤 거?',
            '독서 습관 만들기: 작심삼일 안 되는 현실적인 방법',
        ],
        '심리과학': [
            '미루는 습관, 의지력 문제가 아니라는 연구들',
            '매몰비용 오류: 알아도 못 빠져나오는 이유',
        ],
        '생활금융': [
            '가계부 앱, 끝까지 쓰게 되는 건 따로 있다',
            '구독료 새는 돈, 한 달에 얼마나 쌓이는지 계산해봤다',
        ],
    },
    'MONEY': {
        '연말정산': [
            '연말정산 13월의 월급, 놓치기 쉬운 공제 항목 정리',
            '월세 세액공제, 자격 되는데 안 받는 사람들',
        ],
        '정부지원금': [
            '청년 지원금, 나도 받을 수 있는지 한 번에 확인하는 법',
            '숨은 정부 환급금 조회, 진짜 되는 사이트는 어디',
        ],
        '카드혜택': [
            '신용카드 연회비 본전 뽑는 법, 혜택 계산해봤다',
            '체크카드 캐시백, 카드별로 실제 혜택 비교',
        ],
        '금융상품': [
            '파킹통장 금리 비교, 비상금 어디에 둘까',
            'ISA 계좌, 진짜 나한테 이득인지 따져봤다',
        ],
    }
}

# ==========================================
# 🔒 SECURITY
# ==========================================

class SecurityValidator:
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
    def __init__(self):
        self.anthropic_key = os.getenv('ANTHROPIC_API_KEY')
        self.unsplash_key = os.getenv('UNSPLASH_API_KEY')
        self.blog_id = os.getenv('BLOGGER_BLOG_ID')

        if not self.anthropic_key:
            raise ValueError("❌ ANTHROPIC_API_KEY required")

        self.claude = Anthropic(api_key=self.anthropic_key)
        self.validator = SecurityValidator()
        self.conversation_history = []

        self.persona = random.choice(SYSTEM_PROMPTS)
        self.system_prompt = self.persona["prompt"] + UNIVERSAL_RULES
        self.writing_format = random.choice(WRITING_FORMATS)
        self.tone = random.choice(TONE_MODIFIERS)
        self.quirks = random.sample(HUMAN_QUIRKS, 3)

        self.existing_posts = []

    def _get_blogger_service(self):
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
        print("📚 기존 게시물 불러오는 중...")

        if not self.blog_id:
            print("   ⚠️ BLOGGER_BLOG_ID 없음 — 건너뜀")
            return []

        try:
            service = self._get_blogger_service()
            posts = []
            request = service.posts().list(
                blogId=self.blog_id,
                maxResults=50,
                status='LIVE',
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
                request = service.posts().list_next(request, response)

            try:
                draft_request = service.posts().list(
                    blogId=self.blog_id,
                    maxResults=50,
                    status='DRAFT',
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
                pass

            self.existing_posts = posts
            print(f"   ✅ 기존 게시물 {len(posts)}개 확인")
            return posts

        except Exception as e:
            print(f"   ⚠️ 게시물 불러오기 실패: {e}")
            return []

    def _extract_keywords(self, text):
        """한글/영문/숫자 키워드 추출 (한국어 조사·불용어 제거)"""
        # 한국어 불용어 + 자주 붙는 조사/어미
        stop_words = {
            '그리고', '하지만', '그런데', '그래서', '또는', '정말', '진짜', '아주',
            '매우', '너무', '좀', '더', '제일', '가장', '나도', '내가', '우리', '당신',
            '이거', '저거', '그거', '이것', '저것', '그것', '여기', '저기', '거기',
            '하는', '되는', '있는', '없는', '같은', '대해', '대한', '위한', '통해',
            '에서', '으로', '에게', '한테', '부터', '까지', '이다', '한다', '된다',
            '방법', '법은', '경우', '때문', '이런', '저런', '그런', '어떤', '무슨',
            'the', 'a', 'an', 'is', 'are', 'to', 'for', 'of', 'and', 'or', 'vs',
        }
        # 한글 2글자 이상 덩어리, 영문/숫자 토큰 추출
        tokens = re.findall(r'[가-힣]{2,}|[a-zA-Z0-9]{2,}', text.lower())
        result = set()
        for t in tokens:
            if t in stop_words:
                continue
            result.add(t)
            # 한글 토큰은 조사가 붙는 경우가 많아 앞 2~4글자 어근도 추가
            if re.match(r'[가-힣]+', t) and len(t) >= 3:
                result.add(t[:2])
        return result

    def is_duplicate(self, title):
        if not self.existing_posts:
            return False

        title_norm = title.lower().strip()
        new_keywords = self._extract_keywords(title)

        for post in self.existing_posts:
            existing_norm = post['title'].lower().strip()

            if title_norm == existing_norm:
                return True

            existing_keywords = self._extract_keywords(post['title'])
            if existing_keywords and new_keywords:
                overlap = len(new_keywords & existing_keywords)
                similarity = overlap / max(len(new_keywords), len(existing_keywords))
                if similarity >= 0.6:
                    print(f"   ⚠️ 기존 글과 너무 유사: '{post['title']}' ({similarity:.0%})")
                    return True

        return False

    def find_related_posts(self, title, labels, max_links=3):
        if not self.existing_posts:
            return []

        new_keywords = self._extract_keywords(title)
        new_labels = set(l.lower() for l in labels) if labels else set()

        scored = []
        for post in self.existing_posts:
            if not post.get('url'):
                continue

            score = 0
            post_labels = set(l.lower() for l in post.get('labels', []))
            label_overlap = len(new_labels & post_labels)
            score += label_overlap * 2

            post_keywords = self._extract_keywords(post['title'])
            keyword_overlap = len(new_keywords & post_keywords)
            score += keyword_overlap

            if score > 0:
                scored.append((score, post))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [post for _, post in scored[:max_links]]

    # ------------------------------------------
    # API call helpers (Opus 4.5용 - adaptive thinking 제거)
    # ------------------------------------------

    def _call_claude(self, messages, max_tokens=4096, use_json_output=False, json_schema=None):
        """Opus 4.5 API 호출 (adaptive thinking 없음)"""
        kwargs = {
            "model": CLAUDE_MODEL,
            "max_tokens": max_tokens,
            "system": self.system_prompt,
            "messages": messages,
        }

        if use_json_output and json_schema:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": json_schema,
            }

        response = self.claude.messages.create(**kwargs)
        return response

    def _extract_text(self, response):
        """응답에서 텍스트 추출"""
        text_parts = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
        return "\n".join(text_parts)

    def _append_to_history(self, role, content):
        """Multi-turn 대화 히스토리 관리"""
        if role == "user":
            self.conversation_history.append({"role": "user", "content": content})
        elif role == "assistant":
            text = self._extract_text(content)
            self.conversation_history.append({"role": "assistant", "content": text})

    # ------------------------------------------
    # Step 0: Dynamic Topic Generation
    # ------------------------------------------

    def step_0_generate_topic(self):
        print("🎯 [0/7] 새 주제 생성 중...")

        existing_titles = [p['title'] for p in self.existing_posts]
        existing_titles_str = "\n".join(f"- {t}" for t in existing_titles[-30:])

        categories = CATEGORIES[CURRENT_MODE]
        category_str = "\n".join(f"- {k}: {v}" for k, v in categories.items())

        topic_schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "category": {
                    "type": "string",
                    "description": "위에 나열된 카테고리 키 중 하나 (한글 그대로)"
                },
                "topic_title": {
                    "type": "string",
                    "description": "구체적이고 끌리는 한국어 블로그 제목"
                },
                "why_this_topic": {
                    "type": "string",
                    "description": "이 주제가 독자를 끌 이유 한 문장"
                }
            },
            "required": ["category", "topic_title", "why_this_topic"]
        }

        prompt = f"""한국어 블로그 "인사이트 크로스로드"에 올릴 새 글 주제가 필요해요.

## 사용 가능한 카테고리
{category_str}

## 이미 발행한 글 (절대 반복하거나 비슷하게 겹치지 말 것)
{existing_titles_str if existing_titles_str else "(아직 글 없음)"}

## 요구사항
- 한국 사람들이 네이버나 구글에 실제로 검색할 만한 주제일 것
- 막연한 주제 말고 구체적인 각도 (나쁜 예: "노션 활용법" — 좋은 예: "노션 6개월 써보고 느낀, 엑셀보다 나은 점과 아닌 점")
- 뻔한 자기계발이나 당연한 조언은 피할 것
- 제목이 구체적인 이득이나 의외의 발견을 약속할 것
- 위 기존 글 목록에서 적게 다뤄진 카테고리를 고를 것
- 기존 모든 제목과 확실히 다를 것
- 제목에 "완벽 가이드", "총정리", "필수", "여러분" 같은 AI 티 나는 표현 금지

주제 하나를 생성하세요. 스키마에 맞는 JSON만 반환하고, 마크다운 코드블록은 쓰지 마세요."""

        try:
            response = self._call_claude(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1000,
                use_json_output=True,
                json_schema={"name": "topic_generation", "schema": topic_schema},
            )

            text = self._extract_text(response)
            result = json.loads(text)

            topic = result['topic_title']
            category = result['category']

            valid_categories = list(categories.keys())
            if category not in valid_categories:
                category = random.choice(valid_categories)

            if self.is_duplicate(topic):
                print(f"   ⚠️ 생성된 주제가 중복, 폴백으로 전환...")
                return self._topic_fallback()

            print(f"   ✅ 생성됨: [{category}] {topic}")
            print(f"   💡 이유: {result.get('why_this_topic', 'N/A')}")
            return category, topic

        except Exception as e:
            print(f"   ⚠️ 동적 주제 생성 실패: {e}")
            return self._topic_fallback()

    def _topic_fallback(self):
        print("   ↳ 주제 풀에서 폴백...")
        pool = FALLBACK_TOPICS.get(CURRENT_MODE, {})

        all_topics = []
        for cat, topics in pool.items():
            for t in topics:
                all_topics.append((cat, t))

        random.shuffle(all_topics)

        for cat, topic in all_topics:
            if not self.is_duplicate(topic):
                print(f"   ✅ 폴백: [{cat}] {topic}")
                return cat, topic

        cat, topic = random.choice(all_topics)
        print(f"   ⚠️ 폴백도 전부 중복, 그냥 사용: {topic}")
        return cat, topic

    # ------------------------------------------
    # Pipeline stages
    # ------------------------------------------

    def step_1_plan(self, topic):
        print(f"🧠 [1/7] 글 구성 짜는 중...")

        plan_schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "working_title": {
                    "type": "string",
                    "description": "구체적 이득을 약속하는 SEO 친화적 한국어 제목"
                },
                "hook_concept": {
                    "type": "string",
                    "description": "도입을 어떻게 열지 한 문장"
                },
                "contrarian_angle": {
                    "type": "string",
                    "description": "어떤 통념을 뒤집는가?"
                },
                "sections": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "header": {"type": "string"},
                            "key_point": {"type": "string"},
                            "research_element": {"type": "string"}
                        },
                        "required": ["header", "key_point", "research_element"]
                    },
                    "description": "자연스럽게 이어지는 3~5개 섹션"
                },
                "honest_caveat": {
                    "type": "string",
                    "description": "포함할 한계 또는 '이런 경우엔 안 맞음' 하나"
                },
                "image_queries": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Unsplash 검색용 시각 컨셉 2개 — 반드시 영어로 (예: 'office desk laptop', 'morning coffee notebook')"
                }
            },
            "required": ["working_title", "hook_concept", "contrarian_angle", "sections", "honest_caveat", "image_queries"]
        }

        prompt = f"""이 주제로 글을 써야 해요: "{topic}"

생각해볼 것:
1. 이 주제에 대한 통념 중에 틀렸거나 불완전한 게 뭘까?
2. 비슷한 글 50개 사이에서 이걸 굳이 읽을 만하게 만드는 각도는?
3. 대부분의 글이 건너뛰는 구체적인 정보는 뭘까?

다음 조건의 구성을 짜세요:
- 독자가 "어, 이건 몰랐네" 하게 만드는 도입
- 서로 이어지는 3~5개 섹션 (랜덤한 소주제 나열 금지)
- 독자의 예상을 뒤집는 대목 하나
- "힘내세요" 같은 헛소리 말고 구체적인 다음 단계로 마무리

중요: image_queries는 반드시 영어로 작성하세요. Unsplash가 한글 검색어를 못 알아듣습니다.

스키마에 맞는 JSON만 반환하고, 마크다운 코드블록은 쓰지 마세요."""

        try:
            self._append_to_history("user", prompt)

            response = self._call_claude(
                messages=self.conversation_history,
                max_tokens=2000,
                use_json_output=True,
                json_schema={"name": "article_plan", "schema": plan_schema},
            )

            self._append_to_history("assistant", response)
            text = self._extract_text(response)
            plan = json.loads(text)

            if len(plan.get("image_queries", [])) < 2:
                plan["image_queries"] = ["office desk workspace", "person taking notes"]

            return plan

        except Exception as e:
            print(f"⚠️ 구성 짜기 실패: {e}")
            return self._plan_fallback(topic)

    def _plan_fallback(self, topic):
        print("   ↳ 폴백 구성 시도...")
        self.conversation_history = []

        prompt = f"""이 주제로 글을 써야 해요: "{topic}"

다음 필드를 가진 JSON 객체를 반환하세요:
- working_title (string, 한국어)
- hook_concept (string, 한국어)
- contrarian_angle (string, 한국어)
- sections (header, key_point, research_element를 가진 객체 배열, 한국어)
- honest_caveat (string, 한국어)
- image_queries (영어 문자열 2개 — Unsplash 검색용)

JSON만, 마크다운 코드블록 없이:"""

        self._append_to_history("user", prompt)

        try:
            response = self._call_claude(
                messages=self.conversation_history,
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
            print(f"⚠️ 폴백 구성도 실패: {e}")
            return None

    def step_2_write_draft(self, plan):
        print(f"✍️ [2/7] 초안 작성 중...")
        print(f"   📐 형식: {self.writing_format['name']}")
        print(f"   🎭 톤: {self.tone['name']}")
        print(f"   👤 페르소나: {self.persona['name']}")

        quirks_str = "\n".join(f"- {q}" for q in self.quirks)

        prompt = f"""우리가 짠 구성을 바탕으로:
- 제목: {plan['working_title']}
- 각도: {plan['contrarian_angle']}
- 섹션: {json.dumps(plan['sections'], indent=2, ensure_ascii=False)}
- 한계: {plan['honest_caveat']}

전체 블로그 글을 HTML 형식으로 작성하세요. 한국어로 씁니다.

## 이 글의 형식
{self.writing_format['instruction']}

## 이 글의 톤
{self.tone['instruction']}

## 사람 같은 디테일 (자연스럽게 녹이기 - 억지로 끼워넣지 말 것)
{quirks_str}

## 한국어 문체 규칙 (가장 중요)
- 어미를 섞어서 쓸 것: "~합니다 / ~예요 / ~죠 / ~거든요 / 명사형 종결". 같은 어미 3연속 금지.
- 도입은 말 걸듯이 자연스럽게. "오늘은 ~에 대해 알아보겠습니다" 같은 기계적 도입 금지.
- "결론적으로", "정리하자면", "~하는 것이 중요합니다", "필수입니다", "여러분" 금지.
- 문장 길이를 다양하게. 짧은 문장과 긴 문장을 섞기.

## 기술 요구사항
- 1,500~2,500자 (공백 제외 한국어 기준, 충분한 분량)
- <h2>를 주요 섹션, <h3>를 하위 섹션에
- 문단은 <p>로
- 이미지 마커 정확히 2개 배치: [IMAGE: {plan['image_queries'][0]}] 와 [IMAGE: {plan['image_queries'][1]}]
- 순수 HTML만 출력. <html>, <head>, <body> 태그 금지. 마크다운 코드블록 금지.

## 내용 요구사항
- 가짜 경험·통계·이메일·이름·자격 금지
- 뻔한 빈 문단 금지
- 모든 섹션이 구체적 가치를 더해야 함"""

        self._append_to_history("user", prompt)

        try:
            response = self._call_claude(
                messages=self.conversation_history,
                max_tokens=8000,
            )

            self._append_to_history("assistant", response)
            draft = self._extract_text(response)
            return self.validator.sanitize_html(draft)

        except Exception as e:
            print(f"⚠️ 작성 실패: {e}")
            return None

    def step_3_self_critique(self, draft):
        print(f"🔍 [3/7] 자가 검토 및 개선...")

        critique_and_fix_prompt = f"""방금 쓴 초안을 검토하고, 개선된 버전을 만드세요.

## 검토 체크리스트 (가차없이)
1. AI 티 한국어: "결론적으로", "정리하자면", "~하는 것이 중요합니다", "필수입니다", "여러분", "완벽 가이드", "총정리", "꼭 알아야 할" 같은 표현 없나?
2. 어미 반복: "~합니다"로만 끝나는 문장이 연속으로 있나? 있으면 "~예요/~죠/~거든요/명사형"으로 섞어라.
3. 지어낸 것: 가짜 통계, 가짜 경험, 만들어낸 출처 없나?
4. 군더더기: 진짜 정보를 안 주는 문단 없나?
5. 가치: 모든 섹션이 구체적이고 새로운 걸 알려주나?
6. 톤 점검: 의도한 톤({self.tone['name']})에 맞나? 아니면 밋밋한 AI 말투로 흘렀나?
7. 형식 점검: 의도한 형식({self.writing_format['name']})을 따르나?
8. 도입 점검: "오늘은 ~에 대해" 같은 뻔한 도입이면 바꿔라.
9. 문장 길이: 다 비슷한 길이면 공격적으로 섞어라.

## 할 일
모든 문제를 고쳐서 글 전체를 다시 쓰세요.
개선된 HTML만 출력. 설명 금지. 마크다운 코드블록 금지."""

        self._append_to_history("user", critique_and_fix_prompt)

        try:
            response = self._call_claude(
                messages=self.conversation_history,
                max_tokens=8000,
            )

            self._append_to_history("assistant", response)
            improved = self._extract_text(response)
            result = self.validator.sanitize_html(improved)

            if len(result) < 500:
                print("   ⚠️ 개선본이 너무 짧음, 초안 사용")
                return draft

            return result

        except Exception as e:
            print(f"⚠️ 검토 실패: {e}")
            return draft

    def step_4_humanize(self, content):
        print(f"🧑 [4/7] 사람 손길 추가...")

        humanize_prompt = f"""당신은 작가가 아니라 사람 편집자입니다. 이 글이 AI 결과물이 아니라 진짜 사람의 블로그 글처럼 읽히도록 작은 수정을 하세요.

## 할 일
- 문장 길이를 더 다양하게. 5어절 문장과 25어절 문장을 섞기.
- 4문장 넘는 문단은 쪼개기.
- 도입이 뻔하면 잘라내거나 구체적인 걸로 교체.
- 딱딱한 단어를 편한 걸로: "활용하다"→"쓰다", "구매하다"→"사다".
- 어미를 더 섞기: "~합니다"가 반복되면 "~예요/~죠/~거든요"로.
- 짧은 문장 1~2개 넣기. 명사로 끝나도 됨.
- 섹션 사이 전환이 다 매끄럽지 않게.
- 모든 섹션이 비슷한 길이면 하나를 더 짧게/길게.
- 이미 한 말을 다시 하는 문장은 삭제.

## 하지 말 것
- 사실이나 주장을 바꾸지 말 것
- 가짜 개인 경험 추가 금지
- 이모지나 느낌표 추가 금지
- 전체 구조 바꾸지 말 것
- [IMAGE: ...] 마커 삭제 금지

## 입력 글
{content}

## 출력
편집된 HTML 글만. 설명 금지. 마크다운 코드블록 금지."""

        try:
            response = self._call_claude(
                messages=[{"role": "user", "content": humanize_prompt}],
                max_tokens=8000,
            )

            result = self._extract_text(response)
            result = self.validator.sanitize_html(result)

            if len(result) < 500:
                print("   ⚠️ 사람화 버전이 너무 짧음, 이전 버전 사용")
                return content

            return result

        except Exception as e:
            print(f"⚠️ 사람화 실패: {e}")
            return content

    def step_5_add_images(self, content):
        print(f"🎨 [5/7] 이미지 추가...")

        if not self.unsplash_key:
            print("   ⚠️ Unsplash 키 없음 — 이미지 건너뜀")
            return re.sub(r'\[IMAGE:.*?\]', '', content)

        markers = re.findall(r'\[IMAGE:.*?\]', content)

        for marker in markers:
            query = marker.replace('[IMAGE:', '').replace(']', '').strip()
            print(f"   🔍 검색: {query}")

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
                    print(f"   ⚠️ Unsplash API 응답 코드 {response.status_code}")
                    content = content.replace(marker, '', 1)

            except Exception as e:
                print(f"   ⚠️ 이미지 가져오기 실패: {e}")
                content = content.replace(marker, '', 1)

        return content

    def step_6_add_internal_links(self, content, title, labels):
        print(f"🔗 [6/7] 내부 링크 추가...")

        related = self.find_related_posts(title, labels)

        if not related:
            print("   ℹ️ 관련 글 없음 — 건너뜀")
            return content

        links_html = '\n<div style="margin-top: 3rem; padding: 1.5rem; background: #f9fafb; border-radius: 12px; border: 1px solid #e5e7eb;">\n'
        links_html += '<h3 style="margin-top: 0; color: #374151; font-size: 1.125rem;">함께 보면 좋은 글</h3>\n<ul style="padding-left: 1.25rem;">\n'

        for post in related:
            post_title = post['title']
            post_url = post['url']
            links_html += f'<li style="margin-bottom: 0.5rem;"><a href="{post_url}" style="color: #2563eb; text-decoration: none;">{post_title}</a></li>\n'

        links_html += '</ul>\n</div>'

        print(f"   ✅ 내부 링크 {len(related)}개 추가")
        return content + links_html

    def step_7_publish(self, title, content, category):
        print(f"🚀 [7/7] Blogger에 발행...")

        css = '''
<style>
    .post-body {
        font-family: 'Apple SD Gothic Neo', 'Malgun Gothic', 'Noto Sans KR', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        line-height: 1.85;
        color: #1f2937;
        font-size: 1.0625rem;
        word-break: keep-all;
    }
    .post-body h2 {
        font-size: 1.625rem;
        font-weight: 700;
        color: #111827;
        margin: 3rem 0 1.25rem;
        letter-spacing: -0.02em;
    }
    .post-body h3 {
        font-size: 1.3rem;
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
        margin: 2rem 0;
        border-radius: 0 8px 8px 0;
    }
    .post-body table {
        width: 100%; border-collapse: collapse; margin: 2rem 0; font-size: 0.95rem;
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
    <strong>안내:</strong> 이 글의 일부 링크는 제휴 링크일 수 있으며,
    독자에게 추가 비용 없이 이 사이트 운영에 도움이 됩니다.
    직접 조사해서 괜찮았던 것만 소개합니다.
</div>
'''

        final_html = f"{css}<div class='post-body'>{content}{disclaimer}</div>"

        tags = [category]
        tag_map = {
            'APPROVAL': ['생활정보', '꿀팁', '정리'],
            'MONEY': ['리뷰', '비교', '추천'],
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

            print(f"✅ 임시저장 글 생성 완료!")
            print(f"   📝 제목: {title}")
            print(f"   🔗 URL: {result.get('url', 'N/A')}")
            print(f"   🏷️ 태그: {tags}")
            return result

        except Exception as e:
            print(f"❌ 발행 실패: {e}")
            return None

    def run(self):
        print(f"""
╔═══════════════════════════════════════════════════════════════════╗
║  Pro Blog Bot v5.0 - Korean Edition (Opus 4.5)                   ║
║  Mode: {CURRENT_MODE:10s} | Model: {CLAUDE_MODEL:28s}   ║
║  Persona: {self.persona['name']:12s} | Format: {self.writing_format['name']:15s}  ║
║  Tone: {self.tone['name']:15s}                                       ║
║  Features: 중복방지 · 동적주제 · 페르소나 · 내부링크             ║
╚═══════════════════════════════════════════════════════════════════╝
""")

        self.fetch_existing_posts()
        category, topic = self.step_0_generate_topic()

        print(f"\n📁 카테고리: {category}")
        print(f"📝 주제: {topic}")
        print("-" * 60)

        self.conversation_history = []

        plan = self.step_1_plan(topic)
        if not plan:
            print("❌ 구성 짜기 실패 — 중단")
            return

        title = plan['working_title']

        if self.is_duplicate(title):
            print(f"⚠️ 기획된 제목이 중복: {title}")
            print("   제목 조정...")
            title = f"{title} (다시 보기)"

        print(f"   📌 제목: {title}")
        print(f"   💡 각도: {plan['contrarian_angle']}")

        draft = self.step_2_write_draft(plan)
        if not draft:
            print("❌ 초안 실패 — 중단")
            return

        improved = self.step_3_self_critique(draft)
        if not improved:
            improved = draft

        humanized = self.step_4_humanize(improved)
        with_images = self.step_5_add_images(humanized)

        tags = [category]
        tag_map = {
            'APPROVAL': ['생활정보', '꿀팁', '정리'],
            'MONEY': ['리뷰', '비교', '추천'],
        }
        tags.extend(random.sample(tag_map.get(CURRENT_MODE, []), 2))

        final_content = self.step_6_add_internal_links(with_images, title, tags)
        self.step_7_publish(title, final_content, category)

        print("\n✅ 파이프라인 완료!")


if __name__ == "__main__":
    bot = ProBlogBotV4()
    bot.run()
