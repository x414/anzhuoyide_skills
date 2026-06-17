#!/usr/bin/env python3
"""
飞书文档内容提取脚本 - v3 滚动提取版
关键改进：
1. 飞书使用虚拟滚动，必须逐步滚动容器才能获取完整内容
2. 找到实际可滚动容器（overflow-y: auto/scroll），逐步滚动并合并内容
3. 每屏提取一次，按行去重
4. 保留重试机制和断点续传
"""
import json, time, os, sys
import glob
import shutil

os.environ['DISPLAY'] = ':0'
os.environ['XAUTHORITY'] = '/run/user/1001/.mutter-Xwaylandauth.73GKP3'
from playwright.sync_api import sync_playwright


SSR_STOP = [".wikiSSRBox{", "!function(){", "window.secondChunk",
            "window.fourthChunk", "document.cookie=", "window.__catalogueContentCallbacks",
            "= 'getAttribute'"]

SIDEBAR_NOISE = ['飞书文档', '搜索', '首页', '云空间', '知识库', '我的空间',
                 'Docs', 'Search', 'Home', 'Drive', 'Wiki', 'My Space',
                 'and Shared Spaces have moved', 'AI QuickView',
                 'Upload Log', 'Customer Service', "What's New",
                 'Help Center', 'Keyboard Shortcuts', 'rangeDom',
                 'Be the first to like']


def find_chrome():
    """查找 Chrome/Chromium 可执行文件"""
    home = os.path.expanduser('~')
    chrome_patterns = [
        os.path.join(home, '.cache/ms-playwright/chromium-*/chrome-linux64/chrome'),
        os.path.join(home, '.cache/ms-playwright/chromium-*/chrome'),
    ]
    for pattern in chrome_patterns:
        matches = glob.glob(pattern)
        if matches:
            return sorted(matches)[-1]
    for cmd in ['google-chrome', 'chromium-browser', 'chromium']:
        path = shutil.which(cmd)
        if path:
            return path
    raise RuntimeError("Chrome 未找到")


def validate_cookies(cookies):
    """验证 cookies 是否有效"""
    if not cookies:
        return False, "Cookies 为空"
    if len(cookies) < 10:
        return False, f"Cookies 数量过少 ({len(cookies)})"
    has_feishu = any('.feishu.cn' in c.get('domain', '') for c in cookies)
    if not has_feishu:
        return False, "未找到飞书 cookies"
    return True, f"Cookies 有效 ({len(cookies)} 个)"


def find_scrollable_container(page):
    """找到飞书文档的实际可滚动容器"""
    return page.evaluate("""() => {
        const all = document.querySelectorAll('*');
        let best = null;
        for (const el of all) {
            const style = getComputedStyle(el);
            const overflowY = style.overflowY;
            if ((overflowY === 'auto' || overflowY === 'scroll')
                && el.scrollHeight > el.clientHeight + 100) {
                if (!best || el.scrollHeight > best.scrollHeight) {
                    best = {
                        scrollHeight: el.scrollHeight,
                        clientHeight: el.clientHeight,
                        className: (el.className || '').toString().split(' ')[0]
                    };
                }
            }
        }
        return best;
    }""")


