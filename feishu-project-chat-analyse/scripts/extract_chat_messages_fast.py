#!/usr/bin/env python3
"""
提取飞书聊天群完整聊天记录 - Fast 版
核心改进：复用浏览器实例 + 减少 sleep

使用方法:
    python3 extract_chat_messages_fast.py "群名" [输出文件]
    python3 extract_chat_messages_fast.py --batch groups.txt --output-dir ./data/
"""
import os
import sys
import json
import time
import re
import hashlib
import argparse
from playwright.sync_api import sync_playwright

os.environ['DISPLAY'] = ':0'
for xauth_path in [os.path.expanduser("~/.Xauthority")]:
    if os.path.exists(xauth_path):
        os.environ['XAUTHORITY'] = xauth_path
        break

COOKIES_FILE = 'feishu_analysis/data/feishu_cookies.json'


def safe_filename(name):
    safe = re.sub(r'[^\w一-鿿_-]', '_', name)
    safe = re.sub(r'_+', '_', safe).strip('_')
    return safe


def extract_single_group(page, target_group, output_file):
    """在已打开的浏览器页面上提取单个群（不复用浏览器）"""
    print(f"\n[EXTRACT] {target_group}")
    start_time = time.time()

    # Step 1: 搜索群
    page.keyboard.press('Escape')
    time.sleep(0.5)
    page.keyboard.press('Control+k')
    time.sleep(1)
    page.mouse.click(960, 90)
    time.sleep(0.3)
    page.keyboard.press('Control+a')
    time.sleep(0.2)
    page.keyboard.type(target_group, delay=30)
    time.sleep(2)

    # Step 2: 选择群
    try:
        locator = page.locator('.search-result-container, [class*="search-result"]').locator(f'text={target_group}').first
        locator.click(timeout=5000)
    except Exception:
        try:
            page.keyboard.press('ArrowDown')
            time.sleep(0.5)
            page.keyboard.press('Enter')
        except Exception as e:
            print(f"  [ERROR] 无法进入群: {e}")
            return 0

    time.sleep(3)
    page.keyboard.press('Escape')
    time.sleep(1)

    # Step 3: 累积捕获（加速版）
    all_texts = []
    seen_hashes = set()
    rounds = 0
    max_rounds = 200
    no_growth_count = 0
    total_chars = 0

    scroll_container = page.locator('.lark-chat-right .scroller').first
    if scroll_container.count() > 0:
        box = scroll_container.bounding_box()
        if box:
            cx = box['x'] + box['width'] / 2
            cy = box['y'] + box['height'] / 2
            page.mouse.move(cx, cy)
        else:
            page.mouse.move(960, 600)
    else:
        page.mouse.move(960, 600)

    time.sleep(0.5)

    while rounds < max_rounds and no_growth_count < 8:
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
            if rounds < 5 or rounds % 30 == 0:
                print(f"  Round {rounds}: +{len(current)} chars (total: {total_chars})")
        else:
            no_growth_count += 1
            if rounds % 20 == 0:
                print(f"  Round {rounds}: same - no growth: {no_growth_count}")

        rounds += 1

        # 加速：减少 sleep，合并为单次操作
        page.mouse.wheel(0, -300)
        page.evaluate('''() => {
            const chatArea = document.querySelector('[class*="chat-content"], [class*="message-list"], .chat-history');
            if (chatArea) chatArea.scrollTop -= 300;
        }''')
        time.sleep(0.6)

        if rounds % 30 == 0:
            scroll_top = page.evaluate('''() => {
                const el = document.querySelector('[class*="chat-content"], [class*="message-list"], .chat-history');
                return el ? el.scrollTop : -1;
            }''')
            if scroll_top == 0:
                print(f"  [INFO] 到达顶部，继续尝试...")
                time.sleep(1.5)

    # 保存
    combined = "\n\n=== ROUND SEPARATOR ===\n\n".join(all_texts)
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(combined)

    duration = time.time() - start_time
    print(f"  ✅ Done! {len(combined)} chars, {combined.count(chr(10))} lines, {duration:.1f}s")
    return len(combined)


