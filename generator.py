# -*- coding: utf-8 -*-
"""dow-seedance-selling-video 生成核心（Python 移植版，唯一事实来源）

移植自 miniprogram/utils/generator.js，模板基准：
references/dow-english-kit.md + references/output-templates.md
深度规则：references/dow-playbook.md
提示词模板参考：awesome-seedance（github.com/LearnPrompt/awesome-seedance）
「UGC 口播测评带货」与「电影级产品广告分镜」模板（产品锁独立成段、
realistic hands、收尾两拍、Style Keywords 尾块、标签避特写）。
"""

import math
import re

# ---------------------------------------------------------------- 常量文本 ----

NEGATIVE_LINES = '\n'.join([
    'professional photography, studio lighting, softbox, three-point lighting,',
    'perfect skin, flawless, retouched, symmetrical, centered composition,',
    'clean background, minimalist set, 3D render, CGI, oversaturated,',
    'hyperreal, AI-art aesthetic, illustration, plastic skin, over-smoothed,',
    'NO text, NO Chinese characters, NO English text, NO numbers, NO logos,',
    'NO UI elements, NO recognizable symbols, NO punctuation.',
    'Documentary realism throughout, NOT AI-art aesthetic, NOT 3D render,',
    'NOT illustration, NOT professional advertising footage.',
    'NO product deformation, NO color or pattern drift — the {productShort}',
    'stays exactly identical in every shot.',
])

COMPLIANCE_NEGATIVES = '\n'.join([
    'NO superlatives, NO efficacy or medical claims, NO fake certifications,',
    'NO misleading guarantees.',
    'NO invented sales numbers, NO invented reviews.',
    'NO national flags, NO emblems, NO fake certification marks, NO misleading badges.',
])

# awesome-seedance 模板：正向需求收尾（关键词堆在提示语最末尾）
STYLE_KEYWORDS_TAIL = '\n'.join([
    '[Style Keywords]',
    'vertical 9:16, handheld iPhone UGC video, realistic hands, natural skin texture,',
    'mixed warm-and-cool household lighting, lived-in cluttered set, documentary realism,',
    'one product, one creator, one simple action per beat,',
    'no logos, no watermarks, no on-screen text — captions added in post.',
])

DEFAULT_PERSONA = {
    'name': 'EMMA',
    'desc': '\n'.join([
        'Woman in her early 30s, average build with relaxed shoulders,',
        'shoulder-length brown hair loosely tied back with a few flyaways,',
        'fair skin with visible pores and faint freckles across the nose,',
        'wearing a slightly wrinkled heather-gray hoodie and loose charcoal sweatpants,',
        'thin silver hoop earrings, no makeup, a small leather-strap watch on her left wrist,',
        'bare feet, short unpolished nails, no other accessories.',
    ]),
}

DEFAULT_ACTION_LOCK = (
    'Holds the product with both hands, slow and simple movements only — '
    'no spinning, no flipping, no fine multi-finger manipulation. '
    'The gesture style stays identical across shots.'
)

SETTINGS = {
    'bedroom': {
        'label': '卧室床头·夜（暖台灯 + 走廊冷光）',
        'lock': '\n'.join([
            'A lived-in bedroom corner at night. Warm bedside lamp on camera-right mixed',
            'with cool ambient light from a hallway door on camera-left. Nightstand behind',
            'her holds a half-finished coffee mug with stains, an opened express bag with',
            'tape peeling, a crumpled tissue, a tangled charging cable.',
            'Spatial composition: medium close-up, her torso sits slightly left of center,',
            'product held at chest height, background clutter soft and slightly out of focus.',
        ]),
        'light': '\n'.join([
            'Mix lighting: warm bedside lamp on camera-right combined with cool ambient',
            'light from a hallway door on camera-left. Color temperatures clash naturally,',
            'uneven shadows across the face. No fill light.',
        ]),
        'lightSource': 'warm bedside lamp plus cool hallway light',
    },
    'kitchen': {
        'label': '厨房一角·白天（窗冷光 + 暖顶灯）',
        'lock': '\n'.join([
            'A lived-in apartment kitchen corner at midday. Cool daylight from a window',
            'on camera-left mixed with a warm overhead household lamp. Countertop behind',
            'her holds a half-finished coffee mug with stains, an opened express bag with',
            'tape peeling, a crumpled tissue, a tangled charging cable.',
            'Spatial composition: medium close-up, her torso sits slightly left of center,',
            'product held at chest height, background clutter soft and slightly out of focus.',
        ]),
        'light': '\n'.join([
            'Mix lighting: cool daylight from a window on camera-left combined with a warm',
            'overhead household lamp. Color temperatures clash naturally, uneven shadows',
            'across the face. No fill light.',
        ]),
        'lightSource': 'window daylight on camera-left plus warm overhead lamp',
    },
}

CLUTTER = '\n'.join([
    'Lived-in cluttered background: half-finished coffee mug with stains, an opened',
    'express bag with tape peeling, a crumpled tissue, a tangled charging cable.',
    'NOT a styled set, NOT a clean background.',
])

UNBOXING_PROP = '\n'.join([
    "Within arm's reach on the same surface: a sealed express bag with the tape",
    'still on, a printed dust bag, and a small after-sales card. The bag she opens',
    'is the sealed one in front of her, not the opened bag in the background.',
])

IPHONE = '\n'.join([
    'Shot on iPhone, handheld with subtle natural shake, slight motion blur,',
    'natural sensor noise and mild compression artifacts,',
    'composition slightly off-center, casual framing, vertical 9:16.',
    'Amateur home-video feel, unposed grip.',
])

SKIN_PATCH = '\n'.join([
    'Skin shows natural texture with pores and subtle imperfections,',
    'not over-smoothed plastic. Hands have natural anatomy with five fingers and',
    'correct proportions. Eyes remain stable and focused without flickering.',
    'Mouth movement strictly synchronized to dialogue per shot — closed and still',
    'otherwise. Same face, same hair, same outfit across every shot — no face drift.',
])

