---
name: feishu-project-doc-analyse
version: 1.0
description: >
  Use when the user wants to browse, analyze, or summarize Feishu (飞书/Lark) documents, wikis, or knowledge bases.
  Triggers on requests like "analyze Feishu docs for project X", "browse our company wiki",
  "summarize the Feishu knowledge base", "scan our 飞书文档 for Y", or any task involving
  programmatic access to Feishu document content. Also use when the user asks to "log into Feishu"
  to browse documents.
---

# Feishu Project Document Analyzer

> **Version**: 1.0  
> **Author**: Victor  
> **公众号**: 安卓一得  
> **简介**: 分享各种Agent实战经验，欢迎交流

## 📖 功能说明

**通过飞书文档获取项目的上下文信息**

本Skill帮助AI助手从飞书文档中提取项目知识，让AI能够：
- 理解项目历史背景和技术演进
- 掌握关键约束和技术债务
- 识别活跃风险和团队分工
- 像团队成员一样思考和协助

Systematically browse Feishu wiki/knowledge bases, extract document content,
and produce a structured analysis report.

## Prerequisites

The user's environment must have:
- Playwright for Python installed (`python3 -c "from playwright.sync_api import sync_playwright"`)
- A Chromium executable (Playwright-bundled or system)
- SSH X11 forwarding active (`DISPLAY` environment variable set) for the login step

## Workflow

### Phase 1: Login & Session Setup

1. Ask the user for the Feishu starting URL (e.g., `https://<tenant>.feishu.cn/drive/home/`)

2. Launch a **persistent, headless=False** browser **IN BACKGROUND** using the bundled `scripts/launch_browser.py`:
   ```bash
   python3 scripts/launch_browser.py "<feishu_url>"
   ```

   **CRITICAL: This script MUST be run in background mode** (use `run_in_background=true` in Claude Code).
   The script launches a persistent browser and does NOT exit automatically — it runs continuously
   to keep the browser session alive for subsequent operations.

   **Why headless=False:** Feishu is an SPA that requires JavaScript execution for login and content rendering.
   The user must complete login (QR scan / SMS) in the visible browser window.

3. **After launching, tell the user**: "Browser launched. Please complete login in the browser window (QR code or SMS). Tell me when login is complete."

4. **Wait for user confirmation** before proceeding to Phase 2. Do NOT continue until the user explicitly confirms login is done.

5. The script auto-saves cookies to `./feishu_cookies.json` whenever they change. You can communicate with the running browser via `./feishu_cmd.json` command file (see script documentation for available commands).

6. When all operations are complete, close the browser by writing `{"action":"quit"}` to `./feishu_cmd.json` or stopping the background task.

### Phase 2: Wiki Tree Discovery

4. With the cookies from Phase 1, extract the wiki space structure using `scripts/extract_wiki_tree.py`:
   ```bash
   python3 scripts/extract_wiki_tree.py --space-id <space_id> --space-url "<url>"
   ```
   If you don't know the space ID, navigate the browser to the wiki space page first —
   the script intercepts the tree API call and saves node data to `./wiki_nodes.json` (current directory).

   The output contains:
   - `title` — document name
   - `wiki_token` — used to construct the document URL: `https://<tenant>.feishu.cn/wiki/<wiki_token>`
   - `obj_token` — the underlying docx object token
   - `obj_type` — 22 for docx, 8 for folder, 3 for sheet, etc.

5. **By default, extract and analyze ALL documents matching the project keywords.**
   Do NOT ask the user which subset to focus on — proceed with all relevant documents automatically.
   Only ask if the document count exceeds 200 or if the user explicitly requests a subset.

6. **Alternative: Search-based discovery** (when wiki tree is incomplete or user wants broader search)
   
   Use `scripts/search_feishu.py` to search for documents by keywords:
   ```bash
   python3 scripts/search_feishu.py \
     --keywords "[Project A]" "[Project B]" "[Product B1]" \
     --exclude "[Exclude Keyword 1]" "[Exclude Keyword 2]" \
     --output ./feishu_search_results.json
   ```
   
   This script implements the optimized search strategy:
   - Clicks search icon (not Control+k)
   - Scrolls 3000px per iteration (not 1500px)
   - Waits 2 seconds after each scroll (not 0.5s)
   - Stops after 10 consecutive rounds with no new content (not 5)
   - Maximum 100 scroll iterations (not 50)

