#!/usr/bin/env python3
"""
从飞书聊天中提取完整消息历史
核心方案：累积捕获 + 鼠标定位 + 真实滚轮

突破点：
1. 飞书使用虚拟列表，旧消息会被卸载，必须在滚动中持续累积捕获
2. 鼠标必须移动到消息容器中心，page.mouse.wheel() 的滚轮事件才能被正确接收
3. 使用真实鼠标滚轮（非JS scrollTop）触发懒加载
"""
import os
import json
import time
import re
import random
import argparse
from datetime import datetime
from playwright.sync_api import sync_playwright


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


def extract_messages_full(cookies, chat_name, output_file=None,
                          scroll_duration=1800, scroll_min=200, scroll_max=500,
                          pause_min=1.5, pause_max=3.0):
    """
    完整提取聊天记录（累积捕获模式）

    Args:
        cookies: 飞书登录cookies
        chat_name: 聊天名称
        output_file: 输出文件路径
        scroll_duration: 总滚动时长（秒）
        scroll_min/scroll_max: 每次滚动距离范围（px）
        pause_min/pause_max: 停顿时间范围（秒）
    """

    with sync_playwright() as p:
        chrome_path = find_chrome()
        browser = p.chromium.launch(
            headless=False,
            executable_path=chrome_path,
            args=['--no-sandbox']
        )
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        context.add_cookies(cookies)
        page = context.new_page()

        # Stealth模式（可选）
        try:
            from playwright_stealth import stealth_sync
            stealth_sync(page)
            print("[INFO] Stealth模式已启用")
        except ImportError:
            print("[INFO] Stealth模式未启用（pip install playwright-stealth）")

        # ====== Step 1: 进入飞书 ======
        print(f"[INFO] 访问飞书...")
        try:
            page.goto('https://<tenant>.feishu.cn/messenger',
                     wait_until='domcontentloaded', timeout=60000)
        except Exception:
            pass
        time.sleep(8)

        # ====== Step 2: 搜索并进入聊天 ======
        print(f"[INFO] 搜索聊天: {chat_name}")
        page.keyboard.press('Control+k')
        time.sleep(2)
        page.keyboard.type(chat_name, delay=50)
        time.sleep(3)
        page.keyboard.press('Enter')
        time.sleep(5)

        # 验证是否进入正确聊天
        right_text = page.evaluate("""() => {
            const el = document.querySelector('.lark-chat-right');
            return el ? el.innerText.substring(0, 100) : '';
        }""")
        if chat_name not in right_text:
            print(f"[WARN] 可能未进入正确聊天，尝试备选方案...")
            page.evaluate(f"""() => {{
                const items = document.querySelectorAll('.a11y_feed_card_item');
                for (const item of items) {{
                    if (item.innerText.includes('{chat_name}')) {{
                        item.click();
                        return true;
                    }}
                }}
                return false;
            }}""")
            time.sleep(5)

        print(f"[INFO] 已进入聊天: {chat_name}")

        # ====== Step 3: 鼠标定位到消息容器中心 ======
        # 这是触发懒加载的关键！
        container_info = page.evaluate("""() => {
            const el = document.querySelector('.lark-chat-right .scroller');
            if (el) {
                const rect = el.getBoundingClientRect();
                return {
                    x: rect.x + rect.width / 2,
                    y: rect.y + rect.height / 2,
                    found: true
                };
            }
            return {found: false};
        }""")

        if container_info and container_info.get('found'):
            page.mouse.move(container_info['x'], container_info['y'])
            time.sleep(0.5)
            page.mouse.click(container_info['x'], container_info['y'])
            time.sleep(1)
            print(f"[INFO] 鼠标已定位到消息容器中心 "
                  f"({container_info['x']:.0f}, {container_info['y']:.0f})")
        else:
            print("[WARN] 未找到消息容器，使用备用位置")
            page.mouse.move(1200, 600)
            time.sleep(0.5)
            page.mouse.click(1200, 600)
            time.sleep(1)

        # ====== Step 4: 累积捕获滚动 ======
        print(f"\n[INFO] 开始累积捕获滚动（目标{scroll_duration}秒）...")
        print("-" * 70)
        print(f"{'时间':>6s} | {'滚动':>6s} | {'快照':>5s} | "
              f"{'累积行':>7s} | {'新增':>5s} | {'状态'}")
        print("-" * 70)

        all_snapshots = []
        unique_lines = set()
        accumulated_lines = []
        scroll_count = 0
        pause_count = 0
        last_unique_count = 0
        no_growth_count = 0
        start_time = time.time()

        while (time.time() - start_time) < scroll_duration:
            # 1. 快速滚动阶段
            fast_scrolls = random.randint(2, 5)
            for _ in range(fast_scrolls):
                scroll_amount = random.randint(scroll_min, scroll_max)
                page.mouse.wheel(0, -scroll_amount)
                time.sleep(random.uniform(0.1, 0.2))
            scroll_count += fast_scrolls

            # 2. 停顿让内容加载
            pause_time = random.uniform(pause_min, pause_max)
            time.sleep(pause_time)
            pause_count += 1

            # 3. 偶尔往回滚一点
            if random.random() < 0.25:
                scroll_back = random.randint(50, 200)
                page.mouse.wheel(0, scroll_back)
                time.sleep(random.uniform(0.5, 1.0))

            # 4. 捕获当前文本快照
            current = page.evaluate("""() => {
                const el = document.querySelector('.lark-chat-right');
                return el ? el.innerText : '';
            }""")

            if current and len(current) > 100:
                all_snapshots.append(current)

                # 解析行并累积去重
                lines = current.split('\n')
                new_count = 0
                for line in lines:
                    stripped = line.strip()
                    if len(stripped) > 1 and stripped not in unique_lines:
                        unique_lines.add(stripped)
                        accumulated_lines.append(stripped)
                        new_count += 1

                elapsed = int(time.time() - start_time)
                current_unique = len(unique_lines)
                growth = current_unique - last_unique_count

                if growth > 0:
                    last_unique_count = current_unique
                    no_growth_count = 0
                    status = "增长"
                else:
                    no_growth_count += 1
                    status = "等待"

                if scroll_count % 30 == 0 or growth > 10:
                    print(f"{elapsed:6d}s | {scroll_count:6d} | "
                          f"{len(all_snapshots):5d} | {current_unique:7d} | "
                          f"{growth:+5d} | {status}")

                # 长时间无增长则增加等待
                if no_growth_count > 15:
                    extra = random.uniform(3.0, 6.0)
                    time.sleep(extra)

                # 检查是否到达顶部
                scroll_top = page.evaluate("""() => {
                    const el = document.querySelector('.lark-chat-right .scroller');
                    return el ? el.scrollTop : -1;
                }""")

                if (scroll_top is not None and scroll_top <= 5
                        and no_growth_count > 20):
                    print(f"\n[INFO] 已到达顶部 (scrollTop={scroll_top})")
                    break

                if no_growth_count > 40 and elapsed > 300:
                    print(f"\n[INFO] 长时间无增长，可能已到顶部")
                    break

        elapsed = int(time.time() - start_time)
        print("-" * 70)
        print(f"\n[INFO] 滚动结束")
        print(f"  总时长: {elapsed}秒 ({elapsed // 60}分钟)")
        print(f"  总滚动次数: {scroll_count}")
        print(f"  总快照数: {len(all_snapshots)}")
        print(f"  累积唯一行: {len(unique_lines)}")

        # ====== Step 5: 保存结果 ======
        accumulated_text = '\n'.join(accumulated_lines)

        # 保存原始文本
        txt_file = output_file.replace('.json', '.txt') if output_file else None
        if txt_file:
            with open(txt_file, 'w', encoding='utf-8') as f:
                f.write(accumulated_text)
            print(f"\n[INFO] 原始文本已保存: {txt_file}")
            print(f"  总字符数: {len(accumulated_text)}")

        # 解析日期
        dates = re.findall(
            r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) \d{1,2})',
            accumulated_text
        )
        if dates:
            unique_dates = sorted(set(dates))
            print(f"\n[INFO] 日期覆盖: {len(unique_dates)}天")
            print(f"  最早: {unique_dates[0]}")
            print(f"  最晚: {unique_dates[-1]}")

        # 解析消息结构
        messages = parse_messages_from_text(accumulated_text)
        print(f"\n[INFO] 解析到 {len(messages)} 条消息")

        # 保存JSON
        result = {
            'chat_name': chat_name,
            'extraction_method': '累积捕获 + 真实鼠标滚轮',
            'duration_seconds': elapsed,
            'scroll_count': scroll_count,
            'snapshots': len(all_snapshots),
            'total_chars': len(accumulated_text),
            'messages': messages,
            'raw_text': accumulated_text
        }

        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"\n[INFO] JSON已保存: {output_file}")

        browser.close()
        return result


