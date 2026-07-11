#!/usr/bin/env python3
"""
提取飞书聊天群完整聊天记录 - v6 (通用版)
核心改进：Playwright locator click + 滚动容器定位

使用方法:
    python3 extract_chat_messages_v6.py "群名" [输出文件]
    python3 extract_chat_messages_v6.py "<项目主群>" ./data/<keyword>.txt
    python3 extract_chat_messages_v6.py "<项目软件研发群>" ./data/example.txt

如果省略输出文件，默认保存到 feishu_analysis/data/<群名_safe>.txt
"""
import os
import sys
import json
import time
import re
import hashlib
from playwright.sync_api import sync_playwright

os.environ['DISPLAY'] = ':0'
# Try common Xauthority locations
for xauth_path in [
    # Auto-detect: checks ~/.Xauthority etc.
    os.path.expanduser("~/.Xauthority"),
]:
    if os.path.exists(xauth_path):
        os.environ['XAUTHORITY'] = xauth_path
        break

COOKIES_FILE = 'feishu_analysis/data/feishu_cookies.json'

# 尝试导入增量模块
HAS_NEW_MODULES = False
IncrementalState = None
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from incremental_state import IncrementalState as _IncrementalState
    IncrementalState = _IncrementalState
    HAS_NEW_MODULES = True
except Exception:
    pass


def safe_filename(name):
    """将群名转换为安全的文件名"""
    safe = re.sub(r'[^\w一-鿿_-]', '_', name)
    safe = re.sub(r'_+', '_', safe).strip('_')
    return safe


