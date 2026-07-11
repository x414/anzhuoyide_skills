# Feishu Project Chat Analyzer

> **Version**: 0.3.5
> **公众号**: 安卓一得

## 🔬 核心突破：累积捕获 + 鼠标定位

飞书Web端使用**虚拟列表**（Virtual List），向上滚动加载历史消息时，视口外的旧消息会被**卸载**。常规方法只能获取当前视口的消息，无法得到完整历史。

### 突破方案（2026-06-25验证）

#### 1. 鼠标定位到消息容器中心
飞书的消息容器 `.lark-chat-right .scroller` 必须获得鼠标焦点，`page.mouse.wheel()` 的滚轮事件才能触发懒加载。

```python
container_info = page.evaluate('''() => {
    const el = document.querySelector(".lark-chat-right .scroller");
    if (el) {
        const rect = el.getBoundingClientRect();
        return {x: rect.x + rect.width/2, y: rect.y + rect.height/2, found: true};
    }
    return {found: false};
}''')
page.mouse.move(container_info['x'], container_info['y'])
page.mouse.click(container_info['x'], container_info['y'])
```

#### 2. 累积捕获（解决虚拟列表卸载）
每轮滚动后立即捕获 `.lark-chat-right` 的 `innerText`，保存所有快照，最后合并去重。

```python
all_snapshots = []
unique_lines = set()
accumulated_lines = []

for _ in range(total_scrolls):
    page.mouse.wheel(0, -random.randint(200, 500))
    time.sleep(random.uniform(1.5, 3.0))
    
    current = page.evaluate('''() => {
        const el = document.querySelector(".lark-chat-right");
        return el ? el.innerText : "";
    }''')
    
    for line in current.split("\n"):
        stripped = line.strip()
        if len(stripped) > 1 and stripped not in unique_lines:
            unique_lines.add(stripped)
            accumulated_lines.append(stripped)
```

#### 3. 真实鼠标滚轮（非JS scrollTop）
JS 的 `scrollTop` 修改不会触发飞书的懒加载。必须使用 `page.mouse.wheel()` 发送真实滚轮事件。

### 验证效果

| 指标 | 改进前 | 改进后 | 提升 |
|------|--------|--------|------|
| 字符数 | 4,514 | 11,293 | **2.5x** |
| 行数 | 157 | 356 | **2.3x** |
| 日期覆盖 | 7天 | 14天 | **2x** |

## 🚀 快速开始

```bash
# 提取聊天消息（完整历史，默认30分钟滚动）
python3 scripts/extract_chat_messages.py \
  --chat-name "<项目讨论群>" \
  --output ./feishu_analysis/data/messages_project.json

# 自定义滚动参数（适合消息量特别大的群）
python3 scripts/extract_chat_messages.py \
  --chat-name "<项目讨论群>" \
  --duration 3600 \
  --scroll-min 200 --scroll-max 500 \
  --pause-min 1.5 --pause-max 3.0 \
  --output ./feishu_analysis/data/messages_project.json
```

## 🛠️ 脚本说明

### 核心脚本
| 脚本 | 功能 |
|------|------|
| `launch_browser.py` | 启动浏览器，自动加载/保存 cookies |
| `search_feishu_groups.py` | 搜索所有相关群（支持选择器 fallback） |
| `extract_chat_messages_v6.py` | 提取单群完整历史（推荐） |
| `batch_extract.py` | 批量提取多群（增量+重试+报告） |
| `get_chat_list.py` | 获取聊天列表 |

### 分析脚本
| 脚本 | 功能 |
|------|------|
| `deep_context_mining.py` | 10维度深度项目分析 |
| `topic_analysis.py` | 讨论主题分析 |
| `decision_analysis.py` | 决策追踪分析 |
| `issue_analysis.py` | 问题追踪分析 |
| `participant_analysis.py` | 人员活跃度分析 |
| `preprocess_messages.py` | 消息预处理 |

### 共享模块
| 脚本 | 功能 |
|------|------|
| `feishu_selectors.py` | CSS 选择器 fallback 链 |
| `config.py` | 统一配置管理 |
| `incremental_state.py` | 增量提取状态跟踪 |
| `check_setup.py` | 环境检查工具 |

## ⚠️ 注意事项

