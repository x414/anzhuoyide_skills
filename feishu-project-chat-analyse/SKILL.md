---
name: feishu-project-chat-analyse
version: 0.3.5
description: >
  Use when the user wants to analyze Feishu (飞书/Lark) chat messages to understand project discussions,
  decisions, and issue tracking. Triggers on requests like "analyze chat history for project X",
  "summarize group chat discussions", "extract decisions from chat", or "track issues in chat messages".
---

# Feishu Project Chat Analyzer

> **Version**: 0.3.5  
> **作者公众号**: 安卓一得  
> **公众号简介**: 分享各种Agent实战经验，欢迎交流

## 📖 功能说明

**通过飞书聊天记录获取项目的讨论过程、决策和问题追踪，最终目的是让AI助手深度理解项目上下文，从而能够高效地协助解决项目相关问题。**

### 为什么需要这个Skill？

当你问AI "帮我看看这个bug"、"这个需求怎么实现"、"为什么测试失败了" 时，AI如果**不了解项目背景**，只能给出通用答案。通过分析飞书聊天记录，AI可以：
- 知道团队已经讨论过什么方案、为什么选择了当前方案
- 了解谁负责哪个模块，应该@谁确认
- 掌握项目当前阶段（EVT/DVT/MP）和已知风险
- 识别历史类似问题及其解决方案
- **从而给出针对性强、可执行的建议，而不是泛泛而谈**

### 本Skill帮助AI做到

- 理解项目讨论过程和决策形成
- 追踪问题的提出和解决
- 识别关键参与者和贡献者
- 生成讨论摘要和时间线
- **深度上下文挖掘：推断团队角色、追踪迭代、分析供应链瓶颈、识别跨项目冲突**

## 🎯 适用场景

- **辅助决策**：问AI技术选型时，AI知道团队之前的讨论和顾虑
- **问题排查**：问AI报错时，AI知道类似问题之前怎么解决的
- **代码审查**：AI知道模块间的依赖关系和设计约束
- **项目复盘**：回顾项目讨论过程和决策
- **知识提取**：从聊天记录中提取项目知识
- **团队协作分析**：分析团队沟通和参与度
- **项目上下文构建：让AI深度理解项目全貌（角色、阶段、风险、依赖），从而提供精准帮助**

## Prerequisites

The user's environment must have:
- Playwright for Python installed (`python3 -c "from playwright.sync_api import sync_playwright"`)
- A Chromium executable (Playwright-bundled or system)
- SSH X11 forwarding active (`DISPLAY` environment variable set) for the login step
- Access to Feishu web version

## 核心原则

### 原则1：穷尽提取

**当用户要求提取和分析某个项目的聊天记录时，必须提取所有相关群的全部对话，过程中不要询问是否继续提取。**

用户说提取所有、全部提取或类似表达时，意味着要穷尽所有相关群的完整聊天记录，不要中途停下来问还要不要继续。

### 原则2：服务于问题解决

**提取和分析聊天记录的最终目的，是让AI具备解决项目相关问题的能力。**

分析报告不是终点，而是手段。完整的分析应该让AI能够：
- 回答 "这个问题之前出现过吗？怎么解决的？"
- 判断 "这个方案行不行？团队之前讨论过类似的吗？"
- 推荐 "这个问题应该找谁确认？"
- 识别 "这个改动会影响哪些模块？有什么风险？"

因此，分析报告必须包含足够的**技术细节、人名、版本号、决策理由**，而不仅是高层概括。

## Workflow

### Phase 1: Login & Session Setup

1. Ask the user for the Feishu starting URL (e.g., `https://<tenant>.feishu.cn/messenger`)

2. Launch a **persistent, headless=False** browser using the bundled `scripts/launch_browser.py`:
   ```bash
   python3 scripts/launch_browser.py "<feishu_url>"
   ```
   This opens a Chromium window on the user's display and saves cookies to `./feishu_analysis/data/feishu_cookies.json`.

   **Why headless=False:** Feishu is an SPA that requires JavaScript execution for login and content rendering.
   The user must complete login (QR scan / SMS) in the visible browser window.

3. Wait for the user to confirm login is complete. The script auto-saves cookies whenever they change.

### Phase 2: Chat List Discovery (Optional Fallback)

