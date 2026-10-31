# -*- coding: utf-8 -*-
"""OpenAI 兼容 Chat Completions 调用封装（移植自 miniprogram/utils/ai.js）

安全约定：API Key 只在内存中使用与转发，不写入文件、不写日志、不在响应中回显。
"""

import json
import re
import socket
import urllib.error
import urllib.request

SYSTEM_PROMPT = '\n'.join([
    '你是 Dow，出海带货短视频策划。用户可能给你一张商品图和商品名。只依据图上可见信息与品类常识推断；没有图时不得编造外观。输出严格 JSON（不要输出任何其他文字）：',
    '{',
    '  "productDesc": "英文。一句话，逐项描述图中可见外观（颜色/材质/图案/形状/细节）；只写图上能确认的，禁止编造；无图返回空字符串",',
    '  "points": ["英文卖点，1-3条，仅基于可见特征与品类常识，不涉及功效承诺；无图时只写品类通用卖点并在 unknowns 标注待核实"],',
    '  "audience": "英文目标人群，如 US TikTok shoppers, 25-45, new parents",',
    '  "setting": "bedroom 或 kitchen，按品类最常见使用场景二选一",',
    '  "scriptType": "demo 或 unboxing；送礼/礼盒/毛绒/香氛等适合 unboxing，其余 demo",',
    '  "actions": ["英文动作 1（Hook）", "英文动作 2（Seed 1）", "英文动作 3（Seed 2）", "英文动作 4（Proof+Action）"],',
    '  "hook": "英文 Hook 台词，夸张表情 + 具体数字或反常识，2 秒内落地",',
    '  "seed1": "英文，核心卖点 + 真实使用场景",',
    '  "seed2": "英文，第二卖点或场景补充",',
    '  "proof": "英文信任背书句。销量数字禁止编造，一律用占位符 [SALES]，如 Over [SALES] sold, and the reviews are honestly lovely.",',
    '  "action": "英文，一句话购买指令",',
    '  "zh": {"hook": "中文注释/字幕，≤20字", "seed1": "...", "seed2": "...", "proof": "...", "action": "...", "hookB": "..."},',
    '  "hookB": {"line": "英文备选钩子，痛点向", "action": "英文，Shot 1 表情动作差异描述"},',
    '  "caption": "英文发布文案一句话",',
    '  "hashtags": "3-5 个英文 hashtag",',
    '  "unknowns": ["中文，列出图上无法确认或需用户补充的信息，如材质/尺寸/价格/功能参数/真实销量"]',
    '}',
    'actions 固定 4 条，按 Hook / Seed 1 / Seed 2 / Proof+Action 顺序；unboxing 按拆快递袋→取布袋→捧出产品→把玩顺序；每条只写简单手部动作，避开转动/翻面/多指精细操作。',
    '硬性规则：每条英文台词单独成句 4-12 个单词；允许口语碎词 just/basically/you know；禁止 best/#1/guaranteed/perfect/100%/cure/treat/prevent/FDA 等绝对化、功效或背书用语；禁止抗菌/美白/减肥/生发/防晒/见效等功效词；禁止 certified/award-winning/dermatologist 等无依据背书；禁止编造认证与销量；避免中式英语；动作描述避开转动/翻面/多指精细操作；英文台词中不得出现中文。',
])

