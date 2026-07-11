#!/usr/bin/env python3
"""
Launch a persistent Playwright browser for Feishu login.
Does NOT exit — keeps browser alive so cookies stay fresh.
Kill with Ctrl+C or send {"action":"quit"} to ./feishu_cmd.json

Usage: python3 launch_browser.py [feishu_url]
Default URL: https://<tenant>.feishu.cn/messenger

Features:
- Loads existing cookies if available (avoids re-login)
- Saves cookies to ./feishu_cookies.json periodically
- Accepts commands via ./feishu_cmd.json, writes results to ./feishu_result.json
"""
import os, json, time, sys, argparse

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

from playwright.sync_api import sync_playwright

# Paths
CHROME_PATHS = [
    os.path.expanduser('~/.cache/ms-playwright/chromium-*/chrome-linux64/chrome'),
    os.path.expanduser('~/.cache/ms-playwright/chromium-*/chrome'),
    os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-linux64/chrome"),
]
CMD_FILE = "./feishu_cmd.json"
RESULT_FILE = "./feishu_result.json"
COOKIE_FILE = "./feishu_cookies.json"


def find_chrome():
    """Find a usable Chromium binary."""
    import glob
    for pattern in CHROME_PATHS:
        matches = glob.glob(pattern)
        if matches:
            return sorted(matches)[0]
    # Try system chrome
    for cmd in ["google-chrome", "chromium", "chromium-browser"]:
        import shutil
        path = shutil.which(cmd)
        if path:
            return path
    raise RuntimeError("No Chromium found. Install: npx playwright install chromium")


def write_result(data):
    """Write result to file, handling race conditions."""
    try:
        with open(RESULT_FILE, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def load_cookies_if_exist(context):
    """Load existing cookies from file if available."""
    if os.path.exists(COOKIE_FILE):
        try:
            with open(COOKIE_FILE, "r") as f:
                cookies = json.load(f)
            if cookies:
                context.add_cookies(cookies)
                print(f"[INFO] Loaded {len(cookies)} cookies from {COOKIE_FILE}")
                return len(cookies)
        except Exception as e:
            print(f"[WARN] Failed to load cookies: {e}")
    return 0


def main():
    global COOKIE_FILE

    parser = argparse.ArgumentParser()
    parser.add_argument("url", nargs="?", default="https://<tenant>.feishu.cn/messenger")
    parser.add_argument("--cookies", default=COOKIE_FILE, help="Path to cookies file")
    args = parser.parse_args()

    COOKIE_FILE = args.cookies

    chrome_path = find_chrome()

    # Clean stale command file
    if os.path.exists(CMD_FILE):
        os.remove(CMD_FILE)

    write_result({"status": "starting", "message": "Launching browser..."})

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            executable_path=chrome_path,
            args=["--no-sandbox"]
        )
        context = browser.new_context()

        # Load existing cookies to avoid re-login
        cookie_count = load_cookies_if_exist(context)

        page = context.new_page()

        page.goto(args.url, wait_until="domcontentloaded", timeout=30000)
        print(f"Browser opened: {args.url}")
        if cookie_count > 0:
            print("[INFO] Existing cookies loaded. If still logged in, no action needed.")
        print("Please log in on the browser window if prompted.")
        write_result({
            "status": "ready",
            "url": page.url,
            "cookies_loaded": cookie_count,
            "message": "Please login on the browser window if needed"
        })

        last_cookie_count = cookie_count

        while True:
            time.sleep(2)

            # Auto-save cookies
            cookies = context.cookies()
            if len(cookies) > last_cookie_count:
                last_cookie_count = len(cookies)
                with open(COOKIE_FILE, "w") as f:
                    json.dump(cookies, f)
                print(f"Cookies saved: {len(cookies)}")
                write_result({"status": "cookies_updated", "count": len(cookies)})

            # Process commands
            if os.path.exists(CMD_FILE):
                try:
                    with open(CMD_FILE) as f:
                        cmd = json.load(f)
                    os.remove(CMD_FILE)

                    action = cmd.get("action", "")
                    timeout = cmd.get("timeout", 30)

                    if action == "navigate":
                        page.goto(cmd["url"], wait_until="domcontentloaded", timeout=timeout * 1000)
                        time.sleep(cmd.get("wait", 3))
                        write_result({
                            "status": "ok",
                            "url": page.url,
                            "title": page.title()
                        })

                    elif action == "screenshot":
                        path = cmd.get("path", "./feishu_screenshot.png")
                        page.screenshot(path=path, full_page=True)
                        write_result({"status": "ok", "path": path})

                    elif action == "get_text":
                        text = page.inner_text("body")
                        limit = cmd.get("limit", 10000)
                        write_result({
                            "status": "ok",
                            "text": text[:limit],
                            "length": len(text)
                        })

                    elif action == "scroll":
                        for _ in range(cmd.get("times", 10)):
                            page.evaluate("window.scrollBy(0, 1000)")
                            page.wait_for_timeout(300)
                        write_result({"status": "ok"})

                    elif action == "save_html":
                        html = page.content()
                        path = cmd.get("path", "./feishu_page.html")
                        with open(path, "w") as f:
                            f.write(html)
                        write_result({"status": "ok", "length": len(html)})

                    elif action == "extract_links":
                        links = page.evaluate("""() => {
                            const all = document.querySelectorAll('a');
                            return Array.from(all)
                                .map(a => ({text: a.innerText.trim(), href: a.href}))
                                .filter(l => l.text && l.href && l.href.includes('feishu.cn'));
                        }""")
                        write_result({
                            "status": "ok",
                            "count": len(links),
                            "links": links[:200]
                        })

                    elif action == "get_cookies":
                        cookies = context.cookies()
                        write_result({
                            "status": "ok",
                            "count": len(cookies),
                            "cookies": cookies
                        })

                    elif action == "quit":
                        browser.close()
                        write_result({"status": "quit"})
                        sys.exit(0)

                except Exception as e:
                    write_result({"status": "error", "message": str(e)})


if __name__ == "__main__":
    main()