`get_chat_list.py` extracts visible chats from the sidebar. It is NOT the primary discovery method because it misses:
- Groups not recently active in the sidebar
- Groups collapsed under "Show more"
- Groups not currently loaded in the UI

Use it only as a fallback when search-based discovery fails:
```bash
python3 scripts/get_chat_list.py --output ./feishu_analysis/data/chat_list.json
```

### Phase 2.5: Group Discovery (Primary Method)

**ALWAYS use `search_feishu_groups.py` as the primary group discovery tool.** It searches Feishu global search and automatically triggers lazy loading to find ALL matching groups.

```bash
# Single keyword is sufficient — lazy loading finds all results
python3 scripts/search_feishu_groups.py "<项目名>" --output ./groups_<project>.txt
```

**How it works:**
1. Opens Feishu search panel (Ctrl+K)
2. Types the keyword and clicks the Groups tab
3. Extracts the initial ~15 group results
4. **Automatically clicks the lazy-load trigger area** (`observerItem` / `search-more-placeholder`) below the last result card
5. Each click loads ~15 more groups until no new groups appear
6. Removes member count suffixes and deduplicates
7. Saves the complete list to the output file

**Example results:**
| Keyword | Groups Found |
|---------|-------------|
| `<项目名>` | ~100+ groups |
| `<项目名A>` | ~100+ groups |
| `<项目名B>` | ~80+ groups |

**Key insight:** Unlike the UI which requires manual scrolling to trigger lazy loading, the script directly clicks the invisible Intersection Observer trigger element, which reliably loads all paginated results.

**After discovery**, present the list to the user or default to all groups matching the project name.

---

6. **Use the Fast batch extractor** — it reuses the browser instance across groups, saving ~30s per group:
   ```bash
   # Single group
   python3 scripts/extract_chat_messages_fast.py "群名" ./feishu_data/
   
   # Batch extract all groups (recommended)
   python3 scripts/extract_chat_messages_fast.py --batch groups.txt --output-dir ./feishu_data/
   ```
   
   **Why Fast version:**
   | Metric | v6 | Fast | Improvement |
   |--------|-----|------|-------------|
   | Browser launch | Per group (~30s) | Once only | **-30s/group** |
   | Scroll sleep | 3.0s/round | 0.6s/round | **-2.4s/round** |
   | Avg time/group | ~5-8 min | ~40-60s | **~5-6x faster** |
   
   **Fallback**: If Fast version fails, use v6:
   ```bash
   python3 scripts/extract_chat_messages_v6.py "群名" ./feishu_data/<群名>.txt
   ```
   
   Each extracted chat is saved as a text file with accumulated unique lines.

### Phase 4: Message Preprocessing

7. Preprocess extracted messages using `scripts/preprocess_messages.py`:
   ```bash
   python3 scripts/preprocess_messages.py \
     --input ./feishu_analysis/data/messages_<chat_id>.json \
     --output ./feishu_analysis/data/preprocessed_<chat_id>.json
   ```

   Preprocessing steps:
   - Parse message content (JSON format)
   - Extract @mentions
   - Identify message threads (replies)
   - Normalize timestamps
   - Filter system messages
   - Extract links and attachments

### Phase 5: Analysis & Report — Multiple Modes

8. **Choose analysis mode based on user's goal:**

#### Mode A: Discussion Topic Extraction (when user wants to understand main topics)

**Purpose**: Identify and summarize the main discussion topics in the chat.

**Focus on**:
- **Topic identification** — What are the main topics discussed?
- **Topic evolution** — How did topics change over time?
- **Topic heat** — Which topics had the most discussion?
- **Topic participants** — Who participated in each topic?

#### Mode B: Decision Tracking (when user wants to trace decisions)

**Purpose**: Track how decisions were made in the chat.

**Focus on**:
- **Decision identification** — What decisions were made?
- **Decision context** — What was the discussion before the decision?
- **Decision participants** — Who was involved in the decision?
- **Decision timeline** — When were decisions made?

#### Mode C: Issue Tracking (when user wants to track problems)

**Purpose**: Track issues raised and resolved in the chat.

**Focus on**:
- **Issue identification** — What issues were raised?
- **Issue resolution** — How were issues resolved?
- **Issue timeline** — When were issues raised and resolved?
- **Issue participants** — Who raised and resolved issues?

