#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
libai_engine.py — 诗仙李白风格作诗引擎
以李白之风骨，融使用者之性情，临场应景，借古喻今。
"""

import json
import os
import sys
import random
from pathlib import Path
from datetime import datetime

# ── 路径 ──
BASE_DIR = Path(__file__).parent
STYLE_PATH = BASE_DIR / "libai_style.json"
USER_MEMORY_PATH = Path.home() / ".openclaw" / "workspace" / "MEMORY.md"
USER_PROFILE_PATH = Path.home() / ".openclaw" / "workspace" / "USER.md"

# ── 加载李白风格库 ──
def load_libai_style():
    with open(STYLE_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

# ── 读取当前用户画像（运行时动态加载）──
def load_user_profile():
    """
    动态读取当前使用者的用户画像。
    从标准路径读取 MEMORY.md 和 USER.md，提取公开信息用于个性化作诗。
    若未找到或信息为空，则返回 None（使用通用画像）。
    """
    profile = None
    
    # 尝试读取 USER.md
    if USER_PROFILE_PATH.exists():
        try:
            text = USER_PROFILE_PATH.read_text(encoding='utf-8')
            profile = {}
            # 提取姓名（简单启发式）
            for line in text.splitlines():
                line = line.strip()
                if line.startswith('- **Name:**') or line.startswith('**Name:**'):
                    profile['name'] = line.split(':', 1)[1].strip()
                elif line.startswith('- **职位**：') or '职位' in line and '：' in line:
                    profile['identity'] = line.split('：', 1)[1].strip()
                elif line.startswith('- **所在地**：') or '常驻地点' in line:
                    profile['location'] = line.split('：', 1)[1].strip()
                elif '领域' in line and ('：' in line or ':' in line):
                    interests_str = line.split('：', 1)[1].strip() if '：' in line else line.split(':', 1)[1].strip()
                    profile['interests'] = [i.strip() for i in interests_str.split('、') if i.strip()]
        except Exception:
            pass
    
    # 尝试读取 MEMORY.md 补充近期信息
    if USER_MEMORY_PATH.exists():
        try:
            text = USER_MEMORY_PATH.read_text(encoding='utf-8')
            if profile is None:
                profile = {}
            # 简单提取：只取非隐私的通用标签
            if '跑步' in text or '运动' in text:
                profile.setdefault('interests', []).append('运动')
            if '孩子' in text or '家庭' in text:
                profile['has_family'] = True
        except Exception:
            pass
    
    # 清理：若 profile 为空或只有空值，返回 None
    if not profile:
        return None
    
    # 过滤掉过于私人的字段，只保留可用于诗歌意象的通用标签
    safe_profile = {}
    if profile.get('name'):
        safe_profile['name'] = profile['name']
    if profile.get('identity'):
        safe_profile['identity'] = profile['identity']
    if profile.get('location'):
        safe_profile['location'] = profile['location']
    if profile.get('interests'):
        # 只保留可以转化为诗歌意象的兴趣
        poetic_interests = []
        for i in profile['interests']:
            i = i.strip()
            if i in ['技术', '编程', 'AI', 'AR', 'VR', '文学', '历史', '旅行', '跑步', '运动', '音乐', '摄影']:
                poetic_interests.append(i)
        if poetic_interests:
            safe_profile['interests'] = poetic_interests
    if profile.get('has_family'):
        safe_profile['has_family'] = True
    
    return safe_profile if safe_profile else None

# ── 意象选择器 ──
def select_imagery(theme, style, user_profile=None):
    """
    根据主题和用户信息选择最贴合的意象组合
    """
    img = style["imagery_system"]
    selected = []
    
    # 主题映射
    theme_map = {
        "思乡": [img["celestial"]["moon"]],
        "壮志": [img["artifacts"]["sword"], img["mythical"]["creatures"][0]],
        "孤独": [img["celestial"]["moon"], img["nature"]["mountains"]],
        "豪情": [img["artifacts"]["wine"], img["artifacts"]["sword"]],
        "山水": [img["nature"]["mountains"], img["nature"]["water"]],
        "送别": [img["artifacts"]["boat"], img["nature"]["water"]],
        "自由": [img["mythical"]["creatures"][0], img["celestial"]["clouds"]],
        "酒": [img["artifacts"]["wine"]],
        "月": [img["celestial"]["moon"]],
        "剑": [img["artifacts"]["sword"]]
    }
    
    if theme in theme_map:
        selected.extend(theme_map[theme])
    
    # 根据用户画像调整
    if user_profile:
        if "AR" in user_profile.get("interests", []):
            selected.append({"symbol": "镜", "variants": ["明镜", "玉镜", "瑶镜"], "emotions": ["洞察", "虚实"]})
        if "北京" in user_profile.get("location", ""):
            selected.append({"symbol": "燕", "variants": ["燕山", "燕地", "幽燕"], "emotions": ["雄壮", "苍茫"]})
        if "跑步" in user_profile.get("interests", []):
            selected.append({"symbol": "风", "variants": ["长风", "疾风", "猎猎风"], "emotions": ["速度", "力量"]})
    
    return selected

# ── 生成作诗 prompt ──
def build_poem_prompt(theme, form="七言绝句", situation="", user_profile=None):
    style = load_libai_style()
    
    # 选择意象
    imagery = select_imagery(theme, style, user_profile)
    
    # 构建意象描述
    imagery_desc = []
    for item in imagery:
        if isinstance(item, dict) and "symbol" in item:
            imagery_desc.append(f"{item['symbol']}（{'、'.join(item.get('variants', [])[:3])}）")
        elif isinstance(item, dict) and "variants" in item:
            imagery_desc.append(f"{list(item.keys())[0] if len(item)>1 else '意象'}（{'、'.join(item['variants'][:3])}）")
    
    # 风格关键词
    temperament = "、".join(style["style_core"]["temperament"])
    mood = random.choice(style["style_core"]["mood_spectrum"])
    
    # 用户个性化注入
    user_context = ""
    if user_profile:
        name = user_profile.get("name", "友人")
        identity = user_profile.get("identity", "")
        location = user_profile.get("location", "")
        interests = user_profile.get("interests", [])
        
        if identity:
            user_context += f"为一位{identity}"
        if location:
            user_context += f"，家住{location}"
        if interests:
            user_context += f"，平日关注{'、'.join(interests[:3])}"
        user_context += "而赋。"
    
    # 从主题分类中选取代表作作为参考
    theme_ref = ""
    if "masterpieces_by_theme" in style:
        # 尝试匹配主题
        matched_theme = None
        theme_keywords = {
            "酒": "饮酒豪放", "豪放": "饮酒豪放", "醉": "饮酒豪放",
            "月": "明月思乡", "思乡": "明月思乡", "故乡": "明月思乡",
            "剑": "剑与侠义", "侠": "剑与侠义", "战": "剑与侠义",
            "山": "山水行旅", "水": "山水行旅", "行旅": "山水行旅", "旅": "山水行旅",
            "鸟": "山水行旅", "花": "山水行旅", "春": "山水行旅", "秋": "山水行旅",
            "仙": "游仙与神话", "神话": "游仙与神话", "梦": "游仙与神话",
            "情": "闺怨与爱情", "爱": "闺怨与爱情", "思": "闺怨与爱情",
            "送": "送别与离别", "别": "送别与离别", "离": "送别与离别",
            "古": "怀古与咏史", "史": "怀古与咏史",
            "愁": "孤独与愁绪", "孤": "孤独与愁绪", "独": "孤独与愁绪"
        }
        for kw, cat in theme_keywords.items():
            if kw in theme and cat in style["masterpieces_by_theme"]:
                matched_theme = cat
                break
        
        if matched_theme:
            poems = style["masterpieces_by_theme"][matched_theme]
            selected_refs = random.sample(poems, min(2, len(poems)))
            theme_ref = "\n【李白同主题参考】\n"
            for p in selected_refs:
                theme_ref += f"《{p['title']}》：{p['lines'][0]}\n"
    
    # 形式说明
    form_desc = style["poetic_forms"].get(form, {"description": form})
    
    prompt = f"""请以诗仙李白的风格，作一首{form}。

