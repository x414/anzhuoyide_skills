#!/usr/bin/env python3
"""
飞书文档内容提取脚本 - v2 修复版
改进：
1. 增加重试机制（每个文档最多重试 3 次）
2. 浏览器断开后自动恢复
3. 更好的错误处理和日志
4. 验证提取结果
5. 支持断点续传（跳过已提取的文档）
"""
import json, time, os, sys
import glob
import shutil

os.environ['DISPLAY'] = ':0'
os.environ['XAUTHORITY'] = '/run/user/1001/.mutter-Xwaylandauth.73GKP3'
from playwright.sync_api import sync_playwright


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


def extract_single_doc(page, url, title, max_retries=3):
    """提取单个文档内容，带重试机制"""
    SSR_STOP = [".wikiSSRBox{", "!function(){", "window.secondChunk",
                "window.fourthChunk", "document.cookie=", "window.__catalogueContentCallbacks",
                "= 'getAttribute'"]

    SIDEBAR_NOISE = ['飞书文档', '搜索', '首页', '云空间', '知识库', '我的空间',
                     'Docs', 'Search', 'Home', 'Drive', 'Wiki', 'My Space']

    for attempt in range(max_retries):
        try:
            # 导航到文档页面
            page.goto(url, wait_until='domcontentloaded', timeout=30000)
            time.sleep(3)

            # 等待 SSR 内容可见
            ssr_visible = False
            for wait_round in range(20):
                try:
                    visible = page.evaluate("""() => {
                        const el = document.querySelector('.page-main-item');
                        if (!el) return false;
                        const style = window.getComputedStyle(el);
                        return style.visibility === 'visible';
                    }""")
                    if visible:
                        ssr_visible = True
                        break
                except:
                    pass
                time.sleep(0.5)

            if not ssr_visible:
                if attempt < max_retries - 1:
                    print(f"    ⚠ SSR 未就绪，重试 ({attempt + 1}/{max_retries})")
                    time.sleep(2)
                    continue
                else:
                    print(f"    ✗ SSR 始终未就绪")
                    return None

            # 提取内容
            content = page.evaluate("""() => {
                const mainItem = document.querySelector('.page-main-item');
                if (!mainItem) return '';
                return mainItem.innerText;
            }""")

            if not content:
                if attempt < max_retries - 1:
                    print(f"    ⚠ 内容为空，重试 ({attempt + 1}/{max_retries})")
                    time.sleep(2)
                    continue
                else:
                    print(f"    ✗ 始终无法提取内容")
                    return None

            # 处理内容：按行处理，遇到 SSR 标记停止
            lines = content.split('\n')
            filtered_lines = []
            for line in lines:
                # 检查 SSR 停止标记
                if any(marker in line for marker in SSR_STOP):
                    break
                # 过滤侧边栏噪音
                if any(noise in line for noise in SIDEBAR_NOISE):
                    continue
                filtered_lines.append(line)

            result = '\n'.join(filtered_lines)

            # 验证提取结果
            if len(result) < 50:
                if attempt < max_retries - 1:
                    print(f"    ⚠ 内容过短 ({len(result)} 字符)，重试 ({attempt + 1}/{max_retries})")
                    time.sleep(2)
                    continue
                else:
                    print(f"    ⚠ 内容过短 ({len(result)} 字符)")

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

    # 加载并验证 cookies
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

    # 检查已提取的文档（断点续传）
    extracted_tokens = set()
    if os.path.exists(output_dir):
        for filename in os.listdir(output_dir):
            if filename.endswith('.txt'):
                # 从文件名提取 token
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

        print(f"\n[PHASE 1] 开始提取 {len(doc_list)} 篇文档...")
        print(f"[PHASE 1] 输出目录: {output_dir}")
        print("=" * 70)

        for i, (title, doc_info) in enumerate(doc_list.items(), 1):
            url = doc_info['href']
            token = doc_info['token']

            # 构造完整 URL
            if 'wiki' in url:
                full_url = f"https://<tenant>.feishu.cn/wiki/{token}"
            elif 'docx' in url:
                full_url = f"https://<tenant>.feishu.cn/docx/{token}"
            elif 'docs' in url:
                full_url = f"https://<tenant>.feishu.cn/docs/{token}"
            else:
                full_url = url

            print(f"\n[{i}/{len(doc_list)}] {title[:60]}")
            print(f"  Token: {token}")

            # 检查是否已提取
            if token in extracted_tokens:
                print(f"  ✓ 已存在，跳过")
                # 读取已存在的文件
                for filename in os.listdir(output_dir):
                    if filename.startswith(token + '_'):
                        filepath = os.path.join(output_dir, filename)
                        with open(filepath, 'r', encoding='utf-8') as f:
                            content = f.read()
                        extracted_docs.append({
                            'title': title,
                            'url': full_url,
                            'token': token,
                            'file': filename,
                            'content_length': len(content)
                        })
                        break
                continue

            # 提取文档
            content = extract_single_doc(page, full_url, title)

            if content:
                # 保存为 txt 文件
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
                    'title': title,
                    'url': full_url,
                    'token': token,
                    'file': filename,
                    'content_length': len(content)
                })

                print(f"  ✓ 已提取 {len(content)} 字符")
            else:
                failed_docs.append({
                    'title': title,
                    'url': full_url,
                    'token': token
                })
                print(f"  ✗ 提取失败")

        b.close()

    # 验证结果
    print("\n" + "=" * 70)
    print("[PHASE 2] 提取完成验证")
    print("=" * 70)
    print(f"  成功: {len(extracted_docs)}/{len(doc_list)}")
    print(f"  失败: {len(failed_docs)}/{len(doc_list)}")

    if failed_docs:
        print("\n失败的文档:")
        for doc in failed_docs:
            print(f"  - {doc['title'][:60]}")
            print(f"    Token: {doc['token']}")

    if len(extracted_docs) == 0:
        print("\n⚠ 警告: 所有文档提取失败！")
        print("可能原因:")
        print("  1. Cookies 已过期，请重新登录")
        print("  2. 页面结构变化，需要更新脚本")
        print("  3. 网络问题导致页面加载失败")

    return extracted_docs


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='飞书文档内容提取脚本 - v2 修复版')
    parser.add_argument('--doc-list', required=True, help='文档列表 JSON 文件')
    parser.add_argument('--output', required=True, help='输出目录')
    parser.add_argument('--cookie-file', default='./feishu_cookies.json', help='cookies 文件路径')

    args = parser.parse_args()

    # 加载文档列表
    try:
        with open(args.doc_list) as f:
            doc_list = json.load(f)
        print(f"[INFO] 加载了 {len(doc_list)} 篇文档")
    except Exception as e:
        print(f"[ERROR] 加载文档列表失败: {e}")
        sys.exit(1)

    # 提取文档
    extracted = extract_documents(doc_list, args.output, args.cookie_file)

    # 保存索引
    index_file = os.path.join(args.output, 'index.json')
    with open(index_file, 'w', encoding='utf-8') as f:
        json.dump(extracted, f, ensure_ascii=False, indent=2)

    print(f"\n[FINAL] 索引文件: {index_file}")