CAMERA_MOVES = [
    'slow push-in over 3 seconds, subtle 1.05x zoom, push-in starts at 0s and ends at shot end',
    'slow push-in over 3 seconds, subtle 1.05x zoom, push-in starts at 1s and ends at shot end',
    'handheld sway, slight reframe left at 2s, no zoom',
    'slow pull-back over 3 seconds, subtle 0.95x zoom out, starts at 1s and ends at shot end',
]

DEFAULT_ACTIONS = [
    'lifts the product up beside her face with both hands, eyes wide and eyebrows raised',
    'holds the product at chest level, showing it to the camera with both hands',
    'points at the product detail with her left index finger, holding the product steady in her right hand',
    'cradles the product in her right arm, smiles and nods at the camera, then points down toward the bottom of the frame with her left index finger',
]

DEFAULT_HOOK_B = 'I almost skipped this one, and now I use it every day.'

# playbook 第 5 节：收到包裹 → 展示包装 → 取出布袋 → 捧出产品 → 把玩
UNBOXING_ACTIONS = [
    'holds a sealed express bag up beside her face with both hands, eyes wide and eyebrows raised',
    'tears the tape off the express bag slowly, pulls out a printed dust bag and a small after-sales card, lays both flat in front of her',
    'opens the dust bag with both hands and lifts the product out, keeping it steady and low in frame',
    'cradles the product in her right hand and points at one detail with her left index finger, then points down toward the bottom of the frame',
]

DEFAULT_ZH = {
    'hook': '（占位）夸张表情 + 具体数字或反常识句，2 秒内落地',
    'seed1': '（占位）核心卖点 + 真实使用场景',
    'seed2': '（占位）第二卖点或场景补充',
    'proof': '（占位）真实评价 / 销量数据 / 前后对比，发布前替换真实数据',
    'action': '（占位）明确购买指令，指向屏幕下方链接位',
    'hookB': '（占位）痛点钩：戳痛点或颠覆认知',
}

SCRIPT_LABELS = {
    'demo': '把玩展示型',
    'unboxing': '开箱收礼型',
}

# ------------------------------------------------------------- 合规词表 ----
# 电商合规词表（playbook 第 3 节）

BANNED_EN = [
    ('best', re.compile(r'\bbest\b', re.I)),
    ('#1', re.compile(r'#1(?![0-9])')),
    ('No.1', re.compile(r'\bno\.?\s*1\b', re.I)),
    ('guaranteed', re.compile(r'\bguarantee(d|s)?\b', re.I)),
    ('perfect', re.compile(r'\bperfect\b', re.I)),
    ('100%', re.compile(r'100\s*%')),
    ('instantly', re.compile(r'\binstant(ly)?\b', re.I)),
    ('overnight', re.compile(r'\bovernight\b', re.I)),
    ('cure', re.compile(r'\bcure(s|d)?\b', re.I)),
    ('treat', re.compile(r'\btreat(s|ed)?\b', re.I)),
    ('prevent', re.compile(r'\bprevent(s|ed)?\b', re.I)),
    ('heal', re.compile(r'\bheal(s|ed)?\b', re.I)),
    ('FDA', re.compile(r'\bFDA\b', re.I)),
    ('clinically proven', re.compile(r'clinically proven', re.I)),
    ('scientifically proven', re.compile(r'scientifically proven', re.I)),
    ('miracle', re.compile(r'\bmiracle\b', re.I)),
    ('permanent', re.compile(r'\bpermanent\b', re.I)),
    ('certified', re.compile(r'\bcertified\b', re.I)),
    ('certification', re.compile(r'\bcertification\b', re.I)),
    ('award-winning', re.compile(r'\baward[- ]winning\b', re.I)),
    ('dermatologist', re.compile(r'\bdermatologist\b', re.I)),
    ('doctor recommended', re.compile(r'\b(doctor|physician)[- ]recommended\b', re.I)),
    ('clinically tested', re.compile(r'clinically tested', re.I)),
    ('risk-free', re.compile(r'\brisk[- ]free\b', re.I)),
    ('side effects', re.compile(r'\bside[- ]effects?\b', re.I)),
    ('antibacterial', re.compile(r'\banti[- ]?bacterial\b', re.I)),
    ('whitening', re.compile(r'\bwhiten(ing|s|ed)?\b', re.I)),
    ('slimming', re.compile(r'\bslimming\b', re.I)),
    ('weight loss', re.compile(r'\bweight[- ]loss\b', re.I)),
    ('hair growth', re.compile(r'\bhair[- ]growth\b', re.I)),
    ('SPF', re.compile(r'\bSPF\b')),
    ('X times', re.compile(r'\b\d+(?:\.\d+)?\s*(?:x|times)\b', re.I)),
    ('in N seconds', re.compile(r'\b(?:in|within)\s+\d+\s+(?:seconds?|minutes?|hours?|days?)\b', re.I)),
]

BANNED_ZH = [
    '最好', '最佳', '最强', '最有效', '最安全', '最快', '最低', '最高',
    '最便宜', '最大', '最小', '销量第一', '第一名', '第一品牌', '全网第一',
    '排名第一', '销量冠军', '顶级', '极致', '绝对', '100%', '永久', '唯一',
    '首个', '国家级', '世界级', '王牌', '冠军', '零风险', '无副作用',
    '根治', '治愈', '治疗', '预防', '抗菌', '抑菌', '杀菌', '美白', '防晒',
    '防脱', '生发', '减肥', '瘦身', '增高', '丰胸', '见效', '立竿见影',
    '秒变', '秒杀', 'FDA',
]

