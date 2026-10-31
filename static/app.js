/* Dow 便捷出片 Web 版 · 前端逻辑
 * 前端只负责展示与交互；台词/分镜/提示词/字幕/合规/自查全部由 Python 后端确定性组装。
 */
(function () {
  'use strict';

  function $(id) { return document.getElementById(id); }
  function val(id) { return $(id).value.trim(); }
  function setVal(id, v) { if (v) $(id).value = v; }
  function setHidden(el, hidden) { el.classList.toggle('hidden', hidden); }

  function toast(msg) {
    var t = $('toast');
    t.textContent = msg;
    t.style.opacity = 1;
    clearTimeout(t._timer);
    t._timer = setTimeout(function () { t.style.opacity = 0; }, 1800);
  }

  async function postJSON(url, body) {
    var resp;
    try {
      resp = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
    } catch (e) {
      throw new Error('无法连接本机后端：' + e.message);
    }
    var data = null;
    try { data = await resp.json(); } catch (e) { /* ignore */ }
    if (!resp.ok || !data || data.ok === false) {
      throw new Error((data && data.error) || ('请求失败（HTTP ' + resp.status + '）'));
    }
    return data;
  }

  /* ---------- Tab 切换 ---------- */
  document.querySelectorAll('.tab').forEach(function (btn) {
    btn.addEventListener('click', function () {
      document.querySelectorAll('.tab').forEach(function (b) { b.classList.remove('active'); });
      btn.classList.add('active');
      setHidden($('tab-gen'), btn.dataset.tab !== 'gen');
      setHidden($('tab-settings'), btn.dataset.tab !== 'settings');
    });
  });

  /* ---------- 设置页：API 配置（Key 仅存浏览器 localStorage） ---------- */
  var PRESETS = [
    { name: '自定义', endpoint: '' },
    { name: 'OpenAI', endpoint: 'https://api.openai.com/v1/chat/completions' },
    { name: '火山方舟（豆包）', endpoint: 'https://ark.cn-beijing.volces.com/api/v3/chat/completions' },
    { name: '阿里百炼（通义千问 Qwen）', endpoint: 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions' },
    { name: 'DeepSeek', endpoint: 'https://api.deepseek.com/v1/chat/completions' },
    { name: '智谱（GLM）', endpoint: 'https://open.bigmodel.cn/api/paas/v4/chat/completions' }
  ];

  (function initSettings() {
    var sel = $('preset');
    PRESETS.forEach(function (p) {
      var opt = document.createElement('option');
      opt.value = p.endpoint;
      opt.textContent = p.name;
      sel.appendChild(opt);
    });
    sel.addEventListener('change', function () {
      if (this.value) {
        $('endpoint').value = this.value;
        localStorage.setItem('dow_endpoint', this.value);
      }
    });
    ['endpoint', 'apikey', 'model'].forEach(function (id) {
      $(id).value = localStorage.getItem('dow_' + id) || '';
      $(id).addEventListener('change', function () {
        localStorage.setItem('dow_' + id, $(id).value);
      });
    });
  })();

  $('test').addEventListener('click', async function () {
    var body = { endpoint: val('endpoint'), apikey: val('apikey'), model: val('model') };
    var status = $('testStatus');
    if (!body.endpoint || !body.apikey || !body.model) {
      status.className = 'status error';
      status.textContent = '请先填写 API 地址 / Key / 模型';
      return;
    }
    this.disabled = true;
    status.className = 'status';
    status.textContent = '测试中…';
    try {
      var r = await postJSON('/api/ai/test', body);
      status.className = 'status ok';
      status.textContent = r.message;
    } catch (e) {
      status.className = 'status error';
      status.textContent = e.message;
    } finally {
      this.disabled = false;
    }
  });

  /* ---------- 生成页：图片（本地压缩，仅随 AI 请求发送） ---------- */
  var imageDataURL = '';

  $('image').addEventListener('change', async function () {
    var f = this.files[0];
    var prev = $('imgPrev');
    if (!f) { imageDataURL = ''; prev.style.display = 'none'; setHidden($('imgClear'), true); return; }
    try {
      imageDataURL = await readImage(f);
      prev.src = imageDataURL;
      prev.style.display = 'block';
      setHidden($('imgClear'), false);
    } catch (e) {
      imageDataURL = '';
      prev.style.display = 'none';
      setHidden($('imgClear'), true);
      toast(e.message || '图片读取失败');
    }
  });

  $('imgClear').addEventListener('click', function () {
    imageDataURL = '';
    $('image').value = '';
    $('imgPrev').style.display = 'none';
    setHidden($('imgClear'), true);
  });

  function readImage(file) {
    return new Promise(function (resolve, reject) {
      var reader = new FileReader();
      reader.onerror = function () { reject(new Error('图片读取失败')); };
      reader.onload = function () {
        var img = new Image();
        img.onerror = function () { reject(new Error('图片解析失败')); };
        img.onload = function () {
          var max = 1024;
          var scale = Math.min(1, max / Math.max(img.width, img.height));
          if (scale === 1) { resolve(reader.result); return; }
          var c = document.createElement('canvas');
          c.width = Math.round(img.width * scale);
          c.height = Math.round(img.height * scale);
          c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
          resolve(c.toDataURL('image/jpeg', 0.85));
        };
        img.src = reader.result;
      };
      reader.readAsDataURL(file);
    });
  }

  /* ---------- AI 补齐（看图 / 无图模式） ---------- */
  function aiZhToFields(z) {
    var out = {};
    if (!z) return out;
    var keys = ['hook', 'seed1', 'seed2', 'proof', 'action', 'hookB'];
    if (Array.isArray(z)) {
      keys.forEach(function (k, i) {
        var v = String(z[i] || '').trim();
        if (v) out['zh' + k.charAt(0).toUpperCase() + k.slice(1)] = v;
      });
      return out;
    }
    if (typeof z === 'object') {
      keys.forEach(function (k) {
        var v = String(z[k] || '').trim();
        if (v) out['zh' + k.charAt(0).toUpperCase() + k.slice(1)] = v;
      });
    }
    return out;
  }

  function toPoints(v) {
    var clean = function (p) { return String(p || '').replace(/^\d+[.)、]\s*/, '').trim(); };
    var arr = Array.isArray(v) ? v : (typeof v === 'string' ? v.split(/\r?\n|;/) : []);
    return arr.map(clean).filter(Boolean);
  }

  function applyAIResult(r) {
    if (String(r.productDesc || '').trim()) setVal('productDesc', String(r.productDesc).trim());
    var pts = toPoints(r.points);
    if (pts.length) $('points').value = pts.slice(0, 3).join('\n');
    if (r.audience) setVal('audience', String(r.audience));
    if (r.setting === 'kitchen') $('setting').value = 'kitchen';
    else if (r.setting === 'bedroom') $('setting').value = 'bedroom';
    if (r.scriptType === 'unboxing') $('scriptType').value = 'unboxing';
    else if (r.scriptType === 'demo') $('scriptType').value = 'demo';
    if (Array.isArray(r.actions)) {
      var acts = r.actions.map(function (a) { return String(a || '').trim(); }).filter(Boolean).slice(0, 4);
      if (acts.length) $('actionsText').value = acts.join('\n');
    }
    if (r.hook) setVal('hook', String(r.hook));
    if (r.seed1) setVal('seed1', String(r.seed1));
    if (r.seed2) setVal('seed2', String(r.seed2));
    if (r.proof) setVal('proof', String(r.proof).replace(/\[SALES\]/g, val('soldCount') || '[SALES]'));
    if (r.action) setVal('action', String(r.action));
    if (typeof r.hookB === 'string' && r.hookB) setVal('hookB', r.hookB);
    else if (r.hookB && typeof r.hookB === 'object') {
      if (r.hookB.line) setVal('hookB', String(r.hookB.line));
      if (r.hookB.action) setVal('hookBAction', String(r.hookB.action));
    }
    Object.keys(aiZhToFields(r.zh)).forEach(function (k) { setVal(k, aiZhToFields(r.zh)[k]); });
    if (r.caption) setVal('caption', String(r.caption));
    if (r.hashtags) setVal('hashtags', Array.isArray(r.hashtags) ? r.hashtags.join(' ') : String(r.hashtags));

    var box = $('unknowns');
    var unknowns = Array.isArray(r.unknowns) ? r.unknowns.map(String) : [];
    lastUnknowns = unknowns;
    if (unknowns.length) {
      box.innerHTML = '<b>图上无法确认，请人工补充：</b><ul><li>'
        + unknowns.map(function (u) { return String(u).replace(/[<>&]/g, ''); }).join('</li><li>')
        + '</li></ul>';
      setHidden(box, false);
    } else {
      setHidden(box, true);
    }
  }

  var lastUnknowns = [];

  $('ai').addEventListener('click', async function () {
    var product = val('product');
    var endpoint = val('endpoint');
    var key = val('apikey');
    var model = val('model');
    var status = $('aiStatus');

    if (!product) { toast('请先填写产品名'); return; }
    if (!endpoint || !key || !model) {
      status.className = 'status error';
      status.textContent = '尚未配置 API：请先到「设置」填写 API 地址 / Key / 模型，并可一键测试连通性';
      toast('尚未配置 API，请先到「设置」页配置');
      return;
    }

    this.disabled = true;
    status.className = 'status';
    status.textContent = imageDataURL ? 'AI 识别中…' : '无图模式：AI 起草卖点与台词…';
    try {
      var r = await postJSON('/api/ai/fill', {
        endpoint: endpoint, apikey: key, model: model,
        product: product, image: imageDataURL
      });
      applyAIResult(r.data);
      var ok = generate();
      status.className = 'status ok';
      status.textContent = ok
        ? (imageDataURL ? 'AI 补齐完成，已自动生成出片包。' : 'AI 起草完成（无图，外观与参数请人工核实），已自动生成出片包。')
        : 'AI 已返回，但缺少卖点，请补充卖点后生成。';
    } catch (e) {
      status.className = 'status error';
      status.textContent = e.message;
      toast('AI 调用失败');
    } finally {
      this.disabled = false;
    }
  });

  /* ---------- 组装：全部交给 Python 后端 ---------- */
  function collect() {
    return {
      product: val('product'),
      points: $('points').value.split(/\r?\n/).map(function (s) { return s.trim(); }).filter(Boolean),
      productDesc: val('productDesc'),
      audience: val('audience'),
      duration: parseInt(val('duration'), 10) || 20,
      setting: $('setting').value,
      scriptType: $('scriptType').value,
      language: $('language').value === 'bi' ? '英文口播 + 中英双语字幕' : '英文口播 + 英文字幕',
      bilingual: $('language').value === 'bi',
      soldCount: val('soldCount'),
      hook: val('hook'), seed1: val('seed1'), seed2: val('seed2'),
      proof: val('proof'), action: val('action'),
      hookB: val('hookB'), hookBAction: val('hookBAction'),
      caption: val('caption'), hashtags: val('hashtags'),
      zh: {
        hook: val('zhHook'), seed1: val('zhSeed1'), seed2: val('zhSeed2'),
        proof: val('zhProof'), action: val('zhAction'), hookB: val('zhHookB')
      },
      actions: $('actionsText').value.split(/\r?\n/).map(function (s) { return s.trim(); }).filter(Boolean),
      hasImage: !!imageDataURL,
      unknowns: lastUnknowns
    };
  }

  var lastResult = null;
  var lastInput = null;

  function generate() {
    var input = collect();
    if (!input.product) { toast('请先填写产品名'); return false; }
    if (!input.points.length) { toast('请至少填写 1 条卖点'); return false; }

    var btn = $('gen');
    btn.disabled = true;
    postJSON('/api/generate', input).then(function (r) {
      lastResult = r.result;
      lastInput = input;
      renderResult(r.result, input);
      toast('已生成：' + r.result.plan.duration + 's / ' + r.result.plan.segs.length + ' 镜头');
    }).catch(function (e) {
      toast(e.message);
    }).finally(function () {
      btn.disabled = false;
    });
    return true;
  }

  $('gen').addEventListener('click', generate);

  /* ---------- 结果渲染 ---------- */
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  function table(headers, rows) {
    var t = el('table', 'data');
    var thead = el('thead');
    var trh = el('tr');
    headers.forEach(function (h) { trh.appendChild(el('th', null, h)); });
    thead.appendChild(trh);
    t.appendChild(thead);
    var tbody = el('tbody');
    rows.forEach(function (cells) {
      var tr = el('tr');
      cells.forEach(function (c) { tr.appendChild(el('td', null, c == null ? '' : String(c))); });
      tbody.appendChild(tr);
    });
    t.appendChild(tbody);
    return t;
  }

  function section(title, tag) {
    var sec = el('div', 'sec');
    var h = el('h4');
    h.appendChild(document.createTextNode(title));
    if (tag) h.appendChild(el('span', 'tag', tag));
    sec.appendChild(h);
    return sec;
  }

  function copyBtn(getText) {
    var b = el('button', 'small', '复制');
    b.type = 'button';
    b.addEventListener('click', function () {
      copyText(getText()).then(function () { toast('已复制'); })
        .catch(function () { toast('复制失败，请手动选择文本复制'); });
    });
    return b;
  }

  function renderResult(res, input) {
    var out = $('result');
    out.className = '';
    out.innerHTML = '';
    $('planInfo').textContent = res.plan.duration + 's · ' + res.plan.segs.length + ' 镜头'
      + (input.points.length > 3 ? ' · 卖点仅取前 3 条' : '')
      + (input.duration < 15 || input.duration > 25 ? ' · 时长已收敛到 15–25s' : '');

    // 0 输入概览
    var s0 = section('输入概览');
    s0.appendChild(table(['项', '值'], [
      ['产品名', input.product],
      ['卖点', input.points.map(function (p, i) { return (i + 1) + '. ' + p; }).join('；')],
      ['目标受众', input.audience || 'US TikTok shoppers, 25–45'],
      ['时长', res.plan.duration + 's → ' + res.plan.segs.length + ' 镜头'],
      ['脚本类型', input.scriptType === 'unboxing' ? '开箱收礼型' : '把玩展示型'],
      ['参考图', input.hasImage ? '已上传' : '未提供（外观需人工补充）']
    ]));
    out.appendChild(s0);

    // 1 口播脚本 T1
    var s1 = section('1 · 口播脚本（T1）');
    s1.appendChild(table(['段落', '时间', '英文台词', '中文注释'],
      res.scriptRows.map(function (r) { return [r.role, r.time, r.en, r.zh]; })));
    out.appendChild(s1);

    // 2 分镜表 T2
    var s2 = section('2 · 分镜表（T2）');
    s2.appendChild(table(['Shot', '时间', '画面动作', '运镜（量化）', '对应台词'],
      res.storyRows.map(function (r) { return [r.n, r.time, r.action, r.camera, r.line]; })));
    out.appendChild(s2);

    // 3 逐镜头提示词 T3
    var s3 = section('3 · 逐镜头 Seedance 提示词（T3）', '每块独立完整，可直接复制提交');
    res.shotCards.forEach(function (shot) {
      var card = el('div', 'shot-card');
      var head = el('div', 'shot-head');
      var t = el('span', null, 'Shot ' + shot.n + ' · ' + shot.role);
      t.appendChild(el('span', 't', '（' + shot.time + '）'));
      head.appendChild(t);
      head.appendChild(copyBtn(function () { return shot.text; }));
      card.appendChild(head);
      var pre = el('pre', 'block', shot.text);
      card.appendChild(pre);
      s3.appendChild(card);
    });
    out.appendChild(s3);

    // B 版 Shot 1
    var sb = section('B 版 Shot 1（痛点钩，完整可直接复制）', '其余镜头块完全复用');
    var cardB = el('div', 'shot-card');
    var headB = el('div', 'shot-head');
    headB.appendChild(el('span', null, 'Shot 1 · B 版'));
    headB.appendChild(copyBtn(function () { return res.shotB; }));
    cardB.appendChild(headB);
    cardB.appendChild(el('pre', 'block', res.shotB));
    sb.appendChild(cardB);
    out.appendChild(sb);

    // 4 字幕与发布文案 T4
    var s4 = section('4 · 字幕与发布文案（T4）');
    s4.appendChild(copyBtn(function () { return res.subtitlesText; }));
    s4.appendChild(el('pre', 'block', res.subtitlesText));
    out.appendChild(s4);

    // 5 A/B 钩子 T5
    var s5 = section('5 · A/B 开头钩子（T5）');
    s5.appendChild(copyBtn(function () { return res.abText; }));
    s5.appendChild(el('pre', 'block', res.abText));
    out.appendChild(s5);

    // 6 结尾重申
    var s6 = section('6 · 结尾重申', '每套提交末尾再写一遍');
    s6.appendChild(copyBtn(function () { return res.closingText; }));
    s6.appendChild(el('pre', 'block', res.closingText));
    out.appendChild(s6);

    // 7 交付自查
    var passCount = res.selfCheck.filter(function (i) { return i.pass; }).length;
    var s7 = section('交付自查', passCount + '/' + res.selfCheck.length + ' 通过；未过项标红并给原因');
    var ul = el('ul', 'check-list');
    res.selfCheck.forEach(function (item) {
      var li = el('li', item.pass ? 'pass' : 'fail');
      li.appendChild(el('span', 'mark', item.pass ? '✓' : '✗'));
      li.appendChild(document.createTextNode(item.label));
      li.appendChild(el('span', 'note', item.note ? ' — ' + item.note : ''));
      ul.appendChild(li);
    });
    s7.appendChild(ul);
    out.appendChild(s7);

    // 8 合规扫描
    var s8 = section('合规扫描', res.warnings.length ? res.warnings.length + ' 处待改写' : '未发现违规词');
    if (res.warnings.length) {
      var wl = el('ul', 'wlist');
      res.warnings.forEach(function (w) {
        var li = el('li');
        var b = el('b', null, '⚠ ' + w.where + '：「' + w.term + '」');
        li.appendChild(b);
        li.appendChild(el('span', 'dir', '改写方向：' + w.hint));
        wl.appendChild(li);
      });
      s8.appendChild(wl);
    } else {
      s8.appendChild(el('div', 'all-ok', '未发现绝对化 / 功效 / 虚假背书类违规词。'));
    }
    if (input.unknowns && input.unknowns.length) {
      var ub = el('div', 'warn-box');
      ub.style.marginTop = '10px';
      ub.innerHTML = '<b>待人工补充（AI 标注）：</b><ul><li>'
        + input.unknowns.map(function (u) { return String(u).replace(/[<>&]/g, ''); }).join('</li><li>')
        + '</li></ul>';
      s8.appendChild(ub);
    }
    out.appendChild(s8);

    // 完整 Markdown
    var s9 = section('完整出片包（Markdown）', '可直接粘贴到笔记 / 交给 AI 视频工具');
    s9.appendChild(el('pre', 'block tall', res.markdown));
    out.appendChild(s9);

    out.scrollTop = 0;
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  /* ---------- 复制与下载 ---------- */
  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) return navigator.clipboard.writeText(text);
    return new Promise(function (resolve, reject) {
      var ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      try {
        document.execCommand('copy') ? resolve() : reject(new Error('copy failed'));
      } catch (e) {
        reject(e);
      }
      document.body.removeChild(ta);
    });
  }

  $('copyAll').addEventListener('click', function () {
    if (!lastResult) { toast('请先生成'); return; }
    copyText(lastResult.markdown).then(function () { toast('已复制全部 Markdown'); })
      .catch(function () { toast('复制失败，请手动复制'); });
  });

  $('dl').addEventListener('click', function () {
    if (!lastResult) { toast('请先生成'); return; }
    var product = (lastInput && lastInput.product) || 'output';
    var slug = product.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'output';
    var blob = new Blob([lastResult.markdown], { type: 'text/markdown;charset=utf-8' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'dow-' + slug + '.md';
    a.click();
    URL.revokeObjectURL(a.href);
    toast('已下载 dow-' + slug + '.md');
  });
})();
