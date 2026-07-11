#!/usr/bin/env python3
"""
决策追踪分析
- 识别重要决策
- 追踪决策形成过程
- 记录决策参与者
"""
import os
import json
import re
from datetime import datetime


def analyze_decisions(input_file, output_file):
    """分析决策"""
    
    # 读取预处理后的消息
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    chat_name = data.get('chat_name', '')
    messages = data.get('messages', [])
    
    print(f"[INFO] 分析 {len(messages)} 条消息中的决策...")
    
    # 决策关键词
    decision_keywords = [
        '决定', '确定', '同意', '通过', '批准', '确认',
        '方案', '方案一', '方案二', '选择', '采用',
        '最终', '结论', '结果', '定了',
        'decide', 'decision', 'agree', 'approve', 'confirm',
        'finalize', 'conclusion', 'choose', 'select'
    ]
    
    # 识别决策消息
    decisions = []
    
    for i, msg in enumerate(messages):
        content = msg.get('content', '')
        sender = msg.get('sender', '')
        time_str = msg.get('time', '')
        
        # 检查是否包含决策关键词
        is_decision = any(keyword in content for keyword in decision_keywords)
        
        if is_decision:
            # 获取上下文（前后各3条消息）
            context_before = messages[max(0, i-3):i]
            context_after = messages[i+1:min(len(messages), i+4)]
            
            # 提取参与者
            participants = set([sender])
            for ctx_msg in context_before + context_after:
                participants.add(ctx_msg.get('sender', ''))
            
            decisions.append({
                'decision': content,
                'timestamp': time_str,
                'decision_maker': sender,
                'participants': list(participants),
                'context_before': [
                    {
                        'time': m.get('time', ''),
                        'sender': m.get('sender', ''),
                        'content': m.get('content', '')[:100]
                    }
                    for m in context_before
                ],
                'context_after': [
                    {
                        'time': m.get('time', ''),
                        'sender': m.get('sender', ''),
                        'content': m.get('content', '')[:100]
                    }
                    for m in context_after
                ]
            })
    
    print(f"[INFO] 识别 {len(decisions)} 个决策")
    
    # 生成报告
    report = f"""# {chat_name} - 决策追踪

> **Skill**: Feishu Project Chat Analyzer v0.1.0  
> **公众号简介**: 分享各种Agent实战经验，欢迎交流  
> 
> Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Messages: {len(messages)} | Decisions: {len(decisions)}

## 决策摘要

- **总消息数**: {len(messages)}
- **识别决策数**: {len(decisions)}
- **决策参与者**: {len(set(p for d in decisions for p in d['participants']))} 人

## 决策详情

"""
    
    for i, decision in enumerate(decisions, 1):
        report += f"""### 决策 {i}: {decision['decision'][:50]}...

- **时间**: {decision['timestamp']}
- **决策者**: {decision['decision_maker']}
- **参与者**: {', '.join(decision['participants'][:10])}

**决策内容**:

{decision['decision']}

**讨论上下文**:

决策前:
"""
        for ctx in decision['context_before']:
            report += f"- [{ctx['time']}] {ctx['sender']}: {ctx['content']}\n"
        
        report += "\n决策后:\n"
        for ctx in decision['context_after']:
            report += f"- [{ctx['time']}] {ctx['sender']}: {ctx['content']}\n"
        
        report += "\n---\n\n"
    
    # 保存报告
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n[INFO] 已生成报告: {output_file}")
    
    if decisions:
        print(f"\n[INFO] 前3个决策:")
        for i, decision in enumerate(decisions[:3], 1):
            print(f"  {i}. [{decision['timestamp']}] {decision['decision_maker']}: {decision['decision'][:50]}...")
    
    return decisions


def main():
    import argparse
    parser = argparse.ArgumentParser(description='分析决策')
    parser.add_argument('--input', required=True, help='输入文件路径')
    parser.add_argument('--output', help='输出报告路径')
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"[ERROR] 输入文件不存在: {args.input}")
        return
    
    # 生成输出文件名
    if not args.output:
        base_name = os.path.basename(args.input)
        name_without_ext = os.path.splitext(base_name)[0]
        name_without_prefix = name_without_ext.replace('preprocessed_', '')
        args.output = f"./feishu_analysis/reports/{name_without_prefix}_decision_analysis.md"
    
    # 确保输出目录存在
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    
    # 分析决策
    analyze_decisions(args.input, args.output)


if __name__ == '__main__':
    main()