ACTION_BANNED = [
    ('spin', re.compile(r'\bspin(ning|s)?\b', re.I)),
    ('flip', re.compile(r'\bflip(ping|s)?\b', re.I)),
    ('twirl', re.compile(r'\btwirl(ing|s)?\b', re.I)),
    ('juggle', re.compile(r'\bjuggl(e|ing|es)\b', re.I)),
    ('toss', re.compile(r'\btoss(ing|es)?\b', re.I)),
    ('rotate', re.compile(r'\brotat(e|ing|es)\b', re.I)),
    ('roll between fingers', re.compile(r'roll(ing)?\s+between\s+(her\s+)?fingers', re.I)),
    ('one-handed spin', re.compile(r'one[- ]hand(ed)?\s+(spin|flip)', re.I)),
]

# 改写方向（playbook 第 3 节分类，附加于扫描结果，不改变判定逻辑）
_HINT_TEXT = {
    'superlative': '绝对化/极限词 — 改描述性表述，不用「最/第一/best」类词',
    'efficacy': '功效承诺 — 删除或改写为常识可支撑的描述，不做医疗/功效断言',
    'number': '数字/时效夸大 — 模糊化处理，无检测数据不写具体倍数与见效时间',
    'endorse': '背书/认证 — 删除无依据的认证、机构、获奖与专家推荐表述',
    'guarantee': '保证/风险承诺 — 改为主观体验描述，不承诺零风险、无副作用',
}
_HINT_TERMS = {
    'superlative': {
        'best', '#1', 'No.1', 'perfect', '100%', 'permanent',
        '最好', '最佳', '最强', '最有效', '最安全', '最快', '最低', '最高',
        '最便宜', '最大', '最小', '销量第一', '第一名', '第一品牌', '全网第一',
        '排名第一', '销量冠军', '顶级', '极致', '绝对', '唯一', '首个',
        '国家级', '世界级', '王牌', '冠军',
    },
    'efficacy': {
        'cure', 'treat', 'prevent', 'heal', 'side effects', 'antibacterial',
        'whitening', 'slimming', 'weight loss', 'hair growth', 'SPF',
        '根治', '治愈', '治疗', '预防', '抗菌', '抑菌', '杀菌', '美白',
        '防晒', '防脱', '生发', '减肥', '瘦身', '增高', '丰胸',
    },
    'number': {'instantly', 'overnight', 'X times', 'in N seconds', '见效', '立竿见影', '秒变', '秒杀'},
    'endorse': {
        'FDA', 'clinically proven', 'scientifically proven', 'certified',
        'certification', 'award-winning', 'dermatologist', 'doctor recommended',
        'clinically tested',
    },
    'guarantee': {'guaranteed', 'risk-free', '零风险', '无副作用'},
}


def _hint(term):
    for cat, terms in _HINT_TERMS.items():
        if term in terms:
            return _HINT_TEXT[cat]
    return '改描述性表述，删除夸大、承诺与无依据背书'


# ------------------------------------------------------------- 工具函数 ----

def has_cjk(text):
    return re.search(r'[\u4e00-\u9fa5]', str(text or '')) is not None


def js_round(x):
    """与 JS Math.round 一致（.5 恒进位）。"""
    return math.floor(x + 0.5)


def fmt(t):
    return '{:.1f}'.format(t)


def sec(t):
    v = js_round(float(t) * 10) / 10
    return '{:g}'.format(v)


def cell(v):
    return str('' if v is None else v).replace('|', '\\|').replace('\r\n', ' ').replace('\n', ' ')


def negatives(short):
    return NEGATIVE_LINES.replace('{productShort}', short)


# ------------------------------------------------------------- 镜头计划 ----

def plan_shots(duration):
    """时长 → 镜头计划。15–18s 用 3 镜头，19–25s 用 4 镜头（Seed 拆 2 镜）。
    T1/T4 使用 script_rows（Proof 与 Action 独立成行）；T2/T3 使用 segs（末镜合并 Proof + Action）。"""
    d = min(25, max(15, js_round(float(duration or 20))))
    proof_start = d - 5
    action_start = d - 2
    four = d >= 19
    seed_mid = js_round((3 + proof_start) / 2)

    if four:
        segs = [
            {'role': 'Hook', 'start': 0, 'end': 3},
            {'role': 'Seed 1', 'start': 3, 'end': seed_mid},
            {'role': 'Seed 2', 'start': seed_mid, 'end': proof_start},
            {'role': 'Proof + Action', 'start': proof_start, 'end': d},
        ]
    else:
        segs = [
            {'role': 'Hook', 'start': 0, 'end': 3},
            {'role': 'Seed', 'start': 3, 'end': proof_start},
            {'role': 'Proof + Action', 'start': proof_start, 'end': d},
        ]

    script_rows = [{'role': 'Hook', 'start': 0, 'end': 3}]
    if four:
        script_rows.append({'role': 'Seed 1', 'start': 3, 'end': seed_mid})
        script_rows.append({'role': 'Seed 2', 'start': seed_mid, 'end': proof_start})
    else:
        script_rows.append({'role': 'Seed', 'start': 3, 'end': proof_start})
    script_rows.append({'role': 'Proof', 'start': proof_start, 'end': action_start})
    script_rows.append({'role': 'Action', 'start': action_start, 'end': d})

    return {
        'duration': d,
        'four': four,
        'proofStart': proof_start,
        'actionStart': action_start,
        'segs': segs,
        'scriptRows': script_rows,
    }


# ------------------------------------------------------------- 缺省台词 ----

def default_lines(inp):
    """缺省台词：仅作可编辑占位，self_check 会标记为待改写"""
    sold = inp.get('soldCount') or '[SALES]'
    return {
        'hook': 'Okay, I did not expect this to work this well.',
        'seed1': 'I basically just use it every day, and look at this.',
        'seed2': 'And honestly, this little detail is my favorite part.',
        'proof': 'Over ' + sold + ' sold, and the reviews are honestly lovely.',
        'action': "Link's right there — grab yours before it sells out again.",
    }


