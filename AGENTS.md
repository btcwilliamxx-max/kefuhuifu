# AGENTS.md — kefuhuifu 项目约定

> 这份文档给 AI 助手（Mavis / OpenCode / Claude Code 等）看，描述这个项目特有的踩坑点和约定。
> **用户的 KB 是公开的，所以这份文档也会被部署到 Pages 上**（arkie.cc.cd/AGENTS.md）。包含的是技术笔记，不是敏感数据。

## 项目简介

- **性质**：ARK 项目客服知识库静态站，部署在 https://arkie.cc.cd（GitHub Pages + 自定义域）
- **存储**：所有内容在 `data/*.txt`，7 个分类文件，无数据库
- **入口**：`index.html`（内含全部 JS / CSS）

## 文件结构

```
kefuhuifu/
├── index.html              # 全部 UI + JS（约 870 行）
├── sw.js                   # Service Worker（cache: 'no-store' 走 data）
├── manifest.json           # PWA 配置
├── README.md               # 用户文档
├── AGENTS.md               # ← 你正在读
├── data/
│   ├── 活动公告.txt
│   ├── 提案政策.txt
│   ├── 工作室事务.txt
│   ├── 常用话术.txt        ← Q&A / 话术 / 客服对外口径
│   ├── 产品操作.txt
│   ├── 常见FAQ.txt
│   ├── 地址合约.txt
│   └── _announcements.json # 公告索引（按时间顺序）
└── tools/
    └── check_data.py       # 数据完整性检查（分隔符等）
```

## 数据格式约定（重要）

每条记录用 `---` 分隔，**每条都必须以 `---` 结尾**，否则 append 新条目时会和上一条合并为一个 block 被吞掉。

```
[问题/关键词]: <空格分隔关键词>
[标签]: #标签1 #标签2
[来源]: ARK-XXX           ← 可选，用于关联到某条公告
[图片]: images/...png     ← 可选
[答案]: 
<正文，多行>

[链接]: https://...       ← 无链接留空
---
```

## Append 新条目 — 安全做法

**不要用 PowerShell `>>` 或 `echo >`**（shell 转义会破坏 `\n`）。**必须用 Python 脚本**。

Append 前**检查上一条结尾**：
```python
existing = open(path, encoding='utf-8').read()
needs_sep = not existing.rstrip('\n').rstrip().endswith('---')
with open(path, 'a', encoding='utf-8', newline='') as f:
    if needs_sep:
        f.write('\n---\n\n')   # 补上分隔符
    f.write(new_entry)
```

Append 后用 `tools/check_data.py` 验证。

## 外部 CDN 依赖（已验证）

| 用途 | URL | 状态 |
|---|---|---|
| Fuse.js | `cdn.jsdelivr.net/npm/fuse.js@7.0.0` | ✅ |
| OpenCC cn→tw | `cdn.jsdelivr.net/npm/opencc-js@1.0.5/dist/umd/cn2t.js` | ✅ |
| Segmentit（中文分词） | `cdn.jsdelivr.net/npm/segmentit@2.0.3/dist/esm/segmentit.js` | ✅ |

❌ **不要用**（404）：
- `.../opencc-js/.../opencc.min.js`
- `.../opencc-js/.../data/s2t.json`
- `.../segmentit@2.1.10/dist/segmentit.es.min.js`（改成 v2.0.3 ESM）

## Service Worker

- 当前 cache version：`ark-knowledge-base-v5`
- `/data/*` 用 `cache: 'no-store'` 走网络，HTML 用 `cache: 'no-cache'`
- 改 data/*.txt 不需要 bump SW 版本（cache: 'no-store' 强制拉新）

## 链接 / 凭据

- GitHub PAT 在 `G:\kefuhuifu\.git\config` 的 remote URL（明文）。如有安全顾虑改用 `gh auth login`。
- 自由子域名 `arkie.cc.cd`（DNSHE）随时可能挂，本地 `G:\kefuhuifu` 是唯一真相。

## 用户约定（强）

- **公告 / 通知类原文**：用户对**文字模版极敏感**，改文案必须先征求明确同意（直接推送原文，不要 simplify / 翻译）。
- **AI 视觉 / 模型批量调用**：涉及多张图前提醒用户成本。
- **截图 / 公告每日临时数据**：用户会手动清理，不要替用户删 / 重生成，只报告状态。

## 推送前自检

1. `python tools/check_data.py` — 所有分隔符 OK
2. `git diff data/` 只看到该条新增
3. push 后等 1-2 分钟
4. Playwright 实测：搜关键词 + 看 sidebar 计数

## 调试 / 一次性脚本

排查时会写 `pw_*.py`、`fix_*.py`、`append_*.py` 等文件，**未追踪**，用完扔 mavis-trash 或加入 .gitignore。**不要 commit**。
