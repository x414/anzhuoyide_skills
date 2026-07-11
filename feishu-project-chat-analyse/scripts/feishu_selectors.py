"""
飞书 UI 选择器 fallback 模块
当首选选择器失效时，自动尝试备用选择器

用法:
    from feishu_selectors import find_element, SELECTORS

    # 获取带 fallback 的选择器列表
    selectors = SELECTORS['search_result_container']

    # 自动尝试多个选择器找到元素
    element = find_element(page, 'chat_scroll_area')
"""

# 选择器配置 —— 按优先级排列，首选在前
SELECTORS = {
    "search_result_container": [
        ".search-result-container",
        "[class*='search-result']",
        ".larkc-global-search-panel",
        ".lark-search-result",
        "[data-testid='search-result-container']",
    ],
    "chat_scroll_area": [
        ".lark-chat-right .scroller",
        ".lark-chat-content .scroller",
        "[class*='chat-content'] [class*='scroller']",
        "[class*='message-list']",
        ".chat-history",
        "[class*='chat-right'] > div:nth-child(2)",
    ],
    "chat_message_item": [
        ".message-content",
        "[class*='message-content']",
        ".lark-message-body",
        "[class*='chat-message']",
        ".bubble",
    ],
    "chat_name_in_list": [
        ".chat-text-title",
        ".group-chat-card-info",
        ".message-chat-title",
        ".conversation-name",
        "[class*='chat-name']",
        "[class*='title']",
    ],
    "search_input": [
        ".larkc-search-input input",
        "[class*='search-input'] input",
        "input[placeholder*='搜索']",
        "input[placeholder*='Search']",
    ],
    "groups_tab": [
        "text=Groups",
        "text=群组",
        "[role='tab']:has-text('Groups')",
        "[role='tab']:has-text('群组')",
    ],
    "view_more_button": [
        "text=View More",
        "text=查看更多",
        "text=Show More",
        "text=加载更多",
        "button:has-text('View More')",
        "button:has-text('查看更多')",
    ],
    "login_qr_code": [
        ".login-qr-code",
        "[class*='qr-code']",
        "img[src*='qr']",
    ],
}


def find_element(page, selector_key, timeout=5000):
    """
    使用 fallback 链查找元素

    Args:
        page: Playwright page 对象
        selector_key: SELECTORS 字典中的 key
        timeout: 每个选择器的超时时间(ms)

    Returns:
        找到的元素，或 None
    """
    selectors = SELECTORS.get(selector_key, [])
    last_error = None

    for idx, sel in enumerate(selectors):
        try:
            if sel.startswith("text="):
                # 文本选择器
                element = page.locator(sel).first
            else:
                element = page.locator(sel).first

            # 尝试等待元素可见
            element.wait_for(timeout=timeout)

            # 检查元素是否实际存在且有内容
            if element.count() > 0:
                return element
        except Exception as e:
            last_error = e
            continue

    return None


def find_element_js(page, selector_key):
    """
    使用 JavaScript 执行 fallback 查找
    适用于 Playwright locator 无法定位的场景

    Args:
        page: Playwright page 对象
        selector_key: SELECTORS 字典中的 key

    Returns:
        元素的 bounding_box 信息，或 None
    """
    selectors = SELECTORS.get(selector_key, [])

    script = """
    (selectors) => {
        for (const sel of selectors) {
            let el;
            if (sel.startsWith('text=')) {
                const text = sel.replace('text=', '');
                const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
                let node;
                while (node = walker.nextNode()) {
                    if (node.textContent.trim() === text) {
                        el = node.parentElement;
                        break;
                    }
                }
            } else if (sel.startsWith('[class*=')) {
                const match = sel.match(/\\[class\\*='(.+?)'\\]/);
                if (match) {
                    el = document.querySelector(`[class*="${match[1]}"]`);
                }
            } else {
                el = document.querySelector(sel);
            }

            if (el) {
                const rect = el.getBoundingClientRect();
                return {
                    found: true,
                    selector: sel,
                    x: rect.x,
                    y: rect.y,
                    width: rect.width,
                    height: rect.height,
                    text: el.innerText?.substring(0, 100) || ''
                };
            }
        }
        return { found: false };
    }
    """

    try:
        result = page.evaluate(script, selectors)
        if result.get('found'):
            return result
    except Exception:
        pass

    return None


def get_available_selectors(page):
    """
    调试工具：列出页面上所有可用的 CSS 类名
    用于飞书 UI 更新后快速定位新选择器

    Args:
        page: Playwright page 对象

    Returns:
        常用类名列表（去重）
    """
    script = """
    () => {
        const allElements = document.querySelectorAll('*');
        const classSet = new Set();
        allElements.forEach(el => {
            if (el.className && typeof el.className === 'string') {
                el.className.split(/\\s+/).forEach(c => {
                    if (c && c.length > 5) classSet.add(c);
                });
            }
        });
        return Array.from(classSet).sort();
    }
    """

    try:
        classes = page.evaluate(script)
        # 过滤出可能相关的类名
        relevant = [c for c in classes if any(k in c.lower() for k in [
            'chat', 'message', 'search', 'result', 'scroller', 'conversation',
            'group', 'title', 'content', 'bubble'
        ])]
        return relevant[:100]  # 最多返回100个
    except Exception:
        return []


def debug_selectors(page, output_file='./selector_debug.json'):
    """
    调试工具：测试所有选择器，输出可用性报告

    Args:
        page: Playwright page 对象
        output_file: 报告输出路径
    """
    import json

    report = {}
    for key, selectors in SELECTORS.items():
        report[key] = {
            'selectors': selectors,
            'results': []
        }
        for sel in selectors:
            try:
                count = page.locator(sel).count()
                report[key]['results'].append({
                    'selector': sel,
                    'found': count > 0,
                    'count': count
                })
            except Exception as e:
                report[key]['results'].append({
                    'selector': sel,
                    'found': False,
                    'error': str(e)
                })

    with open(output_file, 'w') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"[DEBUG] Selector report saved to {output_file}")
    return report
