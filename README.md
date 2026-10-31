# Dow 便捷出片 · Python Web 版

「带货短视频出片包生成器」的 Python 后端 + 网页前端实现，功能与技能包内的小程序 / 单文件网页版对齐。从最少输入产出可直接提交给 Seedance 等 AI 视频工具的「出片包」：四段式口播脚本、分镜表、逐镜头 Seedance 提示词、时间轴字幕、A/B 钩子、合规扫描与交付自查。

## 启动

```bash
cd python_web
pip install -r requirements.txt
python app.py            # 或：python -m uvicorn app:app --host 127.0.0.1 --port 8787
```

浏览器打开 <http://127.0.0.1:8787> 即可使用。

## 使用流程

1. **设置**页：选服务商预设（OpenAI / 火山方舟豆包 / 阿里百炼通义 / DeepSeek / 智谱 / 自定义中转）→ 填 API 地址、API Key、模型名（看图需视觉模型，如 `qwen-vl-max` / `gpt-4o`）→ 点「测试连接」变绿。
2. **生成**页：上传商品图（可选）+ 填产品名与 1–3 条卖点 → 点「AI 补齐」（无图也可用，AI 只起草并标注待核实项）→ 自动生成出片包；也可完全手动填写后直接「生成出片包」。
3. 结果区分区展示 T1 口播脚本 / T2 分镜表 / T3 逐镜头提示词（逐块复制）/ B 版 Shot 1 / T4 字幕文案 / T5 A/B 钩子 / 结尾重申 / 交付自查 / 合规扫描，支持一键复制全部 Markdown 与下载 .md。

## 安全约定

- API Key 只保存在你浏览器的 localStorage，随请求发给本机 Python 后端用于转发，不写入服务器文件与日志，不回显完整 Key，也不会进入任何仓库。
- 商品图仅在点击「AI 补齐」时随请求发送给你自己配置的 API 服务商。

## 目录结构

```
python_web/
├── app.py            # FastAPI 入口：静态托管 + /api/generate + /api/ai/fill + /api/ai/test
├── generator.py      # 确定性生成核心（台词/分镜/提示词/字幕/合规/自查，移植自 generator.js）
├── ai_client.py      # OpenAI 兼容调用封装（vision + 中文报错，移植自 ai.js）
├── requirements.txt
└── static/           # 无构建步骤的原生前端（index.html / app.js / style.css）
```

确定性组装逻辑（脚本、分镜、提示词、字幕、合规、自查）全部在 Python 端实现，作为唯一事实来源；前端只负责展示与交互。

## 说明

- 时长 15–25s：15–18s 自动 3 镜头，19–25s 自动 4 镜头（Seed 拆 2 镜）。
- 台词留空时生成占位句，自查会标红提示；Proof 段销量一律用 `[SALES]` 占位，发布前替换真实数据。
- 合规词库与自查仅作创作辅助，不构成法律意见；发布合规以目标平台规则与当地法规为准。