def resolve_zh(inp):
    raw = inp.get('zh')
    keys = ['hook', 'seed1', 'seed2', 'proof', 'action', 'hookB']
    out = {}
    for i, k in enumerate(keys):
        v = ''
        if isinstance(raw, list):
            if i < len(raw):
                v = str(raw[i] or '')
        elif isinstance(raw, dict):
            v = str(raw.get(k) or '')
        out[k] = v.strip() or DEFAULT_ZH[k]
    return out


def pick_actions(inp, n):
    script_type = 'unboxing' if inp.get('scriptType') == 'unboxing' else 'demo'
    base = UNBOXING_ACTIONS if script_type == 'unboxing' else DEFAULT_ACTIONS
    # 3 镜头时省略 Seed 2：把玩型取 0/1/3，开箱型取 0/2/3（跳过空镜，保证产品露出）
    idx3 = [0, 2, 3] if script_type == 'unboxing' else [0, 1, 3]
    ai = [a for a in (inp.get('actions') or []) if isinstance(a, str) and a.strip()]

    def at(lst, i):
        return lst[i] if i < len(lst) else None

    if len(ai) == n:
        return list(ai)
    if ai:
        if n == 4:
            return [at(ai, 0) or base[0], at(ai, 1) or base[1], at(ai, 2) or base[2], at(ai, 3) or base[3]]
        return [at(ai, idx3[0]) or base[idx3[0]], at(ai, idx3[1]) or base[idx3[1]], at(ai, idx3[2]) or base[idx3[2]]]
    if n == 4:
        return list(base)
    return [base[idx3[0]], base[idx3[1]], base[idx3[2]]]


def product_desc_line(inp):
    short = inp.get('product') or 'the product'
    desc = str(inp.get('productDesc') or '').strip()
    if desc:
        desc_text = re.sub(r'[.!?]+$', '', desc) + '.'
        return ('The product is the exact same ' + short + ' with these visible details: '
                + desc_text + ' No added logos, no added features.')
    if inp.get('hasImage') is not True:
        return ('The product is the exact same ' + short + '. Its appearance has NOT been provided — '
                'do not invent details; keep the product shape and color neutral and consistent.')
    return ('The product is the exact same ' + short + ' as in the reference image. '
            'No added logos, no added features.')


def display_name(persona):
    n = (persona or {}).get('name') or 'EMMA'
    return n[:1] + n[1:].lower()


def clean_action(raw, persona):
    a = str(raw or '').strip()
    a = re.sub(r'\.\s*$', '', a)
    who = display_name(persona)
    for p in [who, persona.get('name'), 'She', 'He', 'The woman', 'The girl']:
        pref = p + ' '
        if a.lower().startswith(pref.lower()):
            a = a[len(pref):].strip()
            break
    return a[:1].lower() + a[1:]


# --------------------------------------------------------- 逐镜头提示词 ----

def build_shot_prompt(inp, plan, idx, override=None):
    opts = override or {}
    st = SETTINGS.get(inp.get('setting'), SETTINGS['bedroom'])
    persona = inp.get('persona') or DEFAULT_PERSONA
    n = len(plan['segs'])
    seg = plan['segs'][idx]
    raw_line = opts.get('line')
    if raw_line is None:
        raw_line = (inp.get('lines') or [''] * (idx + 1))[idx] or ''
    line = str(raw_line or '').replace('"', "'")
    raw_action = opts.get('action')
    if raw_action is None:
        acts = inp.get('actions') or []
        raw_action = (acts[idx] if idx < len(acts) and acts[idx] else None) or DEFAULT_ACTIONS[3]
    action = clean_action(raw_action, persona)
    cam = CAMERA_MOVES[min(idx, len(CAMERA_MOVES) - 1)]
    short = inp.get('product') or 'the product'
    who = display_name(persona)
    parts = []

    if idx > 0:
        parts.append('Same room as Shot A. Same face and outfit as Shot 1.\n')

    parts.append('[Character Lock — ' + persona['name'] + ']')
    parts.append(persona['desc'])
    parts.append('Same outfit and look across all ' + str(n) + ' shots.')
    parts.append('Skin shows natural texture with pores and subtle imperfections,')
    parts.append('not over-smoothed plastic. Same face, same hair, same outfit — no face drift.\n')

    parts.append('[Action Lock]')
    parts.append(inp.get('actionLock') or DEFAULT_ACTION_LOCK)
    parts.append('Realistic hands. One simple action per beat — no multi-step')
    parts.append('manipulation inside a single shot.\n')

    parts.append('[Product Lock]')
    parts.append(product_desc_line(inp))
    parts.append('Break the product into visible structural parts — shape, color, material,')
    parts.append('proportions — and keep every part identical across all ' + str(n) + ' shots.')
    parts.append('Never end a shot on a macro close-up of printed labels; keep brand text,')
    parts.append('tags and packaging print out of frame.\n')

    parts.append('[Setting Lock]')
    parts.append(st['lock'])
    if inp.get('scriptType') == 'unboxing':
        parts.append(UNBOXING_PROP)
    parts.append('Same scene in every shot. Same room as Shot A.\n')

    parts.append(IPHONE + '\n')
    parts.append(st['light'] + '\n')
    parts.append(CLUTTER + '\n')
    parts.append(SKIN_PATCH + '\n')

    parts.append('Action and dialogue (' + sec(seg['start']) + '–' + sec(seg['end']) + 's): ' + who + ' ' + action + '.')
    parts.append(who + ' says: "' + line + '"')
    parts.append('Camera: ' + cam + '.')
    if idx == n - 1:
        parts.append('Closing beats: the ' + short + ' held alone in frame for a moment, then '
                     + who + ' looks into the camera still holding it. No on-screen text —')
        parts.append('captions are added in post.')
    parts.append('')

    parts.append('[Quality directives]')
    parts.append(persona['name'] + "'s face features stay identical across all " + str(n) + ' shots — same face, same')
    parts.append('hair angle, same accessories, same outfit.')
    parts.append('The exact same ' + short + ' in every shot — same color, same pattern, same details.')
    parts.append('Hands have natural anatomy with five fingers and correct proportions.')
    parts.append('Skin shows natural texture and pores, not over-smoothed plastic.')
    parts.append('Eyes stable and focused without flickering. Lip-sync precise to each word.')
    parts.append('Lighting consistent with ' + st['lightSource'] + ' throughout.')
    parts.append(COMPLIANCE_NEGATIVES + '\n')

    parts.append(negatives(short))
    parts.append(STYLE_KEYWORDS_TAIL)
    return '\n'.join(parts)