## Feishu Search Technique

**Correct way to trigger search:**
- Click the search icon in the top-right corner of the page
- Do NOT use `Control+k` keyboard shortcut (doesn't work reliably)
- **CRITICAL: You must click "Advanced Search"** (the button/link in the search dialog) to open the full search results page. The quick search box only shows "Recently viewed" pages, NOT actual search results. Pressing Enter in the quick search box will just open the first matching document instead of showing a results list.

**Search results container:**
- Search results are displayed in a **scrollable container** inside the search dialog, NOT the main page window
- The container selector is typically `._results_*` or `[class*="advance-search-results"]`
- You MUST scroll this container, not `window.scrollBy()` — scrolling the window does nothing
- To find the container programmatically:
  ```javascript
  const dialog = document.querySelector('[role="dialog"]');
  const allEls = dialog.querySelectorAll('*');
  for (const el of allEls) {
      const style = getComputedStyle(el);
      if ((style.overflow === 'auto' || style.overflowY === 'auto')
          && el.scrollHeight > el.clientHeight + 50) {
          // This is the scroll container — scroll this, not window
          el.scrollBy(0, 3000);
      }
  }
  ```

**Scrolling strategy for complete results:**
- **Scroll target**: the search results container (see above), NOT `window`
- **Scroll distance**: 3000px per iteration (not 1500px)
- **Wait time after scroll**: 2 seconds (not 0.5s) to let content load
- **Stop threshold**: 10 consecutive rounds with no new content (not 5)
- **Max rounds**: 100 iterations (not 50)

**Example:**
```python
# Step 1: Click search icon
search_icon = page.query_selector('[class*="search"]')
if search_icon and search_icon.is_visible():
    search_icon.click()
    time.sleep(2)

# Step 2: Type keyword
page.keyboard.type(keyword, delay=50)
time.sleep(3)

# Step 3: CRITICAL — Click "Advanced Search" to open full results page
# Do NOT press Enter here! Enter opens the first document, not search results.
advanced_search = page.query_selector('text=Advanced Search')
if advanced_search:
    advanced_search.click()
    time.sleep(3)

# Step 4: Find the scrollable results container inside the dialog
container_selector = page.evaluate("""() => {
    const dialog = document.querySelector('[role="dialog"]');
    if (!dialog) return null;
    const allEls = dialog.querySelectorAll('*');
    for (const el of allEls) {
        const style = window.getComputedStyle(el);
        if ((style.overflow === 'auto' || style.overflowY === 'auto')
            && el.scrollHeight > el.clientHeight + 50) {
            const cls = (el.className || '').toString().substring(0, 50);
            return '.' + cls.split(' ')[0];
        }
    }
    return null;
}""")

# Step 5: Progressive scrolling WITHIN the container
last_count = 0
no_change_count = 0
for scroll_round in range(100):
    links = page.evaluate("... extract all links from container ...")
    new_docs = count_new_links(links)
    print(f"Round {scroll_round+1}: {len(links)} links, +{new_docs} new")

    if len(links) == last_count:
        no_change_count += 1
        if no_change_count >= 10:
            break
    else:
        no_change_count = 0
        last_count = len(links)

    # Scroll the CONTAINER, not the window!
    if container_selector:
        page.evaluate(f"""() => {{
            const el = document.querySelector('{container_selector}');
            if (el) el.scrollBy(0, 3000);
        }}""")
    time.sleep(2)
```

### Phase 3: Content Extraction

6. For each target document, extract content using `scripts/extract_doc_content.py`:
   ```bash
   python3 scripts/extract_doc_content.py --doc-list ./target_docs.json --output ./feishu_docs/
   ```

   **Critical extraction technique — the result of trial and error:**

   - **Use headless=False** — content renders properly only with a real display
   - **Feishu uses virtual scrolling** — content is lazy-loaded, only rendered in the visible viewport.
     You MUST scroll the document container to load all content.
   - **Find the scrollable container** — look for elements with `overflow-y: auto/scroll` and
     `scrollHeight > clientHeight + 100`. The main container is typically `.bear-web-x-container`
     or `.page-main-item`. Use the tallest one.
   - **Scroll step by step** — scroll the container by ~85% of viewport height each step,
     wait 0.8s for content to render, then extract text from the visible viewport.
   - **Merge and deduplicate** — collect text from each scroll position, merge all lines,
     deduplicate by exact line content to avoid repetition.
   - **Stop at SSR JS markers** — when processing merged text, stop at the first line containing:
     `.wikiSSRBox{`, `!function(){`, `window.secondChunk`, `window.fourthChunk`, `document.cookie=`
   - **Filter sidebar noise** — remove lines that are purely navigation (Feishu Docs, Search, Home, Drive, etc.)
   - **Wait for initial render** — after page load, wait 4s for the first screen to render before scrolling

   **IMPORTANT: Save extracted documents to the current project directory, NOT /tmp.**
   Create a subdirectory named `<project>_docs_content/` in the current working directory to store all extracted `.txt` files.
   This ensures the extracted content is preserved alongside the analysis reports.

   Each extracted document is saved as a `.txt` file in the project directory.

### Phase 3.5: Preparation (CRITICAL — Do NOT skip)

Before generating reports, you MUST complete these steps:

1. **Read ALL extracted documents**
   ```bash
   # Read every .txt file in the output directory
   for f in ./<project>_docs_content/*.txt; do
       echo "=== $f ==="
       cat "$f"
   done
   ```
   Store key findings in variables for later reference.

2. **Build document-to-code mapping**
   Search the codebase for terms mentioned in documents:
   - File names (e.g., `xxx_drv.c`)
   - Function names (e.g., `display_Init`, `Write_Yyy_Version`)
   - Constants/macros (e.g., `VID_PID`, `RESOLUTION_3840_1920`)
   - Commit messages related to document topics

3. **Identify cross-document patterns**
   - Which documents reference each other?
   - What contradictions or gaps exist?
   - What is the project timeline/evolution?

4. **Reconstruct tables from extracted content**
   Tabular data in SSR text preserves cell content but loses layout.
   Rebuild tables with clear markdown column headers.

### Phase 4: Analysis & Report — Two Modes

7. **Generate TWO separate reports (DO NOT combine into one):**

   **Mode A: 详细文档归档** (`<project>_detailed_document_archive.md`)
   - 逐篇文档深入分析，关联分析，交叉分析，文档覆盖评估
   - Structure: Knowledge Base Overview → Core Documents Detailed Analysis → Team Organization → External Documents → Key Insights

   **Mode B: 项目上下文知识** (`<project>_project_context_knowledge.md`)
   - 历史包袱/技术债务、关键约束、活跃风险、隐性知识
   - Structure: Project Snapshot → Historical Baggage → Key Constraints → Active Risks → Tacit Knowledge → Future Assistance Guide

   If the user explicitly requests only one mode, generate only that report.
   Default behavior: generate BOTH reports.

8. **Choose analysis mode based on user's answer:**

#### Mode A: Detailed Document Archive (when user wants complete documentation)

Read ALL extracted documents thoroughly. Produce a **detailed, substantial, and archive-quality** analysis report. Use the existing report structure (sections 1-N+3).

**Template for each document section (MUST follow):**

```markdown
### N.M [Document Title]

> **Author**: ... | **Modified**: ... | **wiki_token**: ... | **Category**: ...

**Content Summary**:
- Key point 1 with details
- Key point 2 with details
- [Reconstruct any tables found in the document]

**Code Association**:
- Related files: `path/to/file.c`, `path/to/header.h`
- Related functions: `function_name()`, `another_function()`
- Related commits: `abc123 Fix the issue...`
- Configuration: `#define MACRO_NAME value`

**Historical Context**:
- How this document relates to other documents
- What project phase this covers
- What was carried forward from older projects or changed

**Key Findings**:
- What this document reveals about the project
- Any issues, risks, or decisions documented


#### Mode B: Project Context Knowledge (when user wants AI to understand the project)

**Purpose**: Help the AI assistant think and act like a team member who knows the project history.

**Focus on**:
- **Historical baggage & tech debt** — What are the landmines? What should I watch out for?
- **Key constraints** — What can't be changed? What are the hard rules?
- **Active risks** — What's happening now? What's in progress?
- **Tacit knowledge** — Why did they choose A over B? What's the real reason?
- **Team & ownership** — Who owns what? Who made what decisions?

**Output structure**:

```markdown
# [Project Name] - Project Context Knowledge

> **Skill**: Feishu Project Document Analyzer v1.0  
> **Skill 作者**: Victor  
> **作者公众号**: 安卓一得  
> **公众号简介**: 分享各种Agent实战经验，欢迎交流  
> 
> Purpose: Help AI assistant understand project background
> Generated: YYYY-MM-DD | Source: N documents

## 1. Project Snapshot (Where We Are Now)
- Product matrix: products, SoCs, kernels, status
- Code repositories: branches, strategies
- Core team: who owns what

## 2. Historical Baggage & Tech Debt (Landmines)
For each issue:
- 🔴 High /  Medium / 🟢 Low risk
- Problem: what went wrong
- Impact: what's affected
- Root cause: why it happened
- Warning: what to watch out for

## 3. Key Constraints (What Can't Be Changed)
- Factory constraints: processes that can't be modified
- Hardware constraints: fixed designs, dependencies
- Interface constraints: APIs, protocols, formats

## 4. Active Risks (What's Happening Now)
For each risk:
- 🔥 Active / ⚠️ Pending
- Status: current state
- Owner: who's responsible
- Impact: what could go wrong

## 5. Tacit Knowledge (What Docs Don't Say)
- Why X is slower than Y
- Why they reused Z
- Why problem P was never fully fixed
- Trade-offs and real reasons behind decisions

## 6. Future Assistance Guide (How I Should Help)
- When coding: what to check, what to remember
- When debugging: who to find, where to look
- When deciding: what matrix to consult

*This knowledge evolves as project understanding deepens.*
```

#### Analysis Principles (MUST follow for both modes)

️ **COMMON FAILURE MODE — DO NOT DO THIS:**
- ❌ Creating a bullet list of document titles without analysis
- ❌ Writing one-sentence summaries per document
- ❌ Skipping code association because "it's too much work"
- ❌ Combining multiple documents into one generic section

**Depth over breadth**: For each document with extractable content, write a full section explaining what was found, why it matters, and how it relates to the codebase. A one-sentence summary per document is insufficient.

**Minimum effort per document (Mode A):**
- 3-5 bullet points of content summary
- At least 1 code association (file path or function name)
- 1-2 sentences of historical context
- If you cannot find code associations, explicitly say "No direct code association found" and explain why

**Asset association**: For every document, explicitly identify related project assets based on project type:
- **Software projects**: source files, functions, modules, configuration files (e.g., `aaa/bbb/xxx/yyy.c`)
- **Hardware projects**: components, schematics, PCB layouts, BOM items, datasheets
- **Design projects**: design phases, CAD files, review checkpoints, deliverables
- **Testing projects**: test cases, test procedures, test equipment, acceptance criteria
- **Management projects**: milestones, deliverables, resource assignments, timelines
- **Operations projects**: service catalogs, incident records, monitoring configs, SLAs
- **Sales projects**: customer accounts, opportunities, quotes, contracts, forecasts
- **Marketing projects**: campaigns, leads, content assets, analytics, channel metrics
- **After-sales projects**: support tickets, repair records, customer feedback, warranty claims
- **Product manager projects**: product requirements, user stories, roadmaps, feature specs
- **Algorithm projects**: algorithm specs, model versions, training datasets, performance metrics
- **Structural projects**: CAD models, mechanical drawings, BOMs, assembly instructions
- **Supply chain projects**: supplier records, purchase orders, inventory levels, logistics
- **Quality management projects**: quality standards, inspection records, defect reports, audits
- **Manufacturing projects**: production orders, work instructions, yield reports, capacity plans
- **Production testing projects**: test procedures, test results, fixture specifications, coverage
- **Finance projects**: budget items, cost centers, financial reports, forecasts
- **IT projects**: system configurations, network assets, service requests, incidents
- **Human resources projects**: employee records, job postings, training records, reviews
- **IP & legal projects**: patent applications, contracts, compliance records, legal risks
- **Administrative projects**: facility requests, procurement orders, admin procedures

Use specific identifiers from the actual project (file paths, component IDs, document numbers, ticket IDs, employee IDs, patent numbers, etc.).

**Cross-document synthesis**: Do not treat each document in isolation. Identify patterns, contradictions, dependencies, and knowledge gaps across documents. Example: flag that "Document A describes the OTA upgrade flow, but Document B reveals a bug caused by incomplete flag cleanup — these are directly connected."

**Historical context**: Trace how projects evolved. When a newer doc references an older project (e.g., [Project A] inheriting from [Legacy Project]), explain the lineage and what was carried forward vs. changed.

**Table reconstruction**: When extracted content contains tabular data (endpoint allocations, CPU binding maps, timing comparisons), reconstruct the table in markdown with clear column headers. The extracted SSR text preserves cell content even when layout is lost — use the positional cues to rebuild the table structure.

**Gap analysis**: After all documents are processed, explicitly list which areas are well-documented, which are sparse, and which key documents could not be fully extracted (requiring manual review).

#### Report Structure

```markdown
# [Project Name] - Feishu Document Knowledge Base Analysis

> **Skill**: Feishu Project Document Analyzer v1.0  
> **Skill 作者**: Victor  
> **作者公众号**: 安卓一得  
> **公众号简介**: 分享各种Agent实战经验，欢迎交流  
>
> Generated: YYYY-MM-DD | Source: <feishu_url> | Documents: N

## Table of Contents (with hyperlinks to all H2/H3 sections)

## 1. Knowledge Base Overview & Architecture
### 1.1 Project System & Scope
Table mapping project components to products, platforms, tools, deliverables, status
- For software projects: code systems, build tools, output formats
- For hardware projects: components, specifications, manufacturing processes
- For design projects: design phases, deliverables, review milestones
- For project management: phases, milestones, resource allocation
- For operations projects: service levels, SLAs, KPIs, operational procedures
- For sales projects: sales targets, pipelines, customer segments, conversion rates
- For marketing projects: campaigns, channels, metrics, ROI analysis
- For after-sales projects: support tickets, resolution times, customer satisfaction, warranty claims
- For product manager projects: product requirements, user stories, roadmaps, feature prioritization
- For algorithm projects: algorithms, models, training data, performance metrics, accuracy benchmarks
- For structural projects: mechanical designs, CAD models, tolerances, materials, assembly processes
- For supply chain projects: suppliers, procurement, inventory, logistics, cost optimization
- For quality management projects: quality standards, inspection criteria, defect tracking, compliance
- For manufacturing projects: production plans, work orders, capacity planning, yield rates
- For production testing projects: test fixtures, test procedures, pass/fail criteria, test coverage
- For finance projects: budgets, cost analysis, financial forecasts, expense tracking
- For IT projects: infrastructure, systems, networks, security, IT service management
- For human resources projects: recruitment, training, performance reviews, employee engagement
- For IP & legal projects: patents, trademarks, contracts, compliance, legal risk assessment
- For administrative projects: office management, facilities, procurement, administrative procedures

### 1.2 Repository & Asset Landscape
Overview of all project repositories and asset locations:
- Code repositories (Gerrit, Git, etc.) - for software projects
- Document repositories (Wiki, Drive, etc.) - for all projects
- Design files (CAD, schematics, etc.) - for hardware/design projects
- Test assets (test plans, test reports) - for testing projects
- Operations assets (runbooks, monitoring configs) - for operations projects
- Sales assets (CRM data, sales decks, proposals) - for sales projects
- Marketing assets (campaign materials, analytics) - for marketing projects
- After-sales assets (knowledge bases, FAQ docs) - for after-sales projects
- Product assets (PRDs, user research, roadmaps) - for product manager projects
- Algorithm assets (model files, datasets, benchmarks) - for algorithm projects
- Structural assets (CAD files, BOMs, drawings) - for structural projects
- Supply chain assets (supplier contracts, inventory records) - for supply chain projects
- Quality assets (inspection reports, defect logs) - for quality management projects
- Manufacturing assets (production schedules, work instructions) - for manufacturing projects
- Testing assets (test plans, test results, fixture designs) - for production testing projects
- Finance assets (financial models, budget spreadsheets) - for finance projects
- IT assets (system configs, network diagrams) - for IT projects
- HR assets (job descriptions, training materials) - for human resources projects
- Legal assets (patent filings, contract templates) - for IP & legal projects
- Admin assets (office policies, facility records) - for administrative projects

### 1.3 Complete Document Inventory
Full table: Name | Type | Owner | Last Modified | wiki_token | Category
Categorize EVERY document into: <Project>-specific, Shared, Management, Technical, Handover

## 2-N. [Each major project/product/component] Core Documents — Detailed Analysis
For EACH document with extractable content:
### N.M [Document Title]
> Author: ... | Modified: ... | wiki_token: ...

Full content summary with bullet points, reconstructed tables, key findings.
**Association mapping** (adapt to project type):
- Software: specific file paths, function names, configuration files
- Hardware: component references, schematic pages, BOM items
- Design: design phases, review checkpoints, deliverables
- Testing: test cases, test procedures, acceptance criteria
- Management: milestones, deliverables, resource assignments
- Operations: service catalogs, incident records, change requests
- Sales: customer accounts, opportunities, quotes, contracts
- Marketing: campaigns, leads, conversions, brand assets
- After-sales: support tickets, repair records, customer feedback
- Product manager: product requirements, user stories, feature specs
- Algorithm: algorithm specs, model versions, training datasets
- Structural: CAD models, mechanical drawings, assembly instructions
- Supply chain: supplier records, purchase orders, inventory levels
- Quality management: quality standards, inspection records, defect reports
- Manufacturing: production orders, work instructions, yield reports
- Production testing: test procedures, test results, fixture specifications
- Finance: budget items, cost centers, financial reports
- IT: system configurations, network assets, service requests
- Human resources: employee records, job postings, training records
- IP & legal: patent applications, contracts, compliance records
- Administrative: facility requests, procurement orders, admin procedures

Historical context: relation to other projects/versions/phases.

## N+1. Team Organization & Personnel
### Core members & responsibilities table
### Known handovers and departures
### Cross-functional collaboration patterns

## N+2. External Documents & Resources
Documents and resources not in primary wiki but referenced:
- Software: OTA packages, SDK releases, vendor integrations
- Hardware: datasheets, application notes, manufacturer docs
- Design: design guidelines, standards, reference designs
- Testing: test standards, compliance docs, certification requirements
- Operations: vendor SLAs, service agreements, compliance docs
- Sales: market research, competitor analysis, pricing strategies
- Marketing: industry reports, brand guidelines, media kits
- After-sales: warranty policies, service level agreements, product manuals
- Product manager: market research, competitor products, user feedback
- Algorithm: research papers, open-source models, benchmark datasets
- Structural: material specifications, industry standards, supplier catalogs
- Supply chain: supplier certifications, logistics contracts, trade regulations
- Quality management: industry standards (ISO, etc.), compliance requirements
- Manufacturing: equipment manuals, safety regulations, industry best practices
- Production testing: test standards, calibration certificates, equipment specs
- Finance: tax regulations, accounting standards, financial compliance docs
- IT: vendor contracts, software licenses, security standards
- Human resources: labor laws, benefit plans, industry salary surveys
- IP & legal: patent databases, legal precedents, regulatory requirements
- Administrative: vendor contracts, facility management standards

## N+3. Key Insights & Cross-Analysis
### **Mapping to project assets**: link each doc to specific project components
- Software: files, functions, commits, modules
- Hardware: components, schematics, PCB layouts, BOMs
- Design: design phases, review gates, deliverables
- Testing: test cases, procedures, equipment, environments
- Management: milestones, deliverables, resources, timelines
- Operations: services, incidents, changes, problems
- Sales: customers, opportunities, deals, forecasts
- Marketing: campaigns, channels, audiences, content
- After-sales: tickets, repairs, replacements, feedback
- Product manager: features, requirements, roadmaps, releases
- Algorithm: models, datasets, experiments, metrics
- Structural: parts, assemblies, materials, tolerances
- Supply chain: suppliers, orders, inventory, shipments
- Quality management: standards, inspections, defects, audits
- Manufacturing: orders, processes, equipment, yields
- Production testing: tests, fixtures, results, coverage
- Finance: budgets, expenses, forecasts, reports
- IT: systems, networks, services, incidents
- Human resources: employees, positions, training, reviews
- IP & legal: patents, contracts, compliance, risks
- Administrative: facilities, procurement, services, policies

### Technology/product evolution trend: project lineage from older → current → future
### Cross-component reuse & risks: specific examples found (code reuse, component reuse, design patterns)
### Document coverage assessment: per-subsystem/area rating (✅ detailed / ⚠️ partial / ❌ missing)
### Recommended next actions: prioritized list
```

#### Example of expected depth

For a "startup keywords" document, do NOT write:
> "This doc lists peripheral startup keywords. PERIPHERAL_CONNECTED means device detected."

Instead write:
> "The startup keywords document defines the canonical boot sequence for [Project] devices.
> Peripheral detection follows a three-stage pipeline:
> `peripheral [controller] initialized` → `STATE=DETECTED` → `STATE=READY`,
> logged in system.log and debug.log respectively. This maps to
> `[repo]/apps/[module]/` initialization and `[sdk]/[driver]/` driver code.
> The timestamp `[1.684]` serves as a startup performance baseline.
> When debugging the reset wakeup issue, these state transitions repeat
> after each hard_reset, making them diagnostic markers."

9. **Pre-save Verification Checklist** (MUST complete before saving)

   **Mode A Checklist:**
   - [ ] Every extracted document has a dedicated section (NOT just a list entry)
   - [ ] Each section includes: Author, Modified date, wiki_token, Category
   - [ ] Each section includes Code Association (file paths, function names)
   - [ ] Each section includes Historical Context
   - [ ] Cross-document analysis section exists (Section N+3)
   - [ ] Document-to-code mapping table exists
   - [ ] Technology evolution trend documented
   - [ ] Cross-project code reuse risks identified
   - [ ] Document coverage assessment with ratings (✅/⚠️/❌)
   - [ ] Recommended next actions with priorities

   **Mode B Checklist:**
   - [ ] Risk level tags used (🔴 High / 🟡 Medium / 🟢 Low)
   - [ ] Each Historical Baggage item has: Problem, Impact, Root cause, Warning
   - [ ] Each Active Risk has: Status, Owner, Impact
   - [ ] Key Constraints organized by type (Factory/Hardware/Interface)
   - [ ] Tacit Knowledge explains WHY decisions were made
   - [ ] Future Assistance Guide has specific, actionable advice

   **If any checkbox is NOT checked, go back and fix it before saving.**

10. Save the reports to the current working directory:
   - Mode A: `<project>_detailed_document_archive.md`
   - Mode B: `<project>_project_context_knowledge.md`

### Phase 5: Cleanup

10. Close the persistent browser when done.
11. Offer to save key findings to Claude memory for future sessions.

## Common Pitfalls

- **"page you were looking for doesn't exist"** — The URL format is `/wiki/<wiki_token>` (NOT `/wiki/wik<token>`).
  The `wiki_token` from the tree API is the full token.
- **"Only outline/TOC extracted, no real content"** — Feishu uses virtual scrolling. The first screen only shows
  the document outline. You MUST find the scrollable container (`.bear-web-x-container` typically), scroll it
  step by step, and merge content from each viewport position. See Phase 3 extraction technique.
- **"Content is very short (<500 chars)"** — Virtual scrolling not triggered. Check if you found the correct
  scrollable container (`overflow-y: auto` and `scrollHeight > clientHeight + 100`).
- **"SSR JS mixed with content"** — The stop-marker logic didn't fire. Check if marker strings appear in the document.
  Some docs have inline scripts; extend the marker list if needed.
- **"Cookies expire mid-session"** — Re-run the login phase. The cookie file auto-refreshes during browsing.

## Best Practices: File Organization

**IMPORTANT**: All generated files should be organized in a structured directory, NOT scattered in the current directory.

### Recommended Directory Structure

When analyzing Feishu documents, create the following structure in the current working directory:

```
feishu_analysis/
├── README.md              # Usage instructions
├── data/                  # Raw data and intermediate results
│   ├── feishu_cookies.json           # Login cookies (sensitive!)
│   ├── feishu_search_urls.json       # Search result URLs
│   ├── feishu_*_extracted.json       # Extracted document content
│   └── wiki_nodes.json               # Wiki tree structure
├── reports/               # Analysis reports
│   ├── <project>_detailed_document_archive.md
│   ├── <project>_project_context_knowledge.md
│   └── analysis_logs.md
├── scripts/               # Custom scripts (if any)
└── logs/                  # Git logs, execution logs
```

### Why This Matters

- ✅ **Persistence**: Files in organized directories survive system reboots
- ✅ **Maintainability**: Easy to find and manage related files
- ✅ **Reusability**: Structure can be reused across different projects
- ✅ **Git-friendly**: Easy to add to version control with proper .gitignore

### Implementation

1. **Create directory before starting**:
   ```bash
   mkdir -p feishu_analysis/{data,reports,scripts,logs}
   ```

2. **Save all outputs to appropriate subdirectories**:
   - Data files → `feishu_analysis/data/`
   - Reports → `feishu_analysis/reports/`
   - Logs → `feishu_analysis/logs/`

3. **Create README.md** with usage instructions and file descriptions

4. **Add .gitignore** to protect sensitive data:
   ```
   feishu_analysis/data/feishu_cookies.json
   feishu_analysis/data/feishu_cmd.json
   ```

### Example Workflow

```bash
# 1. Create structure
mkdir -p feishu_analysis/{data,reports}

# 2. Login and save cookies
python3 scripts/launch_browser.py "https://<tenant>.feishu.cn/drive/home/"
# Cookies saved to: ./feishu_analysis/data/feishu_cookies.json

# 3. Search and save results
python3 scripts/search_feishu.py \
  --keywords "[Project A]" "[Project B]" \
  --output ./feishu_analysis/data/feishu_search_results.json

# 4. Extract documents
python3 scripts/extract_doc_content.py \
  --doc-list ./feishu_analysis/data/feishu_search_urls.json \
  --output ./feishu_analysis/data/feishu_docs/

# 5. Generate reports (saved to feishu_analysis/reports/)
```

**NEVER** save files directly in the current directory like:
- ❌ `./feishu_cookies.json`
- ❌ `./feishu_search_results.json`
- ❌ `./analysis_report.md`

**ALWAYS** use the structured directory:
- ✅ `./feishu_analysis/data/feishu_cookies.json`
- ✅ `./feishu_analysis/data/feishu_search_results.json`
- ✅ `./feishu_analysis/reports/analysis_report.md`

## Bundled Scripts

- `scripts/launch_browser.py` — Launch persistent GUI browser, save cookies
- `scripts/extract_wiki_tree.py` — Capture Feishu wiki tree API responses
- `scripts/extract_doc_content.py` — Extract document content using tested selectors and filters
- `scripts/search_feishu.py` — Search documents by keywords with optimized scrolling strategy
