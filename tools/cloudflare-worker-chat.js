// Cloudflare Worker — ARK KB Chat (MiniMax-M2.7 via Anthropic-compatible API)
// 部署：https://dash.cloudflare.com → Workers & Pages → white-recipe-de08ark-kb-search → Edit Code
// 替换整个文件 → Save and Deploy
//
// Secrets (Settings → Variables → Encrypted):
//   MINIMAX_API_KEY      Token Plan API Key (从 platform.minimaxi.com/subscribe/token-plan 拿)
//   MINIMAX_BASE_URL     可选，默认 https://api.minimaxi.com/anthropic
//
// 跟旧 Worker 的区别:
//   - 旧: 智谱 BigModel glm-4.7-flash，thinking 模型被 max_tokens 卡住
//   - 新: MiniMax-M2.7，标准 chat 模型，不 thinking，
//         Anthropic 兼容协议（x-api-key + anthropic-version header）

const KB_BASE = 'https://arkie.cc.cd';   // GitHub Pages 部署的 KB 数据
const KB_FILES = [
  '活动公告.txt', '提案政策.txt', '工作室事务.txt', '常用话术.txt',
  '产品操作.txt', '常见FAQ.txt', '地址合约.txt', '最新动态.txt',
];
const KB_CACHE_TTL = 5 * 60 * 1000;       // 5 分钟刷一次（KB 改后最多 5 分钟可见）
let KB_CACHE = null;                       // { text, loadedAt }

async function loadKB() {
  const now = Date.now();
  if (KB_CACHE && (now - KB_CACHE.loadedAt) < KB_CACHE_TTL) return KB_CACHE.text;

  const parts = [];
  let okCount = 0;
  let failFiles = [];
  const promises = KB_FILES.map(async (file) => {
    try {
      const resp = await fetch(`${KB_BASE}/data/${file}?t=${now}`, {
        headers: { 'Cache-Control': 'no-cache' },
      });
      if (!resp.ok) throw new Error(`${file} HTTP ${resp.status}`);
      const text = await resp.text();
      okCount++;
      return `===== ${file} =====\n${text}`;
    } catch (e) {
      failFiles.push(`${file}(${e.message})`);
      return `[加载失败] ${file}: ${e.message}`;
    }
  });
  const results = await Promise.all(promises);
  const assembled = results.join('\n\n');

  KB_CACHE = { text: assembled, loadedAt: now };
  console.log(`[KB] 加载 ${okCount}/${KB_FILES.length} 个文件，${assembled.length} 字符`);
  if (failFiles.length > 0) console.error(`[KB] 加载失败: ${failFiles.join(', ')}`);
  return KB_CACHE.text;
}

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, x-api-key, anthropic-version',
};

function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json', ...CORS_HEADERS },
  });
}