# ------------------------------------------------------------- 扫描检查 ----

def scan_compliance(items):
    out = []
    seen = set()
    for item in items or []:
        text = str(item.get('text') or '')
        if not text:
            continue
        for term, rex in BANNED_EN:
            if rex.search(text):
                key = (item['where'], term)
                if key not in seen:
                    seen.add(key)
                    out.append({'id': len(out) + 1, 'where': item['where'], 'term': term, 'hint': _hint(term)})
        for term in BANNED_ZH:
            if term in text:
                key = (item['where'], term)
                if key not in seen:
                    seen.add(key)
                    out.append({'id': len(out) + 1, 'where': item['where'], 'term': term, 'hint': _hint(term)})
    return out


def word_issues(items):
    out = []
    for item in items or []:
        text = str(item.get('text') or '')
        for sentence in re.split(r'[.!?]+', text):
            s = sentence.strip()
            if not s:
                continue
            n = len([w for w in re.split(r'\s+', s) if re.search(r"[A-Za-z0-9']", w)])
            if n < 4 or n > 12:
                out.append({'where': item['where'], 'n': n, 'text': s})
    return out


def action_issues(actions):
    out = []
    for i, a in enumerate(actions or []):
        for term, rex in ACTION_BANNED:
            if rex.search(str(a or '')):
                out.append({'shot': i + 1, 'term': term})
    return out


def build_self_check(ctx):
    lst = []
    lst.append({'label': '四段锁定置顶（角色 / 动作 / 产品 / 场景）', 'pass': True, 'note': '每个镜头块开头即写，产品锁独立成段'})
    lst.append({'label': '四大支柱全在（混合光源 / 生活杂物 / 毛孔纹理 / 手机拍摄）', 'pass': True, 'note': '已写入每个镜头块'})
    lst.append({'label': '六条补丁全加（塑料皮肤 / 崩手 / 眼神 / 口型 / 崩脸 / 乱码与假光照）', 'pass': True, 'note': '已写入每个镜头块'})
    lst.append({'label': 'UGC 收尾规范（末镜收尾两拍 + realistic hands / 无上屏文字）', 'pass': True,
                'note': '参考 awesome-seedance「UGC 口播测评带货」模板'})
    lst.append({'label': '时长 15–25s、四段式（钩子→种草→信任→转化）',
                'pass': 15 <= ctx['duration'] <= 25,
                'note': str(ctx['duration']) + 's · ' + str(ctx['n']) + ' 镜头'})
    lst.append({'label': '台词每句 4–12 词（允许 just / basically / you know）',
                'pass': len(ctx['wordProblems']) == 0,
                'note': ('；'.join(w['where'] + ' ' + str(w['n']) + ' 词' for w in ctx['wordProblems'])
                         if ctx['wordProblems'] else '全部合格')})
    lst.append({'label': '英文提示词与文案全英文（无中文混入）',
                'pass': len(ctx['cjkSources']) == 0,
                'note': ('含中文：' + '、'.join(ctx['cjkSources']) if ctx['cjkSources'] else '全英文')})
    lst.append({'label': '手部动作简单（无转动 / 翻面 / 多指精细操作）',
                'pass': len(ctx['actionProblems']) == 0,
                'note': ('；'.join('Shot ' + str(p['shot']) + ' ' + p['term'] for p in ctx['actionProblems'])
                         if ctx['actionProblems'] else '未发现复杂动作')})
    lst.append({'label': '台词为 AI/人工撰写，非默认占位句',
                'pass': len(ctx['usedDefault']) == 0,
                'note': ('占位：' + '、'.join(ctx['usedDefault']) if ctx['usedDefault'] else '已填写')})
    lst.append({'label': '中文注释 / 中文字幕已填写（非占位）',
                'pass': len(ctx['zhMissing']) == 0,
                'note': ('待补：' + '、'.join(ctx['zhMissing']) if ctx['zhMissing'] else '已填写')})
    lst.append({'label': '电商合规：无绝对化 / 功效承诺 / 虚假背书',
                'pass': len(ctx['warnings']) == 0,
                'note': (str(len(ctx['warnings'])) + ' 处，见合规提醒' if ctx['warnings'] else '未发现违规词')})
    lst.append({'label': '产品锁定逐项（颜色 / 材质 / 图案 / 细节）',
                'pass': bool(ctx['hasProductDesc']),
                'note': ('外观描述已写入每个镜头块' if ctx['hasProductDesc']
                         else ('有图但缺外观文字描述，模型可能脑补' if ctx['hasImage']
                               else '缺外观描述，模型可能脑补'))})
    lst.append({'label': '无未替换占位符（如 [SALES]）',
                'pass': not ctx['placeholderFound'],
                'note': 'Proof 中的 [SALES] 必须替换为真实数据' if ctx['placeholderFound'] else '未发现占位符'})
    lst.append({'label': '多镜头一致性：Same room/face + 结尾重申 + 负面轰炸两遍',
                'pass': True, 'note': '每个镜头块与结尾各写一遍'})
    lst.append({'label': '每个镜头块独立完整、可直接复制提交',
                'pass': True, 'note': 'T3 共 ' + str(ctx['n']) + ' 块'})
    lst.append({'label': '字幕时间轴覆盖全片',
                'pass': True, 'note': '0–' + str(ctx['duration']) + 's，T4 逐句对齐'})
    lst.append({'label': 'A/B 两版钩子',
                'pass': True,
                'note': 'A 默认 + B 已填，均生成完整 Shot 1' if ctx['hookBFromInput']
                        else 'B 为内置默认钩子，可在表单替换'})
    lst.append({'label': '卖点 1–3 条',
                'pass': 1 <= ctx['pointCount'] <= 3,
                'note': str(ctx['pointCount']) + ' 条'})
    lst.append({'label': '产品外观与参考图逐项一致（需人工确认）',
                'pass': bool(ctx['hasProductDesc']),
                'note': ('生成后请对照参考图逐项确认' if ctx['hasProductDesc']
                         else '未提供外观描述，请上传商品图或用 AI 补齐')})
    lst.append({'label': '中英双语字幕（仅在需要时检查）',
                'pass': (not ctx['bilingual']) or len(ctx['zhMissing']) == 0,
                'note': ('中文字幕待补' if ctx['bilingual'] and ctx['zhMissing']
                         else ('双语字幕已生成' if ctx['bilingual'] else '未开启（默认仅英文）'))})
    lst.append({'label': '口播台词与画面动作一致',
                'pass': ctx['actionCount'] == ctx['n'] and ctx['lineCount'] == ctx['n'],
                'note': ('已按镜头一一对应（AI 动作请人工复核）' if ctx['actionCount'] == ctx['n']
                         else '镜头数与台词数不一致')})
    return lst