def scroll_and_collect(page, container_info):
    """逐步滚动容器并收集所有视口内容，按行去重"""
    if not container_info:
        # 没有可滚动容器，直接提取 body
        content = page.evaluate("() => document.body.innerText || ''")
        return content

    class_name = container_info['className']
    total_height = container_info['scrollHeight']
    viewport_height = container_info['clientHeight']
    step = max(int(viewport_height * 0.85), 500)

    # 滚动到顶部
    page.evaluate(f"""() => {{
        const el = document.querySelector('.{class_name}');
        if (el) el.scrollTop = 0;
    }}""")
    time.sleep(1)

    all_lines = []
    seen_lines = set()

    for pos in range(0, total_height + step, step):
        # 滚动到指定位置
        page.evaluate(f"""() => {{
            const el = document.querySelector('.{class_name}');
            if (el) el.scrollTop = {pos};
        }}""")
        time.sleep(0.8)

        # 获取实际滚动位置（可能和请求不同）
        actual_pos = page.evaluate(f"""() => {{
            const el = document.querySelector('.{class_name}');
            return el ? el.scrollTop : 0;
        }}""")

        # 提取当前视口文本
        current = page.evaluate(f"""() => {{
            const el = document.querySelector('.{class_name}');
            return el ? (el.innerText || '') : '';
        }}""")

        # 按行去重合并
        for line in current.split('\n'):
            stripped = line.strip()
            if stripped and stripped not in seen_lines:
                all_lines.append(stripped)
                seen_lines.add(stripped)

        # 到底了就停
        if actual_pos + viewport_height >= total_height - 10:
            break

    return '\n'.join(all_lines)


def filter_content(text):
    """过滤 SSR 标记和侧边栏噪音"""
    lines = text.split('\n')
    filtered = []
    for line in lines:
        if any(marker in line for marker in SSR_STOP):
            break
        if any(noise in line for noise in SIDEBAR_NOISE):
            continue
        filtered.append(line)
    return '\n'.join(filtered)


def extract_single_doc(page, url, title, max_retries=3):
    """提取单个文档内容，带滚动和重试"""
    for attempt in range(max_retries):
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=30000)
            time.sleep(4)

            # 等待页面渲染
            for _ in range(15):
                try:
                    has_content = page.evaluate("""() => {
                        const el = document.querySelector('.bear-web-x-container')
                                  || document.querySelector('.page-main-item')
                                  || document.body;
                        return (el.innerText || '').length > 100;
                    }""")
                    if has_content:
                        break
                except:
                    pass
                time.sleep(0.5)

            # 找到可滚动容器
            container_info = find_scrollable_container(page)

            if container_info:
                print(f"    滚动容器: .{container_info['className']} "
                      f"({container_info['scrollHeight']}x{container_info['clientHeight']})")
            else:
                print(f"    无可滚动容器，直接提取")

            # 滚动并收集内容
            raw_content = scroll_and_collect(page, container_info)

            if not raw_content or len(raw_content) < 50:
                if attempt < max_retries - 1:
                    print(f"    ⚠ 内容过短 ({len(raw_content or '')} 字符)，重试 ({attempt + 1}/{max_retries})")
                    time.sleep(2)
                    continue
                else:
                    return raw_content

            # 过滤
            result = filter_content(raw_content)
            return result

        except Exception as e:
            error_msg = str(e)
            if attempt < max_retries - 1:
                print(f"    ⚠ 提取失败: {error_msg[:50]}...，重试 ({attempt + 1}/{max_retries})")
                time.sleep(3)
            else:
                print(f"    ✗ 提取失败（已重试{max_retries}次）: {error_msg[:80]}")

    return None