#### Mode D: Participant Activity (when user wants to analyze participation)

**Purpose**: Analyze who participated and how active they were.

**Focus on**:
- **Participant list** — Who participated in the chat?
- **Activity level** — How active was each participant?
- **Contribution type** — What did each person contribute?
- **Activity trend** — How did activity change over time?


#### Mode E: Comprehensive Project Analysis (when user wants to understand the full project)

**Purpose**: Generate a comprehensive project analysis report from all extracted chats.

**Must include**:
- **Project Overview** — How many groups, total chars, participants
- **Core Team** — Top 30 active participants
- **Technology Keywords** — Most frequent technical terms
- **Version History** — Firmware/software versions mentioned
- **Project Phases** — EVT/DVT/RB stages
- **Main Technical Directions** — Camera/Display/Audio/Power/OTA/etc.
- **Known Issue Types** — Common problems and bug categories
- **Key Decisions/Events** — Product name changes, tech choices, etc.

**Implementation** (v0.3.6 — includes deduplication & enrichment):
```python
import os, re, glob
from collections import Counter, defaultdict

def dedup_lines(text):
    """Remove duplicate lines while preserving order."""
    seen = set()
    result = []
    for line in text.split('\n'):
        stripped = line.strip()
        if not stripped or stripped == '=== ROUND SEPARATOR ===':
            continue
        normalized = re.sub(r'\s+', ' ', stripped).strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(stripped)
    return '\n'.join(result)

def extract_topics(text):
    """Classify discussions by topic with deduplication."""
    topics = defaultdict(list)
    for line in text.split('\n'):
        line_lower = line.lower()
        if any(k in line_lower for k in ['sensor', '传感器', '替代料']):
            topics['IMU/Sensor'].append(line)
        elif any(k in line_lower for k in ['compiler', '编译器', 'arm compiler', '编译']):
            topics['Compiler/Build'].append(line)
        elif any(k in line_lower for k in ['display', 'screen', 'dp', 'oled', '分辨率', '刷新率', '视频']):
            topics['Display/DP'].append(line)
        elif any(k in line_lower for k in ['usb', 'hid', 'pd', '连接']):
            topics['USB/Connectivity'].append(line)
        elif any(k in line_lower for k in ['power', '功耗', '休眠', 'thermal', 'boot time', '待机']):
            topics['Power/Thermal'].append(line)
        elif any(k in line_lower for k in ['ota', 'upgrade', '升级', 'firmware update', '差分升级']):
            topics['OTA/Upgrade'].append(line)
        elif any(k in line_lower for k in ['factory', '量产', 'mp', 'pvt', 'dvt', 'evt', '产线', '备料']):
            topics['Manufacturing'].append(line)
        elif any(k in line_lower for k in ['bug', 'crash', '缺陷', '踩内存', '黑屏', '闪烁', '异常']):
            topics['Bug/Issue'].append(line)
        elif any(k in line_lower for k in ['version', 'firmware', '固件', 'release', 'boot', 'app', '版本号']):
            topics['Firmware/Version'].append(line)
        elif any(k in line_lower for k in ['rtos', '实时操作系统', '操作系统选型', 'os', '调度']):
            topics['RTOS/OS'].append(line)
    return {k: list(dict.fromkeys(v))[:15] for k, v in topics.items() if v}

def extract_decisions(text):
    """Extract decision/conclusion discussions."""
    decisions = []
    markers = ['决定', '确认', '定下来', '方案', '采用', '选择', '确定', '结论',
               'resolved', 'decision', 'agreed', 'approved', '同意', '通过']
    for line in text.split('\n'):
        line_stripped = line.strip()
        if 20 < len(line_stripped) < 500 and any(m in line_stripped for m in markers):
            decisions.append(line_stripped)
    return list(dict.fromkeys(decisions))[:20]

def extract_risks(text):
    """Extract risk/warning discussions."""
    risks = []
    markers = ['风险', '延期', '瓶颈', 'hold', '暂停', '阻塞', '问题', 'bug', 'fail',
               '失败', 'error', 'crash', '异常']
    for line in text.split('\n'):
        line_stripped = line.strip()
        if 15 < len(line_stripped) < 400 and any(m in line_stripped.lower() for m in markers):
            risks.append(line_stripped)
    return list(dict.fromkeys(risks))[:20]

def generate_comprehensive_report(data_dir, output_file):
    all_files = glob.glob(f'{data_dir}/*_v6.txt')
    
    total_orig = 0
    total_dedup = 0
    all_participants = Counter()
    all_keywords = defaultdict(int)
    all_versions = Counter()
    all_topics = defaultdict(list)
    all_decisions = []
    all_risks = []
    
    for file_path in all_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            raw = f.read()
        
        total_orig += len(raw)
        content = dedup_lines(raw)
        total_dedup += len(content)
        
        # Extract participants (via @mentions, more accurate than name regex)
        mentions = re.findall(r"@([一-龥]{2,4}|[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", content)
        exclude = {'All', 'Channel', 'Bot', 'Feishu', 'Jenkins', 'Build', 'Yesterday', 'Today',
                   'Search', 'Messenger', 'Knowledge', 'Calendar', 'Contacts', 'Email'}
        for m in mentions:
            if m not in exclude and len(m) > 1:
                all_participants[m] += 1
        
        # Extract keywords
        keyword_patterns = {
            'Audio': r'audio|Audio|音频|喇叭|speaker',
            'Power': r'power|Power|功耗|休眠|thermal|boot time',
            'Firmware': r'firmware|Firmware|固件|版本|version|boot|app',
            'Bug': r'bug|Bug|缺陷|crash|踩内存|黑屏|闪烁',
            'USB': r'USB|HID|PD|VID|PID',
            'Test': r'test|Test|测试|验证|压测|可靠性|Sorting',
            'DVT': r'DVT|dvt', 'EVT': r'EVT|evt',
            'PVT': r'PVT|pvt', 'MP': r'MP|mp|量产|备料|产线',
            'MCU': r'MCU|mcu|单片机|微控制器|Flash|Bootloader',
            'RTOS': r'RTOS|rtos|实时操作系统|操作系统选型|OS',
            'BOM': r'BOM|bom|物料|供应商|替代料|sourcing',
            'NPI': r'NPI|npi|试产|产测|IQC|产线测试|良率',
        }
        for k, pat in keyword_patterns.items():
            all_keywords[k] += len(re.findall(pat, content, re.IGNORECASE))
        
        # Extract versions
        versions = re.findall(r'\d+\.\d+\.\d+\.\d+[_-]\d{8}', content)
        all_versions.update(versions)
        
        # Extract topics, decisions, risks
        topics = extract_topics(content)
        for t, lines in topics.items():
            all_topics[t].extend(lines)
        all_decisions.extend(extract_decisions(content))
        all_risks.extend(extract_risks(content))
    
    # Deduplicate global collections
    for t in all_topics:
        all_topics[t] = list(dict.fromkeys(all_topics[t]))[:15]
    all_decisions = list(dict.fromkeys(all_decisions))[:20]
    all_risks = list(dict.fromkeys(all_risks))[:20]
    
    # Generate markdown report
    report = []
    report.append("# Project Comprehensive Analysis Report")
    report.append(f"- **Total Groups**: {len(all_files)}")
    report.append(f"- **Raw Chars**: {total_orig:,}")
    report.append(f"- **Deduped Chars**: {total_dedup:,} (compression: {100*(1-total_dedup/total_orig):.1f}%)")
    report.append(f"- **Participants**: {len(all_participants)}")
    report.append("")
    report.append("## Core Team (Top 30)")
    for idx, (name, count) in enumerate(all_participants.most_common(30), 1):
        report.append(f"{idx}. {name}: {count}")
    report.append("")
    report.append("## Technology Keywords")
    for keyword, count in sorted(all_keywords.items(), key=lambda x: x[1], reverse=True):
        if count > 0:
            report.append(f"- {keyword}: {count}")
    report.append("")
    report.append("## Version History")
    for version, count in all_versions.most_common(20):
        report.append(f"- {version}: {count} times")
    report.append("")
    report.append("## Topic Deep Dive")
    for topic, lines in sorted(all_topics.items(), key=lambda x: len(x[1]), reverse=True):
        report.append(f"### {topic} ({len(lines)} discussions)")
        for line in lines[:8]:
            display = line[:300] + '...' if len(line) > 300 else line
            report.append(f"- {display}")
        report.append("")
    report.append("## Key Decisions")
    for d in all_decisions[:15]:
        report.append(f"- {d[:250]}")
    report.append("")
    report.append("## Risks & Issues")
    for r in all_risks[:15]:
        report.append(f"- {r[:250]}")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report))
    
    return output_file
```

