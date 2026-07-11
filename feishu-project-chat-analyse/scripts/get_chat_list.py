#!/usr/bin/env python3
"""
从飞书消息页面获取聊天列表

使用方法:
    python3 get_chat_list.py --output ./chat_list.json
"""
import os
import json
import time
import argparse
from playwright.sync_api import sync_playwright

# Ensure X11 display — required for GUI browser
if not os.environ.get("DISPLAY"):
    os.environ["DISPLAY"] = ":0"
    # Try common Xauthority locations
    for xauth_path in [
        # Auto-detect: checks ~/.Xauthority etc.
        os.path.expanduser("~/.Xauthority"),
    ]:
        if os.path.exists(xauth_path):
            os.environ["XAUTHORITY"] = xauth_path
            break


def find_chrome():
    """Find Chrome/Chromium executable path"""
    home = os.path.expanduser('~')
    chrome_patterns = [
        os.path.join(home, '.cache/ms-playwright/chromium-*/chrome-linux64/chrome'),
        os.path.join(home, '.cache/ms-playwright/chromium-*/chrome'),
    ]

    import glob
    for pattern in chrome_patterns:
        matches = glob.glob(pattern)
        if matches:
            return sorted(matches)[-1]

    import shutil
    for cmd in ['google-chrome', 'chromium-browser', 'chromium']:
        path = shutil.which(cmd)
        if path:
            return path
    raise RuntimeError("Chrome/Chromium not found")


def get_chat_list(cookies, output_file):
    """获取聊天列表"""

    with sync_playwright() as p:
        chrome_path = find_chrome()
        browser = p.chromium.launch(headless=False, executable_path=chrome_path, args=['--no-sandbox'])
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        context.add_cookies(cookies)
        page = context.new_page()

        print("[INFO] 访问飞书消息页面...")
        page.goto('https://<tenant>.feishu.cn/messenger', wait_until='domcontentloaded', timeout=30000)

        # 等待页面加载
        print("[INFO] 等待页面加载...")
        time.sleep(5)

        # 提取聊天列表
        print("[INFO] 提取聊天列表...")
        chats = page.evaluate('''() => {
            const items = [];
            const chatItems = document.querySelectorAll('[class*="chat-item"], [class*="conversation-item"], [class*="message-item"]');
            chatItems.forEach(item => {
                const nameEl = item.querySelector('[class*="chat-name"], [class*="conversation-name"], [class*="title"]');
                const msgEl = item.querySelector('[class*="last-message"], [class*="message-preview"]');
                const timeEl = item.querySelector('[class*="time"], [class*="timestamp"]');
                
                if (nameEl) {
                    items.push({
                        name: nameEl.innerText.trim(),
                        last_message: msgEl ? msgEl.innerText.trim() : '',
                        time: timeEl ? timeEl.innerText.trim() : ''
                    });
                }
            });
            return items;
        }''')

        print(f"[INFO] 找到 {len(chats)} 个聊天")

        # 保存结果
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(chats, f, ensure_ascii=False, indent=2)

        print(f"[INFO] 已保存到: {output_file}")
        browser.close()
        return chats


def main():
    parser = argparse.ArgumentParser(description='获取飞书聊天列表')
    parser.add_argument('--output', '-o', default='./chat_list.json', help='输出文件路径')
    parser.add_argument('--cookies', default='feishu_analysis/data/feishu_cookies.json', help='cookies文件路径')
    args = parser.parse_args()

    if not os.path.exists(args.cookies):
        print(f"[ERROR] Cookies文件不存在: {args.cookies}")
        print("请先运行 launch_browser.py 登录飞书")
        return

    with open(args.cookies) as f:
        cookies = json.load(f)

    get_chat_list(cookies, args.output)


if __name__ == '__main__':
    main()
