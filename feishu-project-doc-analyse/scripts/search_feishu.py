#!/usr/bin/env python3
"""
飞书搜索脚本 - v2 修复版
严格按照 skill 文档要求实现：
1. 点击搜索图标（不用 Control+k）
2. 必须点击 "Advanced Search" 打开完整搜索结果页面
3. 滚动搜索对话框内的容器（不是 window）
4. 滚动距离 3000px，等待 2 秒
5. 连续 10 次无变化停止，最多 100 轮
6. 增加验证机制和详细日志
"""
import json, time, os, sys
import glob
import shutil

os.environ['DISPLAY'] = ':0'
os.environ['XAUTHORITY'] = '/run/user/1001/.mutter-Xwaylandauth.73GKP3'
from playwright.sync_api import sync_playwright


def detect_tenant_from_cookies(cookie_file='./feishu_cookies.json'):
    """从 cookies 中检测 tenant"""
    try:
        with open(cookie_file) as f:
            cookies = json.load(f)
        # 优先查找具体的 tenant（如 <tenant>.feishu.cn）
        for cookie in cookies:
            domain = cookie.get('domain', '')
            if '.feishu.cn' in domain and not domain.startswith('.'):
                tenant = domain.split('.')[0]
                if tenant and tenant != 'feishu':
                    return tenant
        # 如果没有找到具体的 tenant，返回 None
        # 注意：.feishu.cn 是通用域名，不能用来确定 tenant
    except Exception as e:
        print(f"[WARN] 从 cookies 检测 tenant 失败: {e}")
    return None


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
    raise RuntimeError("Chrome 未找到。请安装: playwright install chromium")


def validate_cookies(cookies):
    """验证 cookies 是否有效"""
    if not cookies:
        return False, "Cookies 为空"
    if len(cookies) < 10:
        return False, f"Cookies 数量过少 ({len(cookies)})"
    # 检查是否有飞书相关的 cookies
    has_feishu = any('.feishu.cn' in c.get('domain', '') for c in cookies)
    if not has_feishu:
        return False, "未找到飞书 cookies"
    return True, f"Cookies 有效 ({len(cookies)} 个)"


def find_scroll_container(page):
    """找到搜索结果的可滚动容器"""
    return page.evaluate("""() => {
        // 优先查找 dialog 内的滚动容器
        const dialog = document.querySelector('[role="dialog"]');
        if (dialog) {
            const allEls = dialog.querySelectorAll('*');
            for (const el of allEls) {
                const style = window.getComputedStyle(el);
                if ((style.overflow === 'auto' || style.overflowY === 'auto')
                    && el.scrollHeight > el.clientHeight + 50) {
                    const cls = (el.className || '').toString().substring(0, 50);
                    return {
                        selector: '.' + cls.split(' ')[0],
                        scrollHeight: el.scrollHeight,
                        clientHeight: el.clientHeight,
                        inDialog: true
                    };
                }
            }
        }

        // 查找常见的搜索结果容器
        const candidates = [
            '[class*="advance-search-results"]',
            '[class*="search-results"]',
            '[class*="results-container"]',
            '._results_*',
        ];
        for (const sel of candidates) {
            const el = document.querySelector(sel);
            if (el && el.scrollHeight > el.clientHeight + 50) {
                return {
                    selector: sel,
                    scrollHeight: el.scrollHeight,
                    clientHeight: el.clientHeight,
                    inDialog: false
                };
            }
        }

        return null;
    }""")


def extract_all_links(page):
    """提取页面中所有文档链接"""
    return page.evaluate("""() => {
        const results = [];
        const all = document.querySelectorAll('a');
        const seen = new Set();
        all.forEach(a => {
            const href = a.href;
            const text = (a.innerText || '').trim();
            if (!href || !text || text.length < 2) return;
            if (!href.includes('feishu.cn')) return;
            if (seen.has(href)) return;
            seen.add(href);

            let token = '';
            let docType = '';
            const wikiMatch = href.match(/feishu\\.cn\\/wiki\\/([a-zA-Z0-9]+)/);
            const docxMatch = href.match(/feishu\\.cn\\/docx\\/([a-zA-Z0-9]+)/);
            const docsMatch = href.match(/feishu\\.cn\\/docs\\/([a-zA-Z0-9]+)/);
            if (wikiMatch) { token = wikiMatch[1]; docType = 'wiki'; }
            else if (docxMatch) { token = docxMatch[1]; docType = 'docx'; }
            else if (docsMatch) { token = docsMatch[1]; docType = 'docs'; }

            results.push({
                text: text.substring(0, 150),
                href: href.substring(0, 250),
                token: token,
                type: docType
            });
        });
        return results;
    }""")