### Phase 6: Deep Context Mining ⭐ NEW in v0.3.0

**When to use**: When the user says "do deeper analysis", "挖掘更多上下文", "了解项目全貌", or asks for project context beyond surface-level summaries.

**Purpose**: 
- Extract project-level contextual knowledge to build a comprehensive mental model of the project
- **Enable the AI to answer project-specific questions with confidence** (e.g., "Why did we choose this type of chipset?", "Who should I ask about camera issues?", "Has this problem happened before?")
- Transform raw chat logs into **structured project intelligence** that persists across sessions

**Use the bundled script**:
```bash
python3 scripts/deep_context_mining.py \
    --input ./feishu_analysis/data/chat.txt \
    --output ./feishu_analysis/reports/report.md \
    --project-name "项目名称"
```

This script **auto-detects project type** (21 types based on  taxonomy) and performs **10 dimensions of deep mining**:

#### Dimension 1: Team Role Inference
- Extract @mention patterns to infer who-does-what
- Identify decision makers vs implementers vs reviewers
- Map core collaboration chains (problem → who → fix → who validates)

#### Dimension 2: Version/Release Iteration Tracking
- Track all version identifiers mentioned (firmware versions like `16.1.03.xxx`, semver like `v1.2.3`, or date versions)
- Correlate versions with dates and test/validation results
- Identify regression patterns (new release → fail → rollback → fix)
- **Auto-adapts**: Detects firmware-style versions for hardware projects, semver for software projects