1. **鼠标定位**: 滚动前必须将鼠标移动到消息容器中心，否则懒加载不触发
2. **累积捕获**: 飞书使用虚拟列表，旧消息会被卸载。必须每轮保存快照并合并去重
3. **真实滚轮**: 使用 `page.mouse.wheel()` 而非 JS `scrollTop`
4. **滚动时长**: 默认30分钟，消息量大的群建议增加

## 🐛 常见问题

### Q: 消息提取不完整（只有当前视口的几条）？
A: 请确认：
   1. 鼠标是否定位到了 `.lark-chat-right .scroller` 中心
   2. 是否使用了 `page.mouse.wheel()` 而非 JS `scrollTop`
   3. 是否启用了累积捕获（每轮保存快照并合并去重）
   4. 滚动时长是否足够（建议30分钟以上）

## 📝 版本历史

### v0.3.5 (2026-07-07)
- **Bug Fixes**: 修复硬编码关键词、DISPLAY环境、cookie加载等问题
- **P0 - 选择器 Fallback**: 新增 `feishu_selectors.py`，UI变更时自动切换备选选择器
- **P0 - 批量提取**: 新增 `batch_extract.py`，标准化多群提取流程
- **P1 - 增量更新**: 新增 `incremental_state.py`，二次提取自动跳过未变化群
- **P1 - 配置外部化**: 新增 `config.py` + `config_example.yaml`，支持YAML配置
- **工程化**: 新增 `requirements.txt`、`.gitignore`、`check_setup.py`

### v0.2.0 (2026-06-25)
- 重大突破: 累积捕获 + 鼠标定位方案，完整提取聊天记录
- 解决飞书虚拟列表卸载旧消息的问题
- 解决 `page.mouse.wheel()` 需要鼠标在容器上的问题

### v0.1.0 (2026-06-17)
- 初始版本
- 浏览器自动化获取聊天记录
- 4种分析模式（主题、决策、问题、参与者）



---

##  分析报告规范

### 时间线标注规则

**必须为所有时间线添加年份标注**，无论是否跨年：

| 场景 | 格式 | 示例 |
|------|------|------|
| 单年 | `## 关键时间线 (2025年)` | `## 关键时间线 (2025年6月)` |
| 跨年 | `## 关键时间线 (2025-2026 跨年)` | `## 关键时间线 (2025-2026 跨年)` |

**时间线条目格式**：
```
2025年4月
Apr 8 ── 主线/user分支策略明确
Apr 24 ── 周末生产准备

2026年6月
Jun 24 ─ 830版本交付
```

**注意**：
- 飞书消息日期格式不统一（`Jun 4`、`Jun 4, 3:50 PM`、`Jun 4, 2025`），需统一标注年份
- 跨年群必须分段展示（按年份分组）
- 单年群也要标注年份，避免歧义


##  分析范围要求（强制）

**必须分析所有与目标项目相关的群聊**，不能只分析部分群。

### 执行流程

1. **获取完整聊天列表**
   - 使用 ArrowDown 导航左侧列表（推荐，可加载虚拟列表）
   - 滚动至少 300 次，确保加载所有群
   - 保存完整列表到 `chat_list_all.json`

2. **筛选项目相关群**
   - 匹配关键词：项目名（如"<Project>"）、项目缩写、相关术语
   - 注意：群名可能包含空格、大小写变体
   - 保存筛选结果到 `chat_list_project.json`

3. **逐一提取每个群**
   - 使用 `extract_any_chat.py` 或 `extract_chat_messages.py`
   - 每个群生成独立的数据文件

4. **生成分析报告**
   - 对每个群生成独立分析报告（包含时间线，必须标注年份）
   - 最后生成**跨群综合报告**，梳理群间协作关系

### 跨群综合报告要求

综合报告必须包含：
- 所有相关群的概览对比表
- 群协作模式图（协作流程、数据流向）
- 核心主题跨群分析
- 核心成员跨群活跃度
- 关键决策汇总（按时间线）
- 待解决问题（标注涉及群）

**注意**:
- 飞书使用虚拟列表，必须通过 ArrowDown 或滚轮滚动才能加载所有群
- 已提取的群跳过，避免重复
- 时间线必须标注年份，无论是否跨年
