#!/usr/bin/env python3
"""
飞书群组搜索工具 - 懒加载版
通过点击 observerItem 区域触发懒加载，找全所有相关群
"""
import os
import json
import time
import re
import argparse
from playwright.sync_api import sync_playwright


def extract_groups_from_page(page, keyword):
    """从页面提取包含关键词的群名"""
    text = page.evaluate('() => document.body.innerText')
    groups = set()
    kw = keyword.lower()
    for line in text.split('\n'):
        line = line.strip()
        if kw in line.lower() and 3 < len(line) < 80:
            bad = [
                'http', 'PM', 'AM', 'Yesterday', 'Search for', 'View More',
                'Related Space', 'Creator', 'Business Line', 'Description:',
                'Change in ar', 'Gerrit-Branch', 'M ota', 'Camera...',
                'Question:', 'Knowledge comes from', 'Last updated', 'External',
                'Group type', 'Filters', 'to navigate', 'to select', 'escto quit',
                'Help and Feedback', 'Sort', 'Clear', 'Search Groups', 'Includes:',
            ]
            if not any(b in line for b in bad):
                if line.endswith(')') and '(' in line:
                    line = line[:line.rfind('(')].strip()
                clean = line
                if clean and clean not in [kw, keyword, keyword + '​']:
                    groups.add(clean)
    return groups


def click_load_more(page):
    """点击加载更多区域（observerItem 或 search-more-placeholder）"""
    target = page.evaluate('''() => {
        let el = document.querySelector('.observerItem');
        if (!el) el = document.querySelector('.search-more-placeholder');
        if (!el) {
            const cards = document.querySelectorAll('.group-chat-card');
            if (cards.length > 0) {
                const last = cards[cards.length - 1];
                const rect = last.getBoundingClientRect();
                return {x: rect.x + rect.width/2, y: rect.bottom + 30, source: 'below_last_card'};
            }
            return null;
        }
        const rect = el.getBoundingClientRect();
        return {x: rect.x + rect.width/2, y: rect.y + rect.height/2, source: el.className};
    }''')
    
    if target:
        page.mouse.click(target['x'], target['y'])
        return True
    return False


def search_feishu_groups(keyword, cookies_path='feishu_analysis/data/feishu_cookies.json'):
    """搜索飞书中包含关键词的所有群组（支持懒加载）"""
    os.environ['DISPLAY'] = ':0'
    for xauth_path in [os.path.expanduser("~/.Xauthority")]:
        if os.path.exists(xauth_path):
            os.environ['XAUTHORITY'] = xauth_path
            break

    with open(cookies_path, 'r') as f:
        cookies = json.load(f)

    all_groups = set()

    with sync_playwright() as p:
        home = os.path.expanduser('~')
        import glob
        chrome_path = sorted(
            glob.glob(os.path.join(home, '.cache/ms-playwright/chromium-*/chrome-linux64/chrome'))
        )[-1]
        browser = p.chromium.launch(
            headless=False, executable_path=chrome_path, args=['--no-sandbox']
        )
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        context.add_cookies(cookies)
        page = context.new_page()

        print(f"[1/4] 打开飞书...")
        page.goto(
            'https://<tenant>.feishu.cn/messenger',
            wait_until='domcontentloaded',
            timeout=60000,
        )
        for i in range(30):
            text = page.evaluate('() => document.body.innerText')
            if 'BSP' in text and len(text) > 500:
                print(f"    Page loaded after {i+1}s")
                break
            time.sleep(1)

        print(f"[2/4] 搜索 '{keyword}'...")
        page.keyboard.press('Escape')
        time.sleep(1)
        page.keyboard.press('Control+k')
        time.sleep(3)
        page.keyboard.type(keyword, delay=50)
        time.sleep(5)

        print(f"[3/4] 点击 Groups...")
        page.evaluate('''() => {
            const btns = document.querySelectorAll('button');
            for (const btn of btns) {
                if (btn.innerText.trim() === 'Groups') {
                    btn.click();
                    return 'clicked';
                }
            }
            return 'not found';
        }''')
        time.sleep(8)

        print(f"[4/4] 提取并触发懒加载...")
        
        # Initial extraction
        groups = extract_groups_from_page(page, keyword)
        all_groups.update(groups)
        print(f"    初始: {len(groups)} 个群")

        # Trigger lazy loading by clicking load-more area
        no_growth_count = 0
        for round_num in range(50):
            # Scroll to bring load-more area into view (if needed)
            page.evaluate('''() => {
                const el = document.querySelector('.observerItem') || document.querySelector('.search-more-placeholder');
                if (el) el.scrollIntoView({behavior: 'instant', block: 'nearest'});
            }''')
            time.sleep(1)
            
            # Click load-more area
            if not click_load_more(page):
                print(f"    无加载区域，停止")
                break
            
            time.sleep(3)
            
            # Extract new groups
            groups = extract_groups_from_page(page, keyword)
            before = len(all_groups)
            all_groups.update(groups)
            after = len(all_groups)
            growth = after - before
            
            if growth > 0:
                print(f"    加载轮次 {round_num}: +{growth} 个群 (总计: {after})")
                no_growth_count = 0
            else:
                no_growth_count += 1
                if no_growth_count >= 3:
                    print(f"    连续{no_growth_count}次无新增，停止")
                    break

        browser.close()

    return all_groups


def main():
    parser = argparse.ArgumentParser(description='搜索飞书中包含关键词的所有群组（支持懒加载）')
    parser.add_argument('keyword', help='搜索关键词')
    parser.add_argument('--output', '-o', help='输出文件路径')
    parser.add_argument('--cookies', default='./feishu_analysis/data/feishu_cookies.json')
    args = parser.parse_args()

    print("=" * 70)
    print(f"飞书群组搜索（懒加载版）- 关键词: {args.keyword}")
    print("=" * 70)

    groups = search_feishu_groups(args.keyword, args.cookies)

    print("\n" + "=" * 70)
    print(f"找到 {len(groups)} 个 '{args.keyword}' 相关群")
    print("=" * 70)
    for g in sorted(groups):
        print(f"  - {g}")

    if args.output:
        with open(args.output, 'w') as f:
            for g in sorted(groups):
                f.write(f"{g}\n")
        print(f"\n[INFO] 已保存到 {args.output}")


if __name__ == '__main__':
    main()