def extract_documents(doc_list, output_dir, cookie_file='./feishu_cookies.json'):
    """提取多个文档"""
    chrome = find_chrome()

    try:
        with open(cookie_file) as f:
            cookies = json.load(f)
        valid, msg = validate_cookies(cookies)
        if not valid:
            print(f"[ERROR] {msg}")
            return []
        print(f"[INFO] {msg}")
    except Exception as e:
        print(f"[ERROR] 加载 cookies 失败: {e}")
        return []

    # 从 cookies 检测 tenant
    tenant = None
    for cookie in cookies:
        domain = cookie.get('domain', '')
        if '.feishu.cn' in domain and not domain.startswith('.'):
            tenant = domain.split('.')[0]
            break
    if not tenant:
        tenant = '<tenant>'
    print(f"[INFO] 使用 tenant: {tenant}")

    # 断点续传
    extracted_tokens = set()
    if os.path.exists(output_dir):
        for filename in os.listdir(output_dir):
            if filename.endswith('.txt'):
                token = filename.split('_')[0]
                extracted_tokens.add(token)

    if extracted_tokens:
        print(f"[INFO] 已存在 {len(extracted_tokens)} 个文档，将跳过")

    os.makedirs(output_dir, exist_ok=True)

    extracted_docs = []
    failed_docs = []

    with sync_playwright() as p:
        b = p.chromium.launch(headless=False, executable_path=chrome, args=['--no-sandbox'])
        ctx = b.new_context(viewport={'width': 1920, 'height': 1080})
        ctx.add_cookies(cookies)
        page = ctx.new_page()

        total = len(doc_list)
        print(f"\n[PHASE 1] 开始提取 {total} 篇文档...")
        print(f"[PHASE 1] 输出目录: {output_dir}")
        print("=" * 70)

        for i, (title, doc_info) in enumerate(doc_list.items(), 1):
            url = doc_info['href']
            token = doc_info['token']

            if 'wiki' in url:
                full_url = f"https://{tenant}.feishu.cn/wiki/{token}"
            elif 'docx' in url:
                full_url = f"https://{tenant}.feishu.cn/docx/{token}"
            elif 'docs' in url:
                full_url = f"https://{tenant}.feishu.cn/docs/{token}"
            else:
                full_url = url

            print(f"\n[{i}/{total}] {title[:60]}")
            print(f"  Token: {token}")

            # 断点续传
            if token in extracted_tokens:
                print(f"  ✓ 已存在，跳过")
                for filename in os.listdir(output_dir):
                    if filename.startswith(token + '_'):
                        filepath = os.path.join(output_dir, filename)
                        with open(filepath, 'r', encoding='utf-8') as f:
                            content = f.read()
                        extracted_docs.append({
                            'title': title, 'url': full_url, 'token': token,
                            'file': filename, 'content_length': len(content)
                        })
                        break
                continue

            content = extract_single_doc(page, full_url, title)

            if content and len(content) > 50:
                safe_title = title[:50].replace('/', '_').replace('\\', '_').replace(':', '_').replace(' ', '_')
                filename = f"{token}_{safe_title}.txt"
                filepath = os.path.join(output_dir, filename)

                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(f"标题: {title}\n")
                    f.write(f"URL: {full_url}\n")
                    f.write(f"Token: {token}\n")
                    f.write(f"{'=' * 60}\n\n")
                    f.write(content)

                extracted_docs.append({
                    'title': title, 'url': full_url, 'token': token,
                    'file': filename, 'content_length': len(content)
                })

                print(f"  ✓ 已提取 {len(content)} 字符")
            else:
                failed_docs.append({'title': title, 'url': full_url, 'token': token})
                print(f"  ✗ 提取失败")

        b.close()

    print("\n" + "=" * 70)
    print("[PHASE 2] 提取完成验证")
    print("=" * 70)
    print(f"  成功: {len(extracted_docs)}/{total}")
    print(f"  失败: {len(failed_docs)}/{total}")

    if failed_docs:
        print("\n失败的文档:")
        for doc in failed_docs:
            print(f"  - {doc['title'][:60]} (token: {doc['token']})")

    return extracted_docs


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='飞书文档内容提取脚本 - v3 滚动提取版')
    parser.add_argument('--doc-list', required=True, help='文档列表 JSON 文件')
    parser.add_argument('--output', required=True, help='输出目录')
    parser.add_argument('--cookie-file', default='./feishu_cookies.json', help='cookies 文件路径')

    args = parser.parse_args()

    try:
        with open(args.doc_list) as f:
            doc_list = json.load(f)
        print(f"[INFO] 加载了 {len(doc_list)} 篇文档")
    except Exception as e:
        print(f"[ERROR] 加载文档列表失败: {e}")
        sys.exit(1)

    extracted = extract_documents(doc_list, args.output, args.cookie_file)

    index_file = os.path.join(args.output, 'index.json')
    with open(index_file, 'w', encoding='utf-8') as f:
        json.dump(extracted, f, ensure_ascii=False, indent=2)

    print(f"\n[FINAL] 索引文件: {index_file}")