#### Dimension 3: Test/Quality Issue Classification
- Categorize failures by type (functional, performance, compatibility, etc.)
- Track which quality dimensions fail most frequently
- Identify regression signatures (e.g., "rollback to old version works = new release introduced the issue")
- **Auto-adapts**: For hardware: test station failures; for software: bug categories; for service: SLA breaches

#### Dimension 4: Quantity/Scale Evolution
- Track how production quantities, team sizes, or resource allocations change over time
- Capture reasons for changes (customer demand, budget cuts, scope expansion, yield issues)
- Example patterns: EVT4 A:794→750→765 (customer cut → validation add); team: 5→8→12 (scaling up)

#### Dimension 5: Cross-Project Conflict Signals
- Look for mentions of other projects or teams
- Identify resource competition (shared personnel, budget conflicts, priority disputes)
- Spot priority hints ("Project X is more urgent" implies resource reallocation)

#### Dimension 6: External Dependency Timeline
- Extract vendor/supplier/partner names and decision milestones
- Track primary/alternative supplier selection rationale
- Note key dates (T0, sample, delivery commitments)
- Flag external risks explicitly called out by team members
- **Auto-adapts**: For hardware: BOM suppliers and 一供/二供; for software: third-party APIs/services; for service: outsourcing partners

#### Dimension 7: Action Items & Follow-ups
- Extract lines containing action verbs + @mentions
- Identify who is blocked waiting for whom
- Track unresolved items that appear multiple times

#### Dimension 8: Quality/Performance Metrics
- Extract quantitative metrics (FR: X/Y, success rate, latency, DAU, conversion rate)
- Track metric trends across releases or time periods
- Correlate metric drops with specific changes
- **Auto-adapts**: Hardware = yield/FR; Software = bug count/performance; Service = DAU/conversion/ROI

#### Dimension 9: Risk & Delay Warnings
- Extract explicit risk statements (延期, 瓶颈, Hold, 暂停)
- Identify critical path items with schedule pressure
- Flag "if X doesn't happen by Y, then Z is impossible" patterns

#### Dimension 10: Project Governance Mechanisms
- Extract group announcements (群公告)
- Identify meeting cadences (日会, 周报, standup, retro)
- Note纪律要求 (response time rules, escalation procedures, code review rules)
- Capture project charter elements (background, goals, milestones)

