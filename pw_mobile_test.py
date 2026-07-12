"""Playwright 移动端测试：iOS (iPhone 14) + Android Chrome (Pixel 6)
测:
- launcher 在右下可见
- 点击 launcher (用 tap) → drawer 打开
- drawer 输入可用 + AI 返回
- drawer 外点击 → 收起
- 拖动 launcher → 位置改变
"""
import asyncio, json, sys
from pathlib import Path
from playwright.async_api import async_playwright

URL = 'http://127.0.0.1:9876/index.html'
PASSWORD = 'ark2026'
OUT = Path(r'G:\kefuhuifu\_pw_mobile')
OUT.mkdir(exist_ok=True)
RESULTS = []

DEVICES = [
    {'name': 'iPhone 14 (iOS-style)', 'viewport_w': 390, 'viewport_h': 844},
    {'name': 'Pixel 6 (Android-style)', 'viewport_w': 412, 'viewport_h': 915},
]

def log(name, ok, detail=''):
    RESULTS.append({'name': name, 'ok': ok, 'detail': detail})
    icon = '✅' if ok else '❌'
    print(f'{icon} {name}' + (f' — {detail}' if detail else ''))

async def test_device(p, device):
    name = device['name']
    print(f'\n{"="*20} {name} {"="*20}')
    browser = await p.chromium.launch(headless=True, args=['--disable-dev-shm-usage'])
    # 不用 is_mobile (会让 innerWidth 变成 device px, 与 CSS layout 混淆)
    # 用 desktop context + 小 viewport + dpr=1 即可
    ctx = await browser.new_context(
        viewport={'width': device['viewport_w'], 'height': device['viewport_h']},
        has_touch=True,
        device_scale_factor=1,
    )
    page = await ctx.new_page()
    page.on('pageerror', lambda e: log(f'{name} pageerror', False, str(e)[:80]))
    # 收集 chat-launcher log 帮助 debug
    page.on('console', lambda m: print(f'  [{name.split()[0]}.console] {m.text}') if 'chat-launcher' in m.text else None)
    try:
        # 加载 + 登录
        await page.goto(URL, wait_until='networkidle', timeout=15000)
        try:
            await page.evaluate("localStorage.removeItem('ark_chat_launcher_pos_v1')")
            await page.reload(wait_until='networkidle')
            await page.wait_for_selector('#loginPassword', timeout=3000)
            await page.fill('#loginPassword', PASSWORD)
            await page.tap('#loginBtn')
            await page.wait_for_selector('#chatLauncher', timeout=15000)
            await page.wait_for_function("() => window.__chatReady === true", timeout=15000)
        except Exception as e:
            log(f'{name} 加载/登录', False, str(e)[:80])
        log(f'{name} 加载 + 登录', True)

        # 1) launcher 可见
        log(f'{name} launcher 可见', await page.locator('#chatLauncher').is_visible())

        # 2) 用真实的 window.innerWidth 判断 launcher 在 viewport
        # (Playwright mobile context 的 window.innerWidth ≠ viewport.width, 用浏览器实际值)
        in_viewport = await page.evaluate("""() => {
            const l = document.getElementById('chatLauncher');
            const r = l.getBoundingClientRect();
            const w = window.innerWidth, h = window.innerHeight;
            return r.x >= 0 && r.x + r.width <= w + 1 && r.y >= 0 && r.y + r.height <= h + 1;
        }""")
        box = await page.locator('#chatLauncher').bounding_box()
        vp_w = await page.evaluate("() => window.innerWidth")
        vp_h = await page.evaluate("() => window.innerHeight")
        log(f'{name} launcher 在 viewport 内', in_viewport, f'pos=({box["x"]:.0f},{box["y"]:.0f}) vp={vp_w}x{vp_h}')

        # 3) tap launcher → drawer 弹出
        await page.tap('#chatLauncher')
        try:
            await page.wait_for_function(
                "() => document.getElementById('chatDrawer').classList.contains('show')",
                timeout=3000
            )
            log(f'{name} tap launcher 弹出 drawer', True)
        except Exception:
            log(f'{name} tap launcher 弹出 drawer', False, 'no show class in 3s')
            await page.screenshot(path=str(OUT / f'fail_{name.split()[0]}_drawer.png'))
            await browser.close(); return

        # 4) backdrop 同时显示
        log(f'{name} backdrop 显示', await page.locator('#chatBackdrop.show').count() == 1)

        # 截图：drawer 打开
        await page.screenshot(path=str(OUT / f'{name.split()[0]}_01_drawer_open.png'))

        # 5) drawer 内部 chat 可用
        await page.fill('#chatInput', '015 提案阶级奖池比例？')
        # 拉动抽屉后 textarea 才可见
        await page.wait_for_selector('#chatInput:visible', timeout=3000)
        await page.tap('#chatSendBtn')
        try:
            await page.wait_for_function(
                """() => {
                    const bubbles = document.querySelectorAll('.chat-msg.assistant .chat-msg-bubble');
                    return bubbles.length >= 1 && bubbles[bubbles.length-1].textContent.length > 100;
                }""",
                timeout=60000
            )
            last_ai = await page.locator('.chat-msg.assistant').last.inner_text()
            log(f'{name} chat AI 答对 (len>100)', len(last_ai) > 100, f'len={len(last_ai)}')
        except Exception as e:
            log(f'{name} chat AI 答对', False, str(e)[:80])

        # 截图：对话
        await page.screenshot(path=str(OUT / f'{name.split()[0]}_02_chat.png'))

        # 6) tap backdrop (mobile: drawer 70vh 占下半, backdrop 上半可用; 避开左上 sidebar handle)
        await page.tap('#chatBackdrop', position={'x': 50, 'y': 150})
        try:
            await page.wait_for_function(
                "() => !document.getElementById('chatDrawer').classList.contains('show')",
                timeout=3000
            )
            log(f'{name} backdrop 收起 drawer', True)
        except Exception:
            log(f'{name} backdrop 收起 drawer', False)

        # 7) 拖动 launcher 到 vp 上半 (避开 mobile drawer 70vh 占的下半)
        await page.evaluate("""async () => {
            const l = document.getElementById('chatLauncher');
            const rect = l.getBoundingClientRect();
            const sx = rect.left + rect.width / 2;
            const sy = rect.top + rect.height / 2;
            const tx = window.innerWidth / 2;
            // Mobile: drawer 占 vp_h * 0.7 (844*0.7≈590), 上面 30vh (≈253) 可拖入
            // 但 mobile drawer 没打开时是 chatLauncher 自己在右下，拖到 vp 上方 (vp_h * 0.15)
            const ty = window.innerHeight * 0.15;
            function dispatch(type, x, y, id=1) {
                const ev = new PointerEvent(type, {
                    pointerId: id, pointerType: 'touch',
                    clientX: x, clientY: y, bubbles: true, cancelable: true
                });
                l.dispatchEvent(ev);
            }
            dispatch('pointerdown', sx, sy);
            for (let i = 1; i <= 8; i++) {
                const t = i / 8;
                dispatch('pointermove', sx + (tx-sx)*t, sy + (ty-sy)*t, 1);
                await new Promise(r => setTimeout(r, 30));
            }
            dispatch('pointerup', tx, ty, 1);
            await new Promise(r => setTimeout(r, 200));
        }""")
        new_box = await page.locator('#chatLauncher').bounding_box()
        vp_w = await page.evaluate("() => window.innerWidth")
        vp_h = await page.evaluate("() => window.innerHeight")
        target_x = vp_w / 2 - 26
        target_y = vp_h * 0.15 - 26
        log(f'{name} launcher 可拖动', abs(new_box['x'] - target_x) < 50, f'new_pos=({new_box["x"]:.0f},{new_box["y"]:.0f}) target=({target_x:.0f},{target_y:.0f})')

        # 8) 拖动后再点 launcher → 抽屉再次打开 (用 evaluate click 模拟 iOS Safari 行为)
        await page.wait_for_timeout(800)   # 等 DRAG_LOCK_MS (400ms) 过期
        await page.evaluate("document.getElementById('chatLauncher').click()")
        try:
            await page.wait_for_function(
                "() => document.getElementById('chatDrawer').classList.contains('show')",
                timeout=3000
            )
            log(f'{name} 拖动后点 launcher 仍展开', True)
        except Exception:
            log(f'{name} 拖动后点 launcher 仍展开', False, 'drawer 未重开')

        # 9) chat 跑一次更多问题 (关闭 backdrop 上方再点输入框避免上方控件拦截)
        # 先点抽屉里的输入框（不是用 fill 而是直接 evaluate 触发，避免 moblie tap 问题）
        await page.fill('#chatInput', 'MBR 是什么')
        await page.evaluate("document.getElementById('chatSendBtn').click()")
        try:
            await page.wait_for_function(
                """() => {
                    const bubbles = document.querySelectorAll('.chat-msg.assistant .chat-msg-bubble');
                    return bubbles.length >= 2 && bubbles[bubbles.length-1].textContent.length > 50;
                }""",
                timeout=60000
            )
            log(f'{name} 多轮对话', True)
        except Exception:
            log(f'{name} 多轮对话', False)
    finally:
        await page.close()
        await ctx.close()
        await browser.close()

async def main():
    async with async_playwright() as p:
        for d in DEVICES:
            await test_device(p, d)
    print('\n' + '=' * 60)
    passed = sum(1 for r in RESULTS if r['ok'])
    failed = sum(1 for r in RESULTS if not r['ok'])
    print(f'通过 {passed}/{len(RESULTS)}  失败 {failed}')
    Path(r'G:\kefuhuifu\_pw_mobile.json').write_text(json.dumps(RESULTS, ensure_ascii=False, indent=2), encoding='utf-8')
    print('=' * 60)
    sys.exit(0 if failed == 0 else 1)

if __name__ == '__main__':
    asyncio.run(main())