def parse_messages_from_text(text):
    """从原始文本解析消息结构（简化版）"""
    lines = text.split('\n')
    messages = []

    # 跳过开头系统信息
    start_idx = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if re.match(r'^(Yesterday|Today|[A-Z][a-z]+day|\d{1,2}:\d{2}|[A-Z][a-z]+ \d{1,2})', stripped):
            start_idx = i
            break

    # 系统关键词
    skip_keywords = [
        'Chat', 'Docs', 'File', 'Pinned', 'BOT', 'External',
        'On Leave', 'Group members', 'Show More', 'replies', 'reply',
        'Clipped by', 'invited', 'joined', 'left the group',
        'Reply to', 'Message ', 'Shift + Enter'
    ]

    current_sender = None
    current_time = ""
    current_content = []
    i = start_idx

    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        # 跳过系统行
        skip = False
        for kw in skip_keywords:
            if kw.lower() in line.lower():
                if not (kw == 'reply' and not line.lower().endswith('reply')):
                    skip = True
                    break
        if skip:
            i += 1
            continue

        # 时间戳
        if re.match(r'^(Yesterday|Today|[A-Z][a-z]+day|\d{1,2}:\d{2}\s*(?:AM|PM)?|[A-Z][a-z]+ \d{1,2},? \d{0,4})$', line):
            if current_sender and current_content:
                messages.append({
                    'sender': current_sender,
                    'time': current_time,
                    'content': '\n'.join(current_content)
                })
                current_sender = None
                current_content = []
            current_time = line
            i += 1
            continue

        # 发送者判断
        is_sender = (2 < len(line) < 40 and not line.startswith('@')
                     and not line.startswith('http') and not line.startswith('[')
                     and not re.match(r'^\d', line)
                     and not any(c in line for c in ['。', '，', '！', '？', '.', ',']))

        if is_sender and i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if next_line and len(next_line) > 1 and not re.match(r'^(Yesterday|Today|\d{1,2}:\d{2})', next_line):
                if current_sender and current_content:
                    messages.append({
                        'sender': current_sender,
                        'time': current_time,
                        'content': '\n'.join(current_content)
                    })
                current_sender = line
                current_content = []
                i += 1
                continue

        # 消息内容
        if current_sender:
            current_content.append(line)

        i += 1

    # 最后一条
    if current_sender and current_content:
        messages.append({
            'sender': current_sender,
            'time': current_time,
            'content': '\n'.join(current_content)
        })

    return messages