**Output**: A comprehensive markdown report with:
- Team role map (auto-inferred)
- Version/release issue tracking table
- Quantity/scale evolution timeline
- Cross-project conflict summary
- External dependency matrix
- Risk register
- Project governance rules
- A "Project Context Panorama" ASCII diagram

**Key insight**: This phase transforms raw chat logs into **structured project intelligence** that persists across sessions. Save key findings to Claude memory.

### Phase 7: Report Generation

9. Save the report to the **project directory**:
   ```bash
   # Reports go to project root, NOT skill directory
   ./<project>_comprehensive_analysis.md
   ./<project>_deep_context.md
   ```

### Phase 8: Cleanup

10. Close the persistent browser when done.
11. Offer to save key findings to Claude memory for future sessions.

## Best Practices: File Organization

**IMPORTANT**: All generated files MUST be saved to the **user's project directory** (current working directory), NOT the skill's internal directory (`~/.claude/skills/feishu-project-chat-analyse/`).

### Why This Matters
- The skill directory is ephemeral and shared across sessions
- Project data belongs with the project codebase
- Reports should be version-controlled alongside other project documents

### Recommended Directory Structure (in project root)

```
<project_root>/
├── feishu_data/           # Raw extracted chat data (MUST be here)
│   ├── <Project>_xxx.txt
│   ├── <Project>_yyy.txt
│   └── ... (one file per group)
├── <project>_comprehensive_analysis.md   # Phase 5 comprehensive report
├── <project>_deep_context.md            # Phase 6 deep context report
└── feishu_cookies.json   # Login cookies (sensitive! add to .gitignore)
```

### Rules
1. **Extracted chat data** → `./feishu_data/` or `./<project>_feishu_data/`
2. **Analysis reports** → `./<project>_analysis.md` or `./<project>_deep_context.md`
3. **Cookies** → Keep in skill directory or secure location, never commit to git
4. **Do NOT save** data/reports under `~/.claude/skills/feishu-project-chat-analyse/`

## Common Pitfalls

- **"Chat list is empty"** — The user may not have joined any group chats, or the page didn't load properly. Try refreshing the page.
- **"Messages not loading"** — Feishu loads messages dynamically. Make sure to scroll up to load more history.
- **"Cannot parse message content"** — Feishu message content is JSON format. Make sure to parse it correctly.
- **"Cookies expire mid-session"** — Re-run the login phase. The cookie file auto-refreshes during browsing.
- **"Cannot click group from search results"** — Use Playwright `locator` instead of JS click. See `extract_chat_messages_v6.py` for the reliable pattern.
- **"Scrolling doesn't load more history"** — You MUST position the mouse over the scroll container (`.lark-chat-right .scroller`) before sending wheel events.

## Bundled Scripts

### 核心提取脚本
- `scripts/launch_browser.py` — Launch persistent GUI browser, auto-load cookies
- `scripts/get_chat_list.py` — Extract chat list from Feishu messenger
- `scripts/search_feishu_groups.py` — **Search ALL groups by keyword** (enhanced lazy-loading + selector fallback)
- `scripts/extract_chat_messages.py` — Extract messages from a specific chat (basic)
- `scripts/extract_chat_messages_v6.py` — **Extract messages with locator click + scroll container positioning + incremental support** (recommended)
- `scripts/batch_extract.py` — **Batch extract multiple groups with retry & report** ⭐ NEW

### 分析脚本
- `scripts/preprocess_messages.py` — Preprocess extracted messages
- `scripts/deep_context_mining.py` — **Deep context mining: 10-dimension project intelligence extraction**
- `scripts/topic_analysis.py` — Topic extraction analysis
- `scripts/decision_analysis.py` — Decision tracking analysis
- `scripts/issue_analysis.py` — Issue tracking analysis
- `scripts/participant_analysis.py` — Participant activity analysis

### 共享模块
- `scripts/feishu_selectors.py` — **CSS selector fallback chain** (handles Feishu UI changes gracefully)
- `scripts/config.py` — **Unified configuration management** (supports config.yaml)
- `scripts/incremental_state.py` — **Incremental extraction state tracking** (skip already-extracted groups)

## Example: Analyzing Project Chat Analysis

