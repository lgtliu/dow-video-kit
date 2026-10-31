# -*- coding: utf-8 -*-
"""Dow 便捷出片 Web 版 · FastAPI 后端

启动：python app.py  或  python -m uvicorn app:app --host 127.0.0.1 --port 8787
安全约定：API Key 仅存浏览器 localStorage，随请求传入后在内存中转发给所选服务商，
不写入服务器文件、不打印日志、不在任何响应中回显。
"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import ai_client
import generator

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / 'static'

app = FastAPI(title='Dow 便捷出片 Web 版', docs_url=None, redoc_url=None)


def err(status_code, message):
    return JSONResponse(status_code=status_code, content={'ok': False, 'error': message})


@app.get('/')
def index():
    return FileResponse(STATIC_DIR / 'index.html')


app.mount('/static', StaticFiles(directory=STATIC_DIR), name='static')


async def _json_body(req: Request):
    try:
        data = await req.json()
    except Exception:
        return None
    return data if isinstance(data, dict) else None


# ------------------------------------------------------- 确定性生成 ----

@app.post('/api/generate')
async def api_generate(req: Request):
    data = await _json_body(req)
    if data is None:
        return err(400, '请求体不是合法 JSON')

    product = str(data.get('product') or '').strip()
    points = [p for p in (data.get('points') or []) if str(p or '').strip()]
    if not product:
        return err(400, '请填写产品名（必填）')
    if not points:
        return err(400, '请至少填写 1 条卖点')

    try:
        result = generator.build_all(data)
    except Exception as e:  # 组装逻辑异常不应泄露堆栈给页面
        return err(500, '生成失败：' + str(e))
    return {'ok': True, 'result': result}


# ------------------------------------------------------- AI 看图补齐 ----

@app.post('/api/ai/fill')
async def api_ai_fill(req: Request):
    data = await _json_body(req)
    if data is None:
        return err(400, '请求体不是合法 JSON')

    endpoint = str(data.get('endpoint') or '').strip()
    key = str(data.get('apikey') or '').strip()
    model = str(data.get('model') or '').strip()
    product = str(data.get('product') or '').strip()
    image = str(data.get('image') or '').strip()

    if not product:
        return err(400, '请先填写产品名（必填）')
    if not endpoint or not key or not model:
        return err(400, '尚未配置 API：请先到「设置」填写 API 地址 / Key / 模型，并可一键测试连通性')
    if image and not image.startswith('data:image/'):
        return err(400, '图片格式不正确，请重新上传商品图')

    try:
        result = ai_client.call_vision(endpoint, key, model, image, product)
    except ai_client.AIError as e:
        return JSONResponse(status_code=502, content={'ok': False, 'error': str(e)})
    except Exception as e:
        return err(500, 'AI 调用异常：' + str(e))
    return {'ok': True, 'data': result}


# ------------------------------------------------------- 连接测试 ----

@app.post('/api/ai/test')
async def api_ai_test(req: Request):
    data = await _json_body(req)
    if data is None:
        return err(400, '请求体不是合法 JSON')

    endpoint = str(data.get('endpoint') or '').strip()
    key = str(data.get('apikey') or '').strip()
    model = str(data.get('model') or '').strip()

    try:
        message = ai_client.test_connection(endpoint, key, model)
    except ai_client.AIError as e:
        return JSONResponse(status_code=502, content={'ok': False, 'error': str(e)})
    except Exception as e:
        return err(500, '连接测试异常：' + str(e))
    return {'ok': True, 'message': message}


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host='127.0.0.1', port=8787)