def main():
    parser = argparse.ArgumentParser(description='提取飞书聊天消息（完整历史）')
    parser.add_argument('--chat-name', required=True, help='聊天名称')
    parser.add_argument('--output', help='输出JSON文件路径')
    parser.add_argument('--duration', type=int, default=1800,
                        help='滚动总时长（秒），默认1800=30分钟')
    parser.add_argument('--scroll-min', type=int, default=200,
                        help='最小滚动距离（px）')
    parser.add_argument('--scroll-max', type=int, default=500,
                        help='最大滚动距离（px）')
    parser.add_argument('--pause-min', type=float, default=1.5,
                        help='最小停顿时间（秒）')
    parser.add_argument('--pause-max', type=float, default=3.0,
                        help='最大停顿时间（秒）')
    args = parser.parse_args()

    cookie_file = './feishu_analysis/data/feishu_cookies.json'
    if not os.path.exists(cookie_file):
        print(f"[ERROR] Cookies文件不存在: {cookie_file}")
        print("[INFO] 请先运行 scripts/launch_browser.py 登录飞书")
        return

    with open(cookie_file, 'r') as f:
        cookies = json.load(f)

    if not args.output:
        safe_name = re.sub(r'[^\w一-鿿]+', '_', args.chat_name).strip('_')
        args.output = f'./feishu_analysis/data/messages_{safe_name}.json'

    extract_messages_full(
        cookies, args.chat_name, args.output,
        scroll_duration=args.duration,
        scroll_min=args.scroll_min, scroll_max=args.scroll_max,
        pause_min=args.pause_min, pause_max=args.pause_max
    )


if __name__ == '__main__':
    main()