```bash
# 1. Login to Feishu
python3 scripts/launch_browser.py "https://<tenant>.feishu.cn/messenger"

# 2. Discover ALL project-related groups
python3 scripts/search_feishu_groups.py <keyword> --output ./feishu_analysis/data/project_groups.txt

# 3. Extract messages from <Project> main group (v6 recommended)
# Edit extract_chat_messages_v6.py to set TARGET='<群名>', then:
python3 scripts/extract_chat_messages_v6.py

# 4. Deep context mining
python3 scripts/deep_context_mining.py
# (reads from feishu_analysis/data/project_main_group_v6.txt)

# 5. Review the generated report
# ./feishu_analysis/reports/<keyword>_main_group_ultra_deep.md
```

## Version History

### v0.3.0 (2026-07-01)

- Added **Phase 6: Deep Context Mining** — 10-dimension project intelligence extraction
- Added `scripts/deep_context_mining.py` for automated deep analysis
- Added `scripts/extract_chat_messages_v6.py` with Playwright locator click + scroll container positioning
- Extracted <项目主群> successfully: 647 lines, 73 days coverage, 28K chars
- Proven techniques: locator click > JS click, scroll container mouse positioning critical for lazy loading


### v0.3.5 (2026-07-07)

**Bug Fixes** — 修复4个关键脚本问题：

1. **`search_feishu_groups.py`** — 修复硬编码 "<keyword>" 关键词的bug
2. **`extract_chat_messages_v6.py`** — 改为命令行参数传入 TARGET 和 OUTPUT_FILE
3. **`get_chat_list.py`** — 添加 `DISPLAY` 环境变量设置
4. **`launch_browser.py`** — 启动时加载已有 cookies

**New Features** — 新增4个P0/P1优化：

1. **`feishu_selectors.py`** — CSS选择器fallback链 (P0)
   - 维护多个备选选择器，当首选选择器失效时自动尝试备用
   - 提供 `find_element()` 函数自动遍历fallback链
   - 提供 `debug_selectors()` 工具快速诊断UI变更

2. **`batch_extract.py`** — 批量提取标准化 (P0)
   - 支持从文件读取群列表批量提取
   - 自动重试失败任务
   - 生成 JSON 格式执行报告
   - 支持增量模式跳过已提取的群

3. **`incremental_state.py`** — 增量更新支持 (P1)
   - 记录每个群的提取状态（哈希、字符数、时间）
   - 二次提取时自动跳过未变化的群
   - 支持断点续传和状态重置

4. **`config.py` + `config_example.yaml`** — 配置外部化 (P1)
   - 统一 YAML/JSON 配置文件管理
   - 支持从 cookies 自动检测租户域名
   - 所有脚本参数可外部配置，无需改代码

### v0.3.3 (2026-07-01)

- **Date range format**: Changed from "覆盖XX天" to "YYYY年M月D日 ~ YYYY年M月D日" for clarity
- Auto-infers year from text (firmware version dates, announcements) or defaults to current year
- Applied to both report overview and project panorama sections

### v0.3.2 (2026-07-01)

- **Expanded to 21 project types** based on  taxonomy:
  software, hardware, design, testing, management, operations, sales, marketing,
  after-sales, product, algorithm, structural, supply-chain, quality, manufacturing,
  production-testing, finance, IT, HR, legal, admin
- Each type has dedicated: name, keywords, role hints, asset keywords, metric keywords
- Supports **mixed project detection** (e.g., "hardware+software" when both keyword sets score high)
- Role inference uses per-type role hint dictionaries (PM/engineer/QA/supplier/designer/...)

### v0.3.1 (2026-07-01)

- **Generalized** `deep_context_mining.py` for any project type (hardware/software/service/mixed)
- Auto-detects project type via keyword frequency analysis
- Auto-infers team roles from @mention patterns and context keywords
- Replaced hardware-specific terms with generic equivalents (version/release, external dependency, quality metrics)
- Added `is_person_name()` filter to exclude non-human entries from role map

### v0.2.0 (2026-06-30)

- Added `search_feishu_groups.py` for comprehensive group discovery
- Fixed lazy-loading issue with real mouse wheel scrolling
- Fixed selector issue: use `.search-result-container` instead of `.larkc-global-search-panel`
- Successfully found 73 project-related groups in production testing

### v0.1.0 (2026-06-17)
- Initial version
- Browser automation for chat extraction
- Four analysis modes (Topic, Decision, Issue, Participant)
- Structured report generation