def extract_groups_batch(groups, output_dir, cookies_path=COOKIES_FILE):
    """批量提取，复用浏览器实例"""
    if not os.path.exists(cookies_path):
        print(f"[ERROR] Cookies文件不存在: {cookies_path}")
        return []

    with open(cookies_path) as f:
        cookies = json.load(f)

    results = []
    total_start = time.time()

    with sync_playwright() as p:
        home = os.path.expanduser('~')
        import glob
        chrome_path = sorted(
            glob.glob(os.path.join(home, '.cache/ms-playwright/chromium-*/chrome-linux64/chrome'))
        )[-1]

        print("[INIT] 启动浏览器...")
        browser = p.chromium.launch(headless=False, executable_path=chrome_path, args=['--no-sandbox'])
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        context.add_cookies(cookies)
        page = context.new_page()

        print("[INIT] 进入飞书...")
        page.goto('https://<tenant>.feishu.cn/messenger', wait_until='domcontentloaded', timeout=60000)
        for i in range(30):
            text = page.evaluate('() => document.body.innerText')
            if 'BSP' in text and len(text) > 500:
                print(f"  Page loaded after {i+1}s")
                break
            time.sleep(1)

        print(f"\n{'='*60}")
        print(f"批量提取 - 共 {len(groups)} 个群")
        print(f"{'='*60}")

        for idx, group in enumerate(groups, 1):
            print(f"\n[{idx}/{len(groups)}] {group}")
            safe = safe_filename(group)
            output_file = os.path.join(output_dir, f"{safe}.txt")

            # 增量跳过
            if os.path.exists(output_file) and os.path.getsize(output_file) > 100:
                with open(output_file, 'r', encoding='utf-8') as f:
                    existing = f.read()
                print(f"  [SKIP] Already extracted ({len(existing)} chars)")
                results.append({'group': group, 'status': 'skipped', 'chars': len(existing)})
                continue

            try:
                chars = extract_single_group(page, group, output_file)
                results.append({'group': group, 'status': 'success', 'chars': chars})
            except Exception as e:
                print(f"  [ERROR] {e}")
                results.append({'group': group, 'status': 'failed', 'error': str(e)})
                # 尝试恢复页面状态
                try:
                    page.keyboard.press('Escape')
                    time.sleep(1)
                except:
                    pass

        browser.close()

    total_duration = time.time() - total_start
    success = sum(1 for r in results if r['status'] == 'success')
    skipped = sum(1 for r in results if r['status'] == 'skipped')
    failed = sum(1 for r in results if r['status'] == 'failed')
    total_chars = sum(r.get('chars', 0) for r in results)

    print(f"\n{'='*60}")
    print(f"完成! 成功:{success} 跳过:{skipped} 失败:{failed} 总计:{len(results)}")
    print(f"总字符: {total_chars:,}  总耗时: {total_duration:.1f}s")
    print(f"{'='*60}")

    return results


def main():
    parser = argparse.ArgumentParser(description='Fast batch extract Feishu chat messages')
    parser.add_argument('target', nargs='?', help='Single group name')
    parser.add_argument('--batch', '-b', help='Batch: file with group names (one per line)')
    parser.add_argument('--output-dir', '-o', default='./feishu_analysis/data', help='Output directory')
    parser.add_argument('--output', help='Output file for single extraction')
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    if args.batch:
        with open(args.batch, 'r', encoding='utf-8') as f:
            groups = [l.strip() for l in f if l.strip()]
        extract_groups_batch(groups, args.output_dir)
    elif args.target:
        extract_groups_batch([args.target], args.output_dir)
    else:
        print("Usage: python3 extract_chat_messages_fast.py '群名'")
        print("       python3 extract_chat_messages_fast.py --batch groups.txt")
        sys.exit(1)


if __name__ == '__main__':
    main()