export default {
  async fetch(request, env) {
    // CORS 预检
    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: CORS_HEADERS });
    }
    // 健康检查
    if (request.method === 'GET') {
      try {
        const kb = await loadKB();
        return jsonResponse({
          ok: true,
          provider: 'minimax-M2.7',
          kb_chars: kb.length,
          kb_files_loaded: KB_FILES.length,
          kb_cache_age_sec: KB_CACHE ? Math.floor((Date.now() - KB_CACHE.loadedAt) / 1000) : null,
          api_base: env.MINIMAX_BASE_URL || 'https://api.minimaxi.com/anthropic',
          has_api_key: !!env.MINIMAX_API_KEY,
        });
      } catch (e) {
        return jsonResponse({ ok: false, error: e.message }, 500);
      }
    }
    if (request.method !== 'POST') {
      return new Response('Method not allowed', { status: 405, headers: CORS_HEADERS });
    }

    // 特殊路由：POST /refresh — 验证密码后清空 KB 缓存
    const url = new URL(request.url);
    if (url.pathname === '/refresh') {
      let body;
      try { body = await request.json(); } catch { return jsonResponse({ error: 'Invalid JSON' }, 400); }
      const pw = body && body.password;
      // 优先用 env.REFRESH_PASSWORD；fallback 到内置硬编码（不推荐生产用）
      const expected = env.REFRESH_PASSWORD || 'arkie2026';
      if (!pw || pw !== expected) {
        return jsonResponse({ ok: false, error: '密码错误' }, 403);
      }
      KB_CACHE = null;
      console.log('[KB] 缓存已清空（手动刷新）');
      return jsonResponse({ ok: true, kb_cache_cleared: true });
    }

    // 解析 body
    let body;
    try { body = await request.json(); }
    catch { return jsonResponse({ error: 'Invalid JSON body' }, 400); }

    // 兼容模式：老接口 { question, contexts }
    let messages = body.messages;
    if (!Array.isArray(messages) && body.question) {
      messages = [{ role: 'user', content: body.question }];
    }
    if (!Array.isArray(messages) || messages.length === 0) {
      return jsonResponse({ error: 'Missing messages array or question string' }, 400);
    }

    // 检查 secret
    if (!env.MINIMAX_API_KEY) {
      return jsonResponse({ error: 'MINIMAX_API_KEY secret not configured. 在 Cloudflare Worker → Settings → Variables 配置。' }, 500);
    }

    // 加载 KB
    let kbText;
    try { kbText = await loadKB(); }
    catch (e) {
      return jsonResponse({ error: `KB load failed: ${e.message}` }, 502);
    }

    // 组装 system prompt
    const systemPrompt = `你是 ARK 项目客服知识库助手，负责帮助客服人员快速回答客户问题。

【铁律】
1. 严格基于下方「参考 KB」内容回答，绝对不要补充、推测、编造参考内容之外的 URL、地址、数字、政策细节。
2. 如果 KB 内容不包含答案所需信息，直接说"知识库暂无相关内容，建议转人工或参考最新公告"，不要硬凑。
3. 引用具体数字时，连带说出上下文（哪个提案、什么时间），便于客服核对。

【回答风格】
- 简洁专业，2-4 段，每段不超过 100 字
- 用列表/分点呈现比例、步骤、时间
- 末尾必须加一行："⚠️ 内容由 AI 生成，仅供参考。客服使用前请人工核对关键数字 / 地址。"
- 不要用"作为 AI 模型"等自我标签
- 直接回答，不要先说"好问题""我来帮您"等客套

【多轮对话】
- 客服可能追问细节（如"那 015 号提案呢""KPI 系数怎么算"），请基于对话上下文聚焦回答
- 客服切换话题时，自然衔接，不要硬绑回旧话题

【参考 KB】(共 ${kbText.length} 字符)

${kbText}`;

    // 转 Anthropic 兼容格式：messages 字段去掉 assistant 那轮空 content（容忍）
    const apiMessages = messages.map(m => ({
      role: m.role,
      content: typeof m.content === 'string' ? m.content : JSON.stringify(m.content),
    })).filter(m => m.content && m.content.trim());

    if (apiMessages.length === 0) {
      return jsonResponse({ error: 'Empty messages after cleanup' }, 400);
    }

    const apiBase = env.MINIMAX_BASE_URL || 'https://api.minimaxi.com/anthropic';

    try {
      const resp = await fetch(`${apiBase}/v1/messages`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-api-key': env.MINIMAX_API_KEY,
          'anthropic-version': '2023-06-01',
        },
        body: JSON.stringify({
          model: 'MiniMax-M2.7',
          system: systemPrompt,
          messages: apiMessages,
          max_tokens: 4000,
          temperature: 0.3,
        }),
        signal: AbortSignal.timeout(90 * 1000),
      });

      if (!resp.ok) {
        const errText = await resp.text();
        console.error(`[LLM] ${resp.status}: ${errText.slice(0, 500)}`);
        return jsonResponse({ error: `LLM ${resp.status}: ${errText.slice(0, 500)}` }, 502);
      }

      const data = await resp.json();
      // Anthropic 格式: content 是数组，取 type=text 的 text
      const textBlock = (data.content || []).find(c => c.type === 'text');
      const answer = textBlock?.text || '（模型无回复）';
      return jsonResponse({
        answer,
        usage: data.usage || null,
        kb_chars: kbText.length,
        model: 'MiniMax-M2.7',
        stop_reason: data.stop_reason,
      });
    } catch (e) {
      console.error(`[LLM] Call failed: ${e.message}`);
      return jsonResponse({ error: `Call failed: ${e.message}` }, 502);
    }
  },
};
