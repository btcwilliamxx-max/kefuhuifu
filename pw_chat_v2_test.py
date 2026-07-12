"""Playwright 测试: ARK 金主题 + chat launcher + drawer + refresh password。
跑: cd G:\\kefuhuifu && python pw_chat_v2_test.py
"""
import asyncio
import json
import sys
from pathlib import Path
from playwright.async_api import async_playwright

URL = 'http://127.0.0.1:9876/index.html'
PASSWORD = 'ark2026'
REFRESH_PW = 'arkie2026'
OUT = Path(r'G:\kefuhuifu\_pw_chat_v2')
OUT.mkdir(exist_ok=True)
RESULTS = []

def log(name, ok, detail=''):
    RESULTS.append({'name': name, 'ok': ok, 'detail': detail})
    icon = '✅' if ok else '❌'
    print(f'{icon} {name}' + (f' — {detail}' if detail else ''))

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--disable-dev-shm-usage'])
        ctx = await browser.new_context(viewport={'width': 1280, 'height': 800})
        page = await ctx.new_page()
        js_errors = []
        page.on('pageerror', lambda e: js_errors.append(str(e)))

        # 1) 加载 + 登录
        await page.goto(URL, wait_until='networkidle', timeout=15000)
        try:
            await page.wait_for_selector('#loginPassword', timeout=3000)
            await page.fill('#loginPassword', PASSWORD)
            await page.click('#loginBtn')
            await page.wait_for_selector('#chatLauncher', timeout=10000)
            await page.wait_for_function("() => window.__chatReady === true", timeout=15000)
        except Exception as e:
            log('加载/登录', False, str(e)[:120])
        log('加载 + 登录 + initChat 完成', True)

        # 2) 全站配色统一到金色（无紫蓝残留）
        bg_color = await page.evaluate("getComputedStyle(document.body).backgroundColor")
        log('主背景深蓝黑', '20, 19, 25' in bg_color or bg_color == 'rgb(20, 19, 25)', f'bg={bg_color}')
        accent = await page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()")
        log('强调色 ARK 金', accent.lower() == '#eeb726', f'--accent={accent}')

        # 检查是否还有紫色（rgba(139, 92, 246) 或 #6366f1 之类）
        purple_left = await page.evaluate("""() => {
            const sheets = Array.from(document.styleSheets);
            for (const s of sheets) {
                try {
                    const rules = Array.from(s.cssRules || []);
                    for (const r of rules) {
                        const t = (r.cssText || '').toLowerCase();
                        if (t.includes('6366f1') || t.includes('8b5cf6') || t.includes('139, 92, 246') || t.includes('rgba(139, 92, 246)')) return true;
                    }
                } catch(e) {}
            }
            return false;
        }""")
        log('全站无紫色残留', not purple_left)

        # 3) chat-launcher 存在 + 默认在右下
        launcher_visible = await page.locator('#chatLauncher').is_visible()
        log('chat-launcher 可见', launcher_visible)
        launcher_box = await page.locator('#chatLauncher').bounding_box()
        log('launcher 默认在右下', launcher_box['x'] > 1000 and launcher_box['y'] > 600, f'pos=({launcher_box["x"]:.0f},{launcher_box["y"]:.0f})')

        # 4) 抽屉初始隐藏
        drawer_visible = await page.locator('#chatDrawer.show').count()
        log('drawer 初始隐藏', drawer_visible == 0)
        backdrop_visible = await page.locator('#chatBackdrop.show').count()
        log('backdrop 初始隐藏', backdrop_visible == 0)

        # 5) 点击 launcher 展开抽屉
        await page.click('#chatLauncher')
        await page.wait_for_function(
            "() => document.getElementById('chatDrawer').classList.contains('show')",
            timeout=2000
        )
        log('点击 launcher 展开抽屉', True)
        log('backdrop 同时显示', await page.locator('#chatBackdrop.show').count() == 1)

        # 截图：抽屉展开
        await page.screenshot(path=str(OUT / '01_drawer_open.png'), full_page=False)

        # 6) chat 提问
        await page.fill('#chatInput', '015 号提案阶级奖池比例怎么算的？')
        await page.click('#chatSendBtn')
        await page.wait_for_function(
            """() => {
                const bubbles = document.querySelectorAll('.chat-msg.assistant .chat-msg-bubble');
                return bubbles.length >= 1 && bubbles[bubbles.length - 1].textContent.length > 100;
            }""",
            timeout=60000
        )
        last_ai = await page.locator('.chat-msg.assistant').last.inner_text()
        log('chat 答对 015 提案 (len>100)', len(last_ai) > 100, f'len={len(last_ai)}')
        log('chat 含 ⚠️ 警告', '⚠️' in last_ai)
        log('chat 含 015', '015' in last_ai or '015' in last_ai.lower())

        # 截图：对话
        await page.screenshot(path=str(OUT / '02_chat_qa.png'), full_page=False)

        # 7) 外点击收起（点 backdrop）
        await page.click('#chatBackdrop')
        await page.wait_for_function(
            "() => !document.getElementById('chatDrawer').classList.contains('show')",
            timeout=2000
        )
        log('外点击 backdrop 收起抽屉', True)

        # 8) 拖动 launcher
        await page.mouse.move(launcher_box['x'] + 28, launcher_box['y'] + 28)
        await page.mouse.down()
        await page.mouse.move(400, 400, steps=10)
        await page.mouse.up()
        await page.wait_for_timeout(300)
        new_box = await page.locator('#chatLauncher').bounding_box()
        log('launcher 可拖动', abs(new_box['x'] - 400) < 50, f'newX={new_box["x"]:.0f}')

        # 截图：拖动后
        await page.screenshot(path=str(OUT / '03_after_drag.png'), full_page=False)

        # 9) 拖动后再点 launcher，验证新位置生效
        await page.click('#chatLauncher')
        await page.wait_for_function(
            "() => document.getElementById('chatDrawer').classList.contains('show')",
            timeout=2000
        )
        log('新位置仍可点击展开', True)

        # 10) 主搜索框（kb 搜索）仍能用
        await page.fill('#searchInput', '015 提案')
        await page.wait_for_timeout(500)
        result_count = await page.locator('#resultsContainer .result-item').count()
        log('主搜索框仍可用', result_count > 0, f'hits={result_count}')

        # 11) 关闭抽屉（点 X）
        await page.click('#chatCloseBtn')
        await page.wait_for_function(
            "() => !document.getElementById('chatDrawer').classList.contains('show')",
            timeout=2000
        )
        log('X 按钮收起抽屉', True)

        # 12) Sidebar 刷新按钮 → 密码 modal
        # 打开 sidebar（移动端汉堡按钮或直接打开）
        # 先尝试 display:block 强制显示
        await page.evaluate("document.getElementById('sidebar').classList.add('open')")
        await page.wait_for_timeout(300)
        refresh_btn_visible = await page.locator('#refreshKBBtn').is_visible()
        log('刷新知识库按钮在 sidebar 中', refresh_btn_visible)
        if refresh_btn_visible:
            await page.click('#refreshKBBtn')
            await page.wait_for_selector('#pwModal.show', timeout=2000)
            log('点击刷新按钮 → 密码 modal 弹出', True)

            # 13) 密码错 → 看到错误
            await page.fill('#pwInput', 'wrong-password')
            await page.click('#pwSubmitBtn')
            await page.wait_for_timeout(2500)
            err_text = await page.locator('#pwError').inner_text()
            log('密码错时显示错误', '密码' in err_text or '错误' in err_text, f'err="{err_text}"')

            # 14) 密码对 → 刷新
            await page.fill('#pwInput', REFRESH_PW)
            # 同时打桩 Worker fetch（防止真 API 受限）
            await page.evaluate("""(pw) => {
                window.__fetched_refresh = null;
                const orig = window.fetch;
                window.fetch = function(...args) {
                    if (args[0].includes('/refresh')) {
                        window.__fetched_refresh = { url: args[0], body: JSON.parse(args[1].body) };
                    }
                    return orig(...args);
                };
            }""", REFRESH_PW)
            await page.click('#pwSubmitBtn')
            await page.wait_for_timeout(2500)
            log('密码对 → modal 关闭', await page.locator('#pwModal.show').count() == 0)

            # 截图：sidebar + 完整页
            await page.screenshot(path=str(OUT / '04_after_refresh.png'), full_page=True)

        # 15) 无 JS 错误
        log('无 JS 错误', len(js_errors) == 0, f'count={len(js_errors)}' + (f', first={js_errors[0][:80]}' if js_errors else ''))

        await browser.close()

    print('\n' + '=' * 60)
    passed = sum(1 for r in RESULTS if r['ok'])
    failed = sum(1 for r in RESULTS if not r['ok'])
    print(f'通过 {passed}/{len(RESULTS)}  失败 {failed}')
    print(f'截图存到 {OUT}')
    print('=' * 60)
    Path(r'G:\kefuhuifu\_pw_chat_v2.json').write_text(json.dumps(RESULTS, ensure_ascii=False, indent=2), encoding='utf-8')
    sys.exit(0 if failed == 0 else 1)

if __name__ == '__main__':
    asyncio.run(main())