PRESETS = [
    {'name': '自定义', 'endpoint': ''},
    {'name': 'OpenAI', 'endpoint': 'https://api.openai.com/v1/chat/completions'},
    {'name': '火山方舟（豆包）', 'endpoint': 'https://ark.cn-beijing.volces.com/api/v3/chat/completions'},
    {'name': '阿里百炼（通义千问 Qwen）', 'endpoint': 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions'},
    {'name': 'DeepSeek', 'endpoint': 'https://api.deepseek.com/v1/chat/completions'},
    {'name': '智谱（GLM）', 'endpoint': 'https://open.bigmodel.cn/api/paas/v4/chat/completions'},
]


class AIError(Exception):
    """带中文诊断信息的 AI 调用错误。"""


def normalize_endpoint(endpoint):
    """地址自动补全：确保以 /chat/completions 结尾"""
    url = str(endpoint or '').strip().rstrip('/')
    if url and not re.search(r'/chat/completions$', url):
        url += '/chat/completions'
    return url


def extract_json(text):
    raw = str(text or '').strip()
    try:
        return json.loads(raw)
    except Exception:
        pass
    fenced = re.search(r'```(?:json)?\s*([\s\S]*?)```', raw, re.I)
    if fenced:
        try:
            return json.loads(fenced.group(1).strip())
        except Exception:
            pass
    m = re.search(r'\{[\s\S]*\}', raw)
    if not m:
        raise AIError('AI 返回内容不是 JSON')
    try:
        return json.loads(m.group(0))
    except Exception as e:
        raise AIError('AI 返回内容不是 JSON（解析失败：' + str(e) + '）')


def build_request_body(model, data_url, product_name, with_response_format):
    text = '商品名：' + product_name + '。' + (
        '请看商品图，按规则输出 JSON。' if data_url
        else '没有提供商品图：productDesc 返回空字符串，unknowns 列出外观/材质/尺寸等待确认项。按规则输出 JSON。')
    if data_url:
        user_content = [
            {'type': 'text', 'text': text},
            {'type': 'image_url', 'image_url': {'url': data_url}},
        ]
    else:
        user_content = text
    body = {
        'model': model,
        'temperature': 0.7,
        'messages': [
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': user_content},
        ],
    }
    if with_response_format:
        body['response_format'] = {'type': 'json_object'}
    return body


def friendly_error(status_code, endpoint, data):
    if status_code == 404:
        hint = '（地址不存在：已自动补全 /chat/completions 仍 404，请核对服务商文档里的完整请求地址）'
    elif status_code in (401, 403):
        hint = '（鉴权失败：检查 API Key）'
    elif status_code == 429:
        hint = '（请求被限流或账户欠费）'
    elif status_code >= 500:
        hint = '（服务商服务异常，稍后重试）'
    else:
        hint = ''
    try:
        brief = json.dumps(data, ensure_ascii=False)[:160]
    except Exception:
        brief = str(data)[:160]
    return 'API 错误 ' + str(status_code) + hint + '\n请求端点：' + endpoint + '\n' + brief


def _post_json(url, key, body, timeout):
    """底层请求：返回 (statusCode, data)；仅网络层失败时抛 AIError。"""
    data_bytes = json.dumps(body, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(url, data=data_bytes, method='POST')
    req.add_header('Content-Type', 'application/json')
    req.add_header('Authorization', 'Bearer ' + key)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode('utf-8', 'replace')
            status = resp.status
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8', 'replace')
        status = e.code
    except urllib.error.URLError as e:
        reason = str(getattr(e, 'reason', e) or e)
        if isinstance(getattr(e, 'reason', None), socket.timeout) or 'timed out' in reason.lower():
            raise AIError('请求超时：' + reason + '\n网络不通或服务商响应慢，请检查网络后重试。')
        if re.search(r'ssl|tls|certificate|证书', reason, re.I):
            raise AIError('HTTPS 证书校验失败：' + reason + '\n请确认服务商证书有效或更换网络后重试。')
        raise AIError('网络请求失败：' + reason + '\n请检查 API 地址与网络连通性。')
    except socket.timeout:
        raise AIError('请求超时：连接在 ' + str(timeout) + ' 秒内未完成\n网络不通或服务商响应慢，请检查网络后重试。')
    try:
        data = json.loads(raw)
    except Exception:
        data = raw
    return status, data


def content_of(payload):
    p = payload
    if isinstance(p, str):
        try:
            p = json.loads(p)
        except Exception:
            pass
    content = None
    try:
        content = p['choices'][0]['message']['content']
    except Exception:
        return None
    if isinstance(content, list):
        content = ''.join(
            ((part.get('text') or '') if isinstance(part, dict) else str(part))
            for part in content
        )
    return content


def call_vision(endpoint, key, model, data_url, product_name):
    """视觉补齐调用：带 response_format 降级重试，成功返回解析后的 JSON。"""
    if not endpoint or not key or not model:
        raise AIError('请先填写 API 地址 / Key / 模型')
    if not product_name:
        raise AIError('请先填写产品名（必填）')
    url = normalize_endpoint(endpoint)
    status, data = _post_json(url, key, build_request_body(model, data_url, product_name, True), 60)
    if status in (400, 422):
        # 部分服务商不支持 response_format，降级重试
        status, data = _post_json(url, key, build_request_body(model, data_url, product_name, False), 60)
    if status < 200 or status >= 300:
        raise AIError(friendly_error(status, endpoint, data))
    content = content_of(data)
    if not content:
        raise AIError('API 返回结构异常（无 choices.content）')
    return extract_json(content)


def test_connection(endpoint, key, model):
    """连接测试：发送最小请求，成功返回提示语。"""
    if not endpoint or not key or not model:
        raise AIError('请先填写 API 地址 / Key / 模型')
    status, data = _post_json(normalize_endpoint(endpoint), key, {
        'model': model,
        'max_tokens': 5,
        'messages': [{'role': 'user', 'content': 'Hi'}],
    }, 30)
    if status < 200 or status >= 300:
        raise AIError(friendly_error(status, endpoint, data))
    content = content_of(data)
    if not content:
        raise AIError('已连通但响应结构异常，请确认是 OpenAI 兼容 /chat/completions 端点')
    return '连接成功，模型「' + model + '」已正常响应'
