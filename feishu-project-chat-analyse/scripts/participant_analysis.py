#!/usr/bin/env python3
"""
人员活跃度分析
- 统计每个参与者的消息数量
- 分析活跃度
- 识别关键贡献者
"""
import os
import json
from collections import defaultdict
from datetime import datetime


def analyze_participants(input_file, output_file):
    """分析参与者活跃度"""
    
    # 读取预处理后的消息
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    chat_name = data.get('chat_name', '')
    messages = data.get('messages', [])
    
    print(f"[INFO] 分析 {len(messages)} 条消息的参与者...")
    
    # 统计每个参与者的信息
    participant_stats = defaultdict(lambda: {
        'message_count': 0,
        'first_message': None,
        'last_message': None,
        'active_days': set(),
        'mentions_count': 0,
        'messages': []
    })
    
    for msg in messages:
        sender = msg.get('sender', '')
        time_str = msg.get('time', '')
        content = msg.get('content', '')
        has_mention = msg.get('has_mention', False)
        
        if not sender:
            continue
        
        stats = participant_stats[sender]
        stats['message_count'] += 1
        
        # 记录第一条和最后一条消息
        if stats['first_message'] is None:
            stats['first_message'] = time_str
        stats['last_message'] = time_str
        
        # 记录活跃日期
        try:
            date = time_str.split(' ')[0] if ' ' in time_str else time_str
            stats['active_days'].add(date)
        except:
            pass
        
        # 统计@提及
        if has_mention:
            stats['mentions_count'] += 1
        
        # 保存最近的消息
        if len(stats['messages']) < 5:
            stats['messages'].append({
                'time': time_str,
                'content': content[:100]
            })
    
    # 转换为列表并排序
    participants = []
    for sender, stats in participant_stats.items():
        participants.append({
            'name': sender,
            'message_count': stats['message_count'],
            'first_message': stats['first_message'],
            'last_message': stats['last_message'],
            'active_days': len(stats['active_days']),
            'mentions_count': stats['mentions_count'],
            'recent_messages': stats['messages']
        })
    
    # 按消息数量排序
    participants.sort(key=lambda x: x['message_count'], reverse=True)
    
    # 计算统计信息
    total_messages = len(messages)
    unique_participants = len(participants)
    avg_messages = total_messages / unique_participants if unique_participants > 0 else 0
    
    # 生成报告
    report = f"""# {chat_name} - 人员活跃度分析

> **Skill**: Feishu Project Chat Analyzer v0.1.0  
> **公众号简介**: 分享各种Agent实战经验，欢迎交流  
> 
> Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Messages: {total_messages} | Participants: {unique_participants}

## 参与者摘要

- **总消息数**: {total_messages}
- **参与人数**: {unique_participants}
- **平均消息数**: {avg_messages:.1f} 条/人
- **最活跃参与者**: {participants[0]['name'] if participants else 'N/A'} ({participants[0]['message_count'] if participants else 0} 条消息)

## 活跃度排名

| 排名 | 姓名 | 消息数 | 活跃天数 | @提及次数 | 首次发言 | 最后发言 |
|------|------|--------|----------|-----------|----------|----------|
"""
    
    for i, p in enumerate(participants, 1):
        report += f"| {i} | {p['name']} | {p['message_count']} | {p['active_days']} | {p['mentions_count']} | {p['first_message']} | {p['last_message']} |\n"
    
    report += "\n## 参与者详情\n\n"
    
    for i, p in enumerate(participants[:20], 1):  # 只显示前20名
        report += f"""### {i}. {p['name']}

- **消息数量**: {p['message_count']} 条
- **活跃天数**: {p['active_days']} 天
- **@提及次数**: {p['mentions_count']} 次
- **首次发言**: {p['first_message']}
- **最后发言**: {p['last_message']}

**最近消息**:

"""
        for msg in p['recent_messages'][:3]:
            report += f"- [{msg['time']}] {msg['content']}\n"
        
        report += "\n"
    
    # 保存报告
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n[INFO] 已生成报告: {output_file}")
    print(f"[INFO] 共 {unique_participants} 个参与者")
    
    if participants:
        print(f"\n[INFO] 最活跃的前5名:")
        for i, p in enumerate(participants[:5], 1):
            print(f"  {i}. {p['name']}: {p['message_count']} 条消息, {p['active_days']} 天活跃")
    
    return participants


def main():
    import argparse
    parser = argparse.ArgumentParser(description='分析参与者活跃度')
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
        args.output = f"./feishu_analysis/reports/{name_without_prefix}_participant_analysis.md"
    
    # 确保输出目录存在
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    
    # 分析参与者
    analyze_participants(args.input, args.output)


if __name__ == '__main__':
    main()