def extract_group(target_group, output_file=None, check_incremental=True):
    """提取单个群的完整聊天记录"""
    if output_file is None:
        safe_name = safe_filename(target_group)
        output_file = f'feishu_analysis/data/{safe_name}_v6.txt'

    print(f"完整聊天记录提取 - {target_group} (v6)", flush=True)

    # 增量检查
    if check_incremental and HAS_NEW_MODULES:
        try:
            state = IncrementalState()
            if os.path.exists(output_file):
                with open(output_file, 'r', encoding='utf-8') as f:
                    existing = f.read()
                if state.is_fully_extracted(target_group, existing):
                    print(f"  [SKIP] {target_group} already extracted ({len(existing)} chars)")
                    return len(existing)
        except Exception:
            pass

    # Load cookies
    if not os.path.exists(COOKIES_FILE):
        print(f"[ERROR] Cookies文件不存在: {COOKIES_FILE}")
        print("请先运行 launch_browser.py 登录飞书")
        return 0

    with open(COOKIES_FILE) as f:
        cookies = json.load(f)

    with sync_playwright() as p:
        home = os.path.expanduser('~')
        import glob
        chrome_path = sorted(
            glob.glob(os.path.join(home, '.cache/ms-playwright/chromium-*/chrome-linux64/chrome'))
        )[-1]

        browser = p.chromium.launch(headless=False, executable_path=chrome_path, args=['--no-sandbox'])
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        context.add_cookies(cookies)
        page = context.new_page()

        # Step 1: 进入飞书
        print("[1/5] 进入飞书...")
        page.goto('https://<tenant>.feishu.cn/messenger', wait_until='domcontentloaded', timeout=60000)
        time.sleep(10)

        # Step 2: 搜索群
        print(f"[2/5] 搜索群: {target_group}...")
        page.keyboard.press('Control+k')
        time.sleep(2)
        page.mouse.click(960, 90)
        time.sleep(1)
        page.keyboard.press('Control+a')
        time.sleep(0.5)
        page.keyboard.type(target_group, delay=50)
        time.sleep(5)

        # Step 3: 选择群（locator click - 更可靠）
        print("[3/5] 选择群...")
        try:
            # 方法1: 使用locator精确匹配
            locator = page.locator('.search-result-container, [class*="search-result"]').locator(f'text={target_group}').first
            locator.click(timeout=5000)
            print("  [OK] 使用locator点击成功")
        except Exception:
            try:
                # 方法2: 键盘导航
                page.keyboard.press('ArrowDown')
                time.sleep(1)
                page.keyboard.press('Enter')
                print("  [OK] 使用键盘导航成功")
            except Exception as e:
                print(f"  [ERROR] 无法进入群: {e}")
                browser.close()
                return 0

        time.sleep(5)
        page.keyboard.press('Escape')
        time.sleep(2)

        # Step 4: 累积捕获
        print("[4/5] 开始累积捕获...")
        all_texts = []
        seen_hashes = set()
        rounds = 0
        max_rounds = 200
        no_growth_count = 0
        total_chars = 0

        # 关键：将鼠标移动到滚动容器中心
        scroll_container = page.locator('.lark-chat-right .scroller').first
        if scroll_container.count() > 0:
            box = scroll_container.bounding_box()
            if box:
                cx = box['x'] + box['width'] / 2
                cy = box['y'] + box['height'] / 2
                page.mouse.move(cx, cy)
                print(f"  [OK] 鼠标定位到滚动容器中心 ({cx:.0f}, {cy:.0f})")
            else:
                page.mouse.move(960, 600)
                print("  [WARN] 使用默认鼠标位置")
        else:
            page.mouse.move(960, 600)
            print("  [WARN] 未找到滚动容器，使用默认位置")

        time.sleep(1)

        while rounds < max_rounds and no_growth_count < 10:
            # 获取当前可见文本
            current = page.evaluate('''() => {
                const chatArea = document.querySelector('[class*="chat-content"], [class*="message-list"], .chat-history');
                if (chatArea) return chatArea.innerText;
                const panels = document.querySelectorAll('div');
                for (const panel of panels) {
                    const rect = panel.getBoundingClientRect();
                    if (rect.left > 400 && rect.width > 400 && rect.height > 300) {
                        const text = panel.innerText;
                        if (text && text.length > 500) return text;
                    }
                }
                return document.body.innerText;
            }''')

            content_hash = hash(current) % 1000000007

            if content_hash not in seen_hashes:
                seen_hashes.add(content_hash)
                all_texts.append(current)
                total_chars += len(current)
                no_growth_count = 0
                if rounds < 10 or rounds % 20 == 0:
                    print(f"  Round {rounds}: +{len(current)} chars (total: {total_chars})")
            else:
                no_growth_count += 1
                if rounds % 10 == 0:
                    print(f"  Round {rounds}: same - no growth: {no_growth_count}")

            rounds += 1

            # 关键：使用真实鼠标滚轮（非JS scrollTop）
            page.mouse.wheel(0, -300)
            time.sleep(1.5)

            # 辅助：JS滚动确保懒加载触发
            page.evaluate('''() => {
                const chatArea = document.querySelector('[class*="chat-content"], [class*="message-list"], .chat-history');
                if (chatArea) chatArea.scrollTop -= 300;
            }''')
            time.sleep(1.5)

            # 当到达顶部时继续滚动（有时需要多次触发）
            if rounds % 20 == 0:
                scroll_top = page.evaluate('''() => {
                    const el = document.querySelector('[class*="chat-content"], [class*="message-list"], .chat-history');
                    return el ? el.scrollTop : -1;
                }''')
                if scroll_top == 0:
                    print(f"  [INFO] 到达顶部(scrollTop=0)，继续尝试加载...")
                    time.sleep(3)

        # Step 5: 合并并保存
        print("[5/5] 合并并保存...")
        combined = "\n\n=== ROUND SEPARATOR ===\n\n".join(all_texts)

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(combined)

        print(f"\n✅ Done! {target_group}")
        print(f"   File: {output_file}")
        print(f"   Chars: {len(combined)}")
        print(f"   Lines: {combined.count(chr(10))}")

        # 记录增量状态
        if HAS_NEW_MODULES:
            try:
                state = IncrementalState()
                state.record_extracted(
                    target_group,
                    content_hash=state._hash_content(combined),
                    msg_count=combined.count(chr(10)),
                    chars=len(combined)
                )
            except Exception:
                pass

        browser.close()
        return len(combined)


if __name__ == '__main__':
    if len(sys.argv) >= 2:
        target = sys.argv[1]
        output = sys.argv[2] if len(sys.argv) >= 3 else None
        extract_group(target, output)
    else:
        print("Usage: python3 extract_chat_messages_v6.py '群名' [输出文件]")
        print("Example: python3 extract_chat_messages_v6.py '<项目主群>' ./<keyword>.txt")
        sys.exit(1)