【主题】{theme}
【情境】{situation if situation else '临场感怀'}
{user_context}
{theme_ref}
【李白风格指引】
- 气质：{temperament}
- 情感基调：{mood}
- 推荐意象：{', '.join(imagery_desc) if imagery_desc else '月、酒、剑、山、水'}
- 语言特征：善用夸张与想象，色彩浓烈（金、银、青、碧），句式自由奔放
- 常用表达：{"、".join(style["language_features"]["key_expressions"]["exclamations"][:3])}

【形式要求】
{form_desc.get('description', form)}
{form_desc.get('structure', '')}

【要求】
1. 必须严格符合{form}的格律（句数字数准确）
2. 融入李白的典型意象和语言风格
3. 结合给定情境和主题
4. 情感真挚，气势连贯
5. 诗后可附简短赏析（点明用典、意象、情感）

请直接输出诗歌，不要加多余解释。
"""
    return prompt

# ── 主入口 ──
def main():
    if len(sys.argv) < 2:
        print("用法: python3 libai_engine.py <主题> [诗体] [情境]")
        print("  主题: 壮志/思乡/山水/送别/酒/月/剑/自由/孤独...")
        print("  诗体: 七言绝句/五言绝句/七言古诗/乐府 (默认: 七言绝句)")
        print("  情境: 任意描述")
        sys.exit(1)
    
    theme = sys.argv[1]
    form = sys.argv[2] if len(sys.argv) > 2 else "七言绝句"
    situation = sys.argv[3] if len(sys.argv) > 3 else ""
    
    user_profile = load_user_profile()
    prompt = build_poem_prompt(theme, form, situation, user_profile)
    
    print(prompt)

if __name__ == "__main__":
    main()
