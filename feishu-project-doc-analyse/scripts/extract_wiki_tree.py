#!/usr/bin/env python3
"""
Extract Feishu wiki tree structure by intercepting API responses.

Two modes:
1. By space URL — navigates to the wiki space, captures tree API calls, saves nodes
2. By space ID — directly calls the tree API (requires valid cookies)

Usage:
  python3 extract_wiki_tree.py --space-url "https://<tenant>.feishu.cn/wiki/space/7316177914184073244"
  python3 extract_wiki_tree.py --space-id 7316177914184073244

Output: ./wiki_nodes.json — list of {title, wiki_token, obj_token, obj_type, url}
"""
import os, json, time, sys, argparse, glob

# Display setup may be needed for API interception mode
if not os.environ.get("DISPLAY"):
    os.environ["DISPLAY"] = ":0"

from playwright.sync_api import sync_playwright

COOKIE_FILE = "./feishu_cookies.json"
OUTPUT_FILE = "./wiki_nodes.json"


def find_chrome():
    home = os.path.expanduser('~')
    for pattern in [
        os.path.join(home, '.cache/ms-playwright/chromium-*/chrome-linux64/chrome'),
        os.path.join(home, '.cache/ms-playwright/chromium-*/chrome'),
    ]:
        matches = glob.glob(pattern)
        if matches:
            return sorted(matches)[0]

    import shutil
    for cmd in ["google-chrome", "chromium"]:
        path = shutil.which(cmd)
        if path:
            return path
    raise RuntimeError("No Chromium found")


def load_cookies():
    if not os.path.exists(COOKIE_FILE):
        raise RuntimeError(
            "No cookies found at %s. Run launch_browser.py first to log in."
            % COOKIE_FILE
        )
    with open(COOKIE_FILE) as f:
        return json.load(f)


def extract_via_browser(space_url, cookies):
    """Navigate to wiki space, intercept tree API responses."""
    captured = []

    def on_response(response):
        url = response.url
        if "wiki/v2/tree/get_info" in url or "wiki/v2/tree/get_node" in url:
            try:
                data = response.json()
                captured.append({"url": url, "data": data})
            except Exception:
                pass

    chrome_path = find_chrome()
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            executable_path=chrome_path,
            args=["--no-sandbox"]
        )
        ctx = browser.new_context(viewport={"width": 1920, "height": 1080})
        ctx.add_cookies(cookies)
        page = ctx.new_page()
        page.on("response", on_response)

        page.goto(space_url, wait_until="domcontentloaded", timeout=30000)
        # Wait for tree API to fire
        for _ in range(20):
            time.sleep(0.5)
            if captured:
                break
        time.sleep(3)

        browser.close()

    return captured


def parse_wiki_nodes(api_responses):
    """Extract document nodes from tree API responses."""
    nodes = []
    seen_tokens = set()

    for resp in api_responses:
        data = resp.get("data", {})
        tree = data.get("data", {}).get("tree", {})

        # The tree has a "nodes" dict keyed by node ID
        tree_nodes = tree.get("nodes", {})
        if not tree_nodes:
            # Try alternate format
            tree_nodes = data.get("nodes", {})

        for node_id, node in tree_nodes.items():
            title = (node.get("title") or node.get("obj_title") or "").strip()
            if not title:
                continue

            wiki_token = node.get("wiki_token", "")
            obj_token = node.get("obj_token", "")
            obj_type = node.get("obj_type", 0)

            if wiki_token in seen_tokens:
                continue
            seen_tokens.add(wiki_token)

            nodes.append({
                "title": title,
                "wiki_token": wiki_token,
                "obj_token": obj_token,
                "obj_type": obj_type,
                "url": node.get("url", "") or "https://<tenant>.feishu.cn/wiki/" + wiki_token,
                "has_child": node.get("has_child", False),
                "parent_wiki_token": node.get("parent_wiki_token", ""),
            })

    return nodes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--space-url", help="Wiki space URL")
    parser.add_argument("--space-id", help="Wiki space ID (if known)")
    parser.add_argument("--tenant", default="<tenant>", help="Feishu tenant name")
    args = parser.parse_args()

    cookies = load_cookies()
    tenant_url = "https://%s.feishu.cn" % args.tenant

    if args.space_url:
        space_url = args.space_url
    elif args.space_id:
        space_url = "%s/wiki/space/%s" % (tenant_url, args.space_id)
    else:
        print("ERROR: Provide --space-url or --space-id")
        sys.exit(1)

    print("Navigating to: %s" % space_url)
    responses = extract_via_browser(space_url, cookies)
    print("Captured %d API responses" % len(responses))

    nodes = parse_wiki_nodes(responses)
    print("Found %d wiki nodes" % len(nodes))

    # Save
    with open(OUTPUT_FILE, "w") as f:
        json.dump(nodes, f, ensure_ascii=False, indent=2)
    print("Saved to: %s" % OUTPUT_FILE)

    # Print summary
    type_names = {3: "sheet", 8: "folder", 22: "docx", 23: "shortcut"}
    for node in nodes:
        tname = type_names.get(node["obj_type"], "type_%d" % node["obj_type"])
        print("  [%s] %s" % (tname, node["title"]))


if __name__ == "__main__":
    main()