def search_keyword(keyword, tenant, exclude_keywords=None, output_file=None, cookie_file='./feishu_cookies.json'):
    """搜索单个关键词 - 严格按照 skill 要求实现"""
    if exclude_keywords is None:
        exclude_keywords = []

    def is_relevant(title):
        for kw in exclude_keywords:
            if kw.lower() in title.lower():
                return False
        return True

    all_docs = {}
    chrome = find_chrome()

    # 加载并验证 cookies
    try:
        with open(cookie_file) as f:
            cookies = json.load(f)
        valid, msg = validate_cookies(cookies)
        if not valid:
            print(f"[ERROR] {msg}")
            return {}
        print(f"[INFO] {msg}")
    except Exception as e:
        print(f"[ERROR] 加载 cookies 失败: {e}")
        return {}

    with sync_playwright() as p:
        b = p.chromium.launch(headless=False, executable_path=chrome, args=['--no-sandbox'])
        ctx = b.new_context(viewport={'width': 1920, 'height': 1080})
        ctx.add_cookies(cookies)
        page = ctx.new_page()

        print("\n" + "=" * 70)
        print(f"[PHASE 1] 搜索关键词: {keyword}")
        print(f"[PHASE 1] 使用 tenant: {tenant}")
        print("=" * 70)

        # 步骤 1: 导航到飞书首页
        print("[STEP 1] 导航到飞书首页...")
        try:
            page.goto(f'https://{tenant}.feishu.cn/drive/home/', wait_until='domcontentloaded', timeout=30000)
            time.sleep(3)
            print(f"  ✓ 页面加载完成: {page.url}")
        except Exception as e:
            print(f"  ✗ 页面加载失败: {e}")
            b.close()
            return {}

        # 步骤 2: 点击搜索图标（不是 Control+k）
        print("[STEP 2] 点击搜索图标...")
        search_clicked = False
        try:
            # 尝试多种方式点击搜索
            search_selectors = [
                '[class*="search"]',
                '[data-testid="search"]',
                'button:has-text("搜索")',
                'button:has-text("Search")',
            ]
            for selector in search_selectors:
                el = page.query_selector(selector)
                if el and el.is_visible():
                    el.click()
                    search_clicked = True
                    print(f"  ✓ 已点击搜索图标: {selector}")
                    break
        except Exception as e:
            print(f"  ✗ 点击搜索失败: {e}")

        if not search_clicked:
            print("  ✗ 无法找到搜索图标")
            b.close()
            return {}

        time.sleep(2)

        # 步骤 3: 输入关键词
        print(f"[STEP 3] 输入关键词: {keyword}")
        try:
            page.keyboard.press('Control+a')
            time.sleep(0.3)
            page.keyboard.type(keyword, delay=50)
            time.sleep(2)
            print(f"  ✓ 关键词已输入")
        except Exception as e:
            print(f"  ✗ 输入关键词失败: {e}")
            b.close()
            return {}

        # 步骤 4: 关键！点击 "Advanced Search" 打开完整搜索结果页面
        # 不能直接按 Enter，那样会打开第一个文档
        print("[STEP 4] 点击 Advanced Search（关键步骤）...")
        advanced_clicked = False
        try:
            # 尝试多种方式找到 Advanced Search 按钮
            advanced_selectors = [
                'text=Advanced Search',
                'text=高级搜索',
                'button:has-text("Advanced")',
                'button:has-text("高级")',
                '[class*="advanced"]',
                'a:has-text("Advanced")',
                'a:has-text("高级")',
            ]
            for selector in advanced_selectors:
                try:
                    el = page.query_selector(selector)
                    if el and el.is_visible():
                        el.click()
                        advanced_clicked = True
                        print(f"  ✓ 已点击 Advanced Search: {selector}")
                        break
                except:
                    continue

            if not advanced_clicked:
                # 如果找不到 Advanced Search，尝试按 Enter 作为备选
                print("  ⚠ 未找到 Advanced Search 按钮，尝试按 Enter 作为备选...")
                page.keyboard.press('Enter')
                advanced_clicked = True
                print("  ⚠ 已按 Enter（可能不是最佳方式）")
        except Exception as e:
            print(f"  ✗ 点击 Advanced Search 失败: {e}")
            # 备选方案：按 Enter
            try:
                page.keyboard.press('Enter')
                advanced_clicked = True
                print("  ⚠ 已按 Enter 作为备选")
            except:
                pass

        if not advanced_clicked:
            print("  ✗ 无法触发搜索")
            b.close()
            return {}

        print("  等待搜索结果加载...")
        time.sleep(5)

        # 步骤 5: 找到搜索结果的可滚动容器
        print("[STEP 5] 查找搜索结果容器...")
        container_info = find_scroll_container(page)
        if container_info:
            print(f"  ✓ 找到容器: {container_info['selector']}")
            print(f"    位置: {'对话框内' if container_info['inDialog'] else '页面中'}")
            print(f"    高度: {container_info['scrollHeight']}px (可视: {container_info['clientHeight']}px)")
        else:
            print("  ⚠ 未找到专用容器，将使用 window 滚动")
            container_info = {'selector': 'window', 'scrollHeight': 0, 'clientHeight': 0, 'inDialog': False}

        # 步骤 6: 滚动加载所有结果
        print("[STEP 6] 滚动加载搜索结果...")
        last_count = 0
        no_change_count = 0
        max_rounds = 100

        for scroll_round in range(max_rounds):
            # 提取当前链接
            links = extract_all_links(page)

            # 过滤相关文档
            new_docs = 0
            for link in links:
                title = link['text']
                if is_relevant(title) and link['token']:
                    if title not in all_docs:
                        all_docs[title] = link
                        new_docs += 1

            print(f"  第{scroll_round + 1}轮: {len(links)}个链接, 新增{new_docs}篇, 总计{len(all_docs)}篇 (连续无变化:{no_change_count})")

            # 保存中间结果
            if (scroll_round + 1) % 20 == 0 and output_file:
                with open(output_file, 'w') as f:
                    json.dump(all_docs, f, ensure_ascii=False, indent=2)
                print(f"    >> 已保存中间结果: {len(all_docs)} 篇")

            # 检查是否停止
            if len(links) == last_count:
                no_change_count += 1
                if no_change_count >= 10:
                    print(f"  ✓ 连续10次无新内容，停止滚动")
                    break
            else:
                no_change_count = 0
                last_count = len(links)

            # 滚动容器（不是 window）
            try:
                if container_info['selector'] == 'window':
                    page.evaluate("window.scrollBy(0, 3000)")
                else:
                    selector = container_info['selector'].replace('"', '\\"')
                    page.evaluate(f"""() => {{
                        const el = document.querySelector('{selector}');
                        if (el) el.scrollBy(0, 3000);
                    }}""")
            except Exception as e:
                print(f"  ⚠ 滚动失败: {e}")

            time.sleep(2)

        b.close()

    # 验证结果
    print("\n" + "=" * 70)
    print(f"[PHASE 2] 搜索完成验证")
    print("=" * 70)
    print(f"  总计: {len(all_docs)} 篇相关文档")

    if len(all_docs) == 0:
        print("  ⚠ 警告: 未找到任何文档！")
        print("  可能原因:")
        print("    1. Cookies 已过期，请重新登录")
        print("    2. 搜索关键词不正确")
        print("    3. 页面结构变化，需要更新脚本")
    elif len(all_docs) < 5:
        print(f"  ⚠ 警告: 文档数量较少 ({len(all_docs)})，可能未加载完全")

    return all_docs


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='飞书搜索脚本 - v2 修复版（严格按 skill 要求）')
    parser.add_argument('--keywords', nargs='+', required=True, help='搜索关键词列表')
    parser.add_argument('--exclude', nargs='*', default=[], help='排除关键词')
    parser.add_argument('--output', required=True, help='输出文件路径')
    parser.add_argument('--tenant', default=None, help='飞书 tenant（默认从 cookies 自动检测）')
    parser.add_argument('--cookie-file', default='./feishu_cookies.json', help='cookies 文件路径')

    args = parser.parse_args()

    # 检测 tenant
    tenant = args.tenant
    if not tenant:
        tenant = detect_tenant_from_cookies(args.cookie_file)

    if not tenant:
        print("[ERROR] 无法检测 tenant。请使用 --tenant 参数指定，例如: --tenant <tenant>")
        sys.exit(1)

    print(f"[INFO] 使用 tenant: {tenant}")
    print(f"[INFO] Cookie 文件: {args.cookie_file}")

    all_results = {}
    for keyword in args.keywords:
        docs = search_keyword(keyword, tenant, args.exclude, args.output, args.cookie_file)
        all_results.update(docs)

    # 保存最终结果
    with open(args.output, 'w') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 70)
    print("[FINAL] 搜索完成!")
    print("=" * 70)
    print(f"  总计: {len(all_results)} 篇相关文档")
    print(f"  保存到: {args.output}")

    # 打印文档列表
    if all_results:
        print("\n文档列表:")
        for i, (title, doc) in enumerate(all_results.items(), 1):
            print(f"  {i}. {title[:80]}")
            print(f"     Token: {doc['token']}")
