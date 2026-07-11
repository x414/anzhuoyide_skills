#!/usr/bin/env python3
"""
飞书 Skill 环境检查脚本
运行此脚本验证环境是否满足使用要求

用法:
    python3 check_setup.py
"""
import sys
import os
import subprocess


def check_python_version():
    """检查 Python 版本"""
    version = sys.version_info
    if version >= (3, 8):
        print(f"✓ Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"✗ Python {version.major}.{version.minor}.{version.micro} (需要 >= 3.8)")
        return False


def check_module(module_name, import_name=None):
    """检查 Python 模块是否已安装"""
    import_name = import_name or module_name
    try:
        __import__(import_name)
        print(f"✓ {module_name}")
        return True
    except ImportError:
        print(f"✗ {module_name} (未安装)")
        return False


def check_playwright_browsers():
    """检查 Playwright 浏览器是否已安装"""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch()
                browser.close()
                print("✓ Playwright Chromium")
                return True
            except Exception as e:
                if "Executable doesn't exist" in str(e):
                    print("✗ Playwright Chromium (未安装，运行: python3 -m playwright install chromium)")
                else:
                    print(f"✗ Playwright Chromium ({e})")
                return False
    except ImportError:
        print("✗ Playwright Chromium (Playwright 未安装)")
        return False


def check_display():
    """检查 DISPLAY 环境变量"""
    if os.environ.get('DISPLAY'):
        print(f"✓ DISPLAY={os.environ['DISPLAY']}")
        return True
    else:
        print("⚠ DISPLAY 未设置 (GUI 模式需要，服务器环境可用 xvfb-run)")
        return False


def check_xauthority():
    """检查 Xauthority"""
    xauth = os.environ.get('XAUTHORITY')
    if xauth and os.path.exists(xauth):
        print(f"✓ XAUTHORITY={xauth}")
        return True

    home = os.path.expanduser("~")
    candidates = [
        os.path.join(home, ".Xauthority"),
    ]
    for c in candidates:
        if os.path.exists(c):
            print(f"✓ XAUTHORITY (auto-detect: {c})")
            return True

    print("⚠ XAUTHORITY 未设置 (GUI 模式需要)")
    return False


def check_skill_files():
    """检查 Skill 文件完整性"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    required = [
        'launch_browser.py',
        'get_chat_list.py',
        'search_feishu_groups.py',
        'extract_chat_messages_v6.py',
        'batch_extract.py',
        'deep_context_mining.py',
        'feishu_selectors.py',
        'config.py',
        'incremental_state.py',
    ]
    all_ok = True
    for f in required:
        path = os.path.join(script_dir, f)
        if os.path.exists(path):
            print(f"✓ {f}")
        else:
            print(f"✗ {f} (缺失)")
            all_ok = False
    return all_ok


def main():
    print("=" * 50)
    print("飞书 Skill 环境检查")
    print("=" * 50)
    print()

    results = []

    print("[Python 环境]")
    results.append(check_python_version())
    print()

    print("[Python 模块]")
    results.append(check_module("playwright"))
    results.append(check_module("pyyaml", "yaml"))
    print()

    print("[浏览器]")
    results.append(check_playwright_browsers())
    print()

    print("[显示环境]")
    results.append(check_display())
    results.append(check_xauthority())
    print()

    print("[Skill 文件]")
    results.append(check_skill_files())
    print()

    passed = sum(results)
    total = len(results)

    print("=" * 50)
    if passed == total:
        print(f"✅ 所有检查通过 ({passed}/{total})")
        print("可以开始使用: python3 scripts/launch_browser.py")
    elif passed >= total - 2:
        print(f"⚠️ 基本可用 ({passed}/{total})")
        print("建议安装缺失项以获得最佳体验")
    else:
        print(f"❌ 环境不满足 ({passed}/{total})")
        print("请先安装依赖: pip install -r requirements.txt")
        print("然后安装浏览器: python3 -m playwright install chromium")
    print("=" * 50)

    return passed == total


if __name__ == '__main__':
    ok = main()
    sys.exit(0 if ok else 1)