# --------------------------------------------------------------- 总装 ----

def build_all(raw):
    inp = dict(raw or {})
    inp['points'] = [p for p in (inp.get('points') or []) if p][:3]

    plan = plan_shots(inp.get('duration'))
    d = plan['duration']
    n = len(plan['segs'])
    dl = default_lines(inp)
    zh = resolve_zh(inp)
    actions = pick_actions(inp, n)
    bilingual = inp.get('bilingual') is True

    inp['actions'] = actions

    # 每镜头台词：末镜 = proof + action 两句
    lines = []
    for i in range(n):
        if i == 0:
            lines.append(inp.get('hook') or dl['hook'])
        elif i == n - 1:
            lines.append((inp.get('proof') or dl['proof']) + ' ' + (inp.get('action') or dl['action']))
        elif i == 1:
            lines.append(inp.get('seed1') or dl['seed1'])
        else:
            lines.append(inp.get('seed2') or dl['seed2'])
    inp['lines'] = lines

    used_default = []
    if not inp.get('hook'):
        used_default.append('Hook')
    if not inp.get('seed1'):
        used_default.append('Seed 1')
    if plan['four'] and not inp.get('seed2'):
        used_default.append('Seed 2')
    if not inp.get('proof'):
        used_default.append('Proof')
    if not inp.get('action'):
        used_default.append('Action')

    zh_missing = []
    z = inp.get('zh') or {}
    needed_zh = [['hook', 'Hook'], ['seed1', 'Seed 1'], ['proof', 'Proof'], ['action', 'Action']]
    if plan['four']:
        needed_zh.insert(2, ['seed2', 'Seed 2'])
    for pair in needed_zh:
        if not str(z.get(pair[0]) or '').strip():
            zh_missing.append(pair[1])

    caption = inp.get('caption') or ('POV: you found the one everyone asks about. '
                                     + (inp.get('product') or 'This product') + ' — link in bio.')
    hashtags = inp.get('hashtags') or '#tiktokmademebuyit #giftideas #cozyfinds'
    hook_b_line = inp.get('hookB') or DEFAULT_HOOK_B
    b_action = inp.get('hookBAction') or ('frowns and shakes her head slightly, then ' + actions[0])

    # T1 脚本行（Proof / Action 独立）
    script_rows = []
    for row in plan['scriptRows']:
        role = row['role']
        if role == 'Hook':
            en, anno = inp.get('hook') or dl['hook'], zh['hook']
        elif role in ('Seed', 'Seed 1'):
            en, anno = inp.get('seed1') or dl['seed1'], zh['seed1']
        elif role == 'Seed 2':
            en, anno = inp.get('seed2') or dl['seed2'], zh['seed2']
        elif role == 'Proof':
            en, anno = inp.get('proof') or dl['proof'], zh['proof']
        else:
            en, anno = inp.get('action') or dl['action'], zh['action']
        script_rows.append({
            'role': role,
            'time': sec(row['start']) + '–' + sec(row['end']) + 's',
            'start': row['start'],
            'end': row['end'],
            'en': en,
            'zh': anno,
        })

    # T2 分镜行（末镜合并 Proof + Action）
    story_rows = []
    for i, seg in enumerate(plan['segs']):
        story_rows.append({
            'n': i + 1,
            'role': seg['role'],
            'time': sec(seg['start']) + '–' + sec(seg['end']) + 's',
            'action': actions[i],
            'camera': CAMERA_MOVES[min(i, len(CAMERA_MOVES) - 1)],
            'lineRole': seg['role'],
            'line': lines[i],
        })

    # T3 逐镜头提示词
    shot_texts = [build_shot_prompt(inp, plan, i) for i in range(n)]
    shot_cards = [{
        'n': i + 1,
        'role': plan['segs'][i]['role'],
        'time': sec(plan['segs'][i]['start']) + '–' + sec(plan['segs'][i]['end']) + 's',
        'text': t,
    } for i, t in enumerate(shot_texts)]
    shot_b = build_shot_prompt(inp, plan, 0, {'line': hook_b_line, 'action': b_action})

    # T4 字幕 + 发布文案
    sub_lines = ['[Subtitles — post-production overlay]']
    for row in script_rows:
        sub_lines.append(fmt(row['start']) + '–' + fmt(row['end']) + '  ' + row['en'])
    if bilingual:
        sub_lines.append('')
        sub_lines.append('[Subtitles — post-production overlay · 中文]')
        for row in script_rows:
            sub_lines.append(fmt(row['start']) + '–' + fmt(row['end']) + '  ' + row['zh'])
    sub_lines.append('')
    sub_lines.append('[Caption]')
    sub_lines.append(caption)
    sub_lines.append(hashtags)
    subtitles_text = '\n'.join(sub_lines)

    # T5 A/B 开头钩子
    ab_text = '\n'.join([
        '| 版本 | Hook 台词（0–3s） | 中文注 | 表情/动作 | Shot 1 提示词差异 |',
        '| --- | --- | --- | --- | --- |',
        '| A · 基准钩（数字/反常识） | ' + cell(inp.get('hook') or '（默认占位）') + ' | ' + cell(zh['hook'])
            + ' | ' + cell(actions[0]) + ' | 即上方 Shot 1 基准版 |',
        '| B · 痛点钩 | ' + cell(hook_b_line) + ' | ' + cell(zh['hookB']) + ' | ' + cell(b_action)
            + ' | 仅替换 Shot 1 的 Action and dialogue 行与台词；完整 B 版见下 |',
        '',
        '仅 Hook 段（Shot 1）不同，其余镜头块完全复用。'
        + ('' if inp.get('hookB') else ' B 为内置默认钩子，可在表单里改。'),
    ])

    # 结尾重申（负面轰炸第二遍）
    closing_text = '\n'.join([
        '[Closing — paste at the end of every submission]',
        'Same room as Shot A. Same face, same hair, same outfit across all ' + str(n) + ' shots — no face drift.',
        'The exact same ' + (inp.get('product') or 'the product')
        + ' in every shot — no product deformation, no color or pattern drift.',
        'Lighting direction and color temperature stay identical in every shot.',
        '',
        COMPLIANCE_NEGATIVES,
        '',
        negatives(inp.get('product') or 'the product'),
    ])

    # 合规扫描
    scan_items = [
        {'where': '产品名', 'text': inp.get('product')},
        {'where': '卖点', 'text': '；'.join(inp['points'])},
        {'where': '产品外观', 'text': inp.get('productDesc')},
        {'where': 'Caption', 'text': caption},
        {'where': 'Hashtags', 'text': hashtags},
    ]
    scan_items.append({'where': 'Hook', 'text': inp.get('hook') or dl['hook']})
    if plan['four']:
        scan_items.append({'where': 'Seed 1', 'text': inp.get('seed1') or dl['seed1']})
        scan_items.append({'where': 'Seed 2', 'text': inp.get('seed2') or dl['seed2']})
    else:
        scan_items.append({'where': 'Seed', 'text': inp.get('seed1') or dl['seed1']})
    scan_items.append({'where': 'Proof', 'text': inp.get('proof') or dl['proof']})
    scan_items.append({'where': 'Action', 'text': inp.get('action') or dl['action']})
    scan_items.append({'where': 'B 版 Hook', 'text': hook_b_line})
    for row in script_rows:
        scan_items.append({'where': '中文注释 ' + row['role'], 'text': row['zh']})
    warnings = scan_compliance(scan_items)

    # 词数检查（每句 4–12 词）
    word_check = [{'where': 'Hook', 'text': inp.get('hook') or dl['hook']}]
    if plan['four']:
        word_check.append({'where': 'Seed 1', 'text': inp.get('seed1') or dl['seed1']})
        word_check.append({'where': 'Seed 2', 'text': inp.get('seed2') or dl['seed2']})
    else:
        word_check.append({'where': 'Seed', 'text': inp.get('seed1') or dl['seed1']})
    word_check.append({'where': 'Proof', 'text': inp.get('proof') or dl['proof']})
    word_check.append({'where': 'Action', 'text': inp.get('action') or dl['action']})
    word_check.append({'where': 'B 版 Hook', 'text': hook_b_line})
    word_problems = word_issues(word_check)

    # 英文交付检查：提示词与英文文案不得混入中文
    cjk_sources = []

    def check_cjk(where, text):
        if has_cjk(text):
            cjk_sources.append(where)

    check_cjk('产品名', inp.get('product'))
    check_cjk('卖点', ' '.join(inp['points']))
    check_cjk('产品外观', inp.get('productDesc'))
    check_cjk('动作描述', ' '.join(actions))
    check_cjk('Hook', inp.get('hook') or dl['hook'])
    check_cjk('Seed 1', inp.get('seed1') or dl['seed1'])
    if plan['four']:
        check_cjk('Seed 2', inp.get('seed2') or dl['seed2'])
    check_cjk('Proof', inp.get('proof') or dl['proof'])
    check_cjk('Action', inp.get('action') or dl['action'])
    check_cjk('B 版 Hook', hook_b_line)
    check_cjk('Caption', caption)
    check_cjk('Hashtags', hashtags)

    # 未替换占位符（如 [SALES]）
    placeholder_found = bool(re.search(r'\[SALES\]', ' '.join([
        inp.get('proof') or dl['proof'],
        ' '.join(inp['points']),
        caption,
        hashtags,
    ])))

    self_check = build_self_check({
        'duration': d,
        'n': n,
        'wordProblems': word_problems,
        'usedDefault': used_default,
        'zhMissing': zh_missing,
        'warnings': warnings,
        'hookBFromInput': bool(inp.get('hookB')),
        'pointCount': len(inp['points']),
        'hasProductDesc': bool(str(inp.get('productDesc') or '').strip()),
        'hasImage': inp.get('hasImage') is True,
        'bilingual': bilingual,
        'actionCount': len(actions),
        'lineCount': len(lines),
        'cjkSources': cjk_sources,
        'placeholderFound': placeholder_found,
        'actionProblems': action_issues(actions),
    })

    # Markdown 出片包
    md = []
    md.append('# 出片包 · ' + (inp.get('product') or '（未命名产品）'))
    md.append('')
    md.append('> 由 Dow 便捷出片 Web 版生成；模板基准 dow-english-kit.md / output-templates.md。')
    md.append('> 发布前请替换占位数据（销量、产品名、台词占位句），产品外观须与参考图逐项一致。')
    md.append('')
    md.append('## 0 · 输入')
    md.append('')
    md.append('| 项 | 值 |')
    md.append('| --- | --- |')
    md.append('| 产品名 | ' + cell(inp.get('product')) + ' |')
    md.append('| 卖点 | ' + cell('；'.join(str(i + 1) + '. ' + p for i, p in enumerate(inp['points']))) + ' |')
    md.append('| 目标受众 | ' + cell(inp.get('audience') or 'US TikTok shoppers, 25–45') + ' |')
    md.append('| 时长 | ' + cell(str(d) + 's → ' + str(n) + ' 镜头') + ' |')
    md.append('| 脚本类型 | ' + cell(SCRIPT_LABELS.get(inp.get('scriptType'), SCRIPT_LABELS['demo'])) + ' |')
    md.append('| 场景 | ' + cell(SETTINGS.get(inp.get('setting'), SETTINGS['bedroom'])['label']) + ' |')
    md.append('| 语言 | ' + cell(inp.get('language') or
                                ('英文口播 + 中英双语字幕' if bilingual else '英文口播 + 英文字幕')) + ' |')
    md.append('| 参考图 | ' + ('未提供（外观需人工补充）' if inp.get('hasImage') is False else '已上传') + ' |')
    md.append('')
    md.append('## 1 · 口播脚本（T1）')
    md.append('')
    md.append('| 段落 | 时间 | 英文台词 | 中文注释 |')
    md.append('| --- | --- | --- | --- |')
    for row in script_rows:
        md.append('| ' + cell(row['role']) + ' | ' + cell(row['time']) + ' | ' + cell(row['en']) + ' | ' + cell(row['zh']) + ' |')
    md.append('')
    md.append('## 2 · 分镜表（T2）')
    md.append('')
    md.append('| Shot | 时间 | 画面动作 | 运镜（量化） | 对应台词 |')
    md.append('| --- | --- | --- | --- | --- |')
    for row in story_rows:
        md.append('| ' + str(row['n']) + ' | ' + cell(row['time']) + ' | ' + cell(row['action'])
                  + ' | ' + cell(row['camera']) + ' | ' + cell(row['line']) + ' |')
    md.append('')
    md.append('## 3 · 逐镜头 Seedance 提示词（T3，每块可直接复制提交）')
    md.append('')
    for shot in shot_cards:
        md.append('### Shot ' + str(shot['n']) + ' · ' + shot['role'] + '（' + shot['time'] + '）')
        md.append('')
        md.append('```text')
        md.append(shot['text'])
        md.append('```')
        md.append('')
    md.append('## 4 · 字幕与发布文案（T4）')
    md.append('')
    md.append('```text')
    md.append(subtitles_text)
    md.append('```')
    md.append('')
    md.append('## 5 · A/B 开头钩子（T5）')
    md.append('')
    md.append(ab_text)
    md.append('')
    if shot_b:
        md.append('### B 版 Shot 1（完整，可直接复制）')
        md.append('')
        md.append('```text')
        md.append(shot_b)
        md.append('```')
        md.append('')
    md.append('## 6 · 结尾重申（每套提交末尾再写一遍）')
    md.append('')
    md.append('```text')
    md.append(closing_text)
    md.append('```')
    md.append('')
    md.append('## 7 · 生成前须知（模型基线）')
    md.append('')
    md.append('- Seedance 单段建议 15–25 秒直出不拆段；跨镜头角色一致性约 80–90%，多镜头精度会下降。')
    md.append('- 模型默认 seedance 2.5；不可用时切 2.0 fast（单段上限 15 秒）须重新确认，不得静默替换。')
    md.append('- 实际生成须确认账号已开通视频创作权限与额度。')
    md.append('- 豆包生成带平台强制水印，不可去除，发布层面接受或另选通道。')
    md.append('')
    md.append('## 8 · 交付前自查（kit 第 6 节）')
    md.append('')
    for item in self_check:
        md.append('- [' + ('x' if item['pass'] else ' ') + '] ' + item['label']
                  + ((' — ' + item['note']) if item.get('note') else ''))
    md.append('')
    md.append('## 9 · 合规扫描与待确认')
    md.append('')
    if warnings:
        for w in warnings:
            md.append('- ⚠ ' + w['where'] + '：' + w['term'] + '（改写方向：' + w['hint'] + '）')
    else:
        md.append('- 未发现绝对化 / 功效 / 虚假背书类违规词。')
    if inp.get('unknowns'):
        md.append('')
        md.append('待人工补充（AI 标注）：')
        for u in inp['unknowns']:
            md.append('- ' + str(u))
    md.append('')

    return {
        'markdown': '\n'.join(md),
        'plan': plan,
        'scriptRows': script_rows,
        'storyRows': story_rows,
        'shotTexts': shot_texts,
        'shotCards': shot_cards,
        'shotB': shot_b,
        'subtitlesText': subtitles_text,
        'abText': ab_text,
        'closingText': closing_text,
        'selfCheck': self_check,
        'warnings': warnings,
        'wordProblems': word_problems,
        'usedDefault': used_default,
        'zhMissing': zh_missing,
        'actions': actions,
    }
