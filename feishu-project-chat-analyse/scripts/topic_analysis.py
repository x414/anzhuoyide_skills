#!/usr/bin/env python3
"""
讨论主题分析
- 识别主要讨论话题
- 话题热度排序
- 参与者统计
"""
import os
import json
import re
from collections import defaultdict, Counter
from datetime import datetime


def analyze_topics(input_file, output_file):
    """分析讨论主题"""
    
    # 读取预处理后的消息
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    chat_name = data.get('chat_name', '')
    messages = data.get('messages', [])
    stats = data.get('stats', {})
    
    print(f"[INFO] 分析 {len(messages)} 条消息的主题...")
    
    # 简单的话题识别（基于关键词）
    topic_keywords = {
        '技术问题': ['bug', '错误', '问题', '异常', '失败', 'crash', 'error', 'fix', '修复'],
        '功能开发': ['功能', 'feature', '开发', '实现', '新增', 'add', 'implement'],
        '进度同步': ['进度', '完成', '进展', '计划', 'schedule', 'progress', 'deadline'],
        '测试相关': ['测试', 'test', '验证', 'validate', 'QA', 'bug'],
        '版本发布': ['版本', 'release', '发布', '上线', 'deploy', 'v1', 'v2'],
        '性能优化': ['性能', '优化', 'performance', '速度', '慢', '快', 'optimize'],
        '代码审查': ['review', '审查', 'CR', 'code review', 'reviewer'],
        '需求讨论': ['需求', 'requirement', 'PRD', '产品', '用户'],
        '架构设计': ['架构', '设计', 'architecture', 'design', '方案'],
        '文档相关': ['文档', 'document', 'doc', '说明', 'README']
    }
    
    # 分析每条消息的主题
    topic_messages = defaultdict(list)
    topic_participants = defaultdict(set)
    topic_times = defaultdict(list)
    
    for msg in messages:
        content = msg.get('content', '').lower()
        sender = msg.get('sender', '')
        time_str = msg.get('time', '')
        
        # 识别主题
        identified_topics = []
        for topic, keywords in topic_keywords.items():
            if any(keyword in content for keyword in keywords):
                identified_topics.append(topic)
                topic_messages[topic].append(msg)
                topic_participants[topic].add(sender)
                topic_times[topic].append(time_str)
        
        # 如果没有识别到主题，归类为"其他"
        if not identified_topics:
            topic_messages['其他'].append(msg)
            topic_participants['其他'].add(sender)
            topic_times['其他'].append(time_str)
    
    # 生成主题摘要
    topics_summary = []
    for topic, msgs in topic_messages.items():
        if topic == '其他' and len(msgs) < 5:
            continue  # 跳过消息太少的"其他"类别
        
        participants = list(topic_participants[topic])
        times = topic_times[topic]
        
        # 计算时间范围
        if times:
            time_range = f"{min(times)} ~ {max(times)}"
        else:
            time_range = "未知"
        
        # 提取代表性消息
        representative = []
        for msg in msgs[:3]:
            representative.append({
                'time': msg.get('time', ''),
                'sender': msg.get('sender', ''),
                'content': msg.get('content', '')[:100]
            })
        
        topics_summary.append({
            'topic': topic,
            'message_count': len(msgs),
            'participants': participants,
            'participant_count': len(participants),
            'time_range': time_range,
            'representative_messages': representative
        })
    
    # 按消息数量排序
    topics_summary.sort(key=lambda x: x['message_count'], reverse=True)
    
    # 生成报告
    report = f"""# {chat_name} - 讨论主题分析

> **Skill**: Feishu Project Chat Analyzer v0.1.0  
> **公众号简介**: 分享各种Agent实战经验，欢迎交流  
> 
> Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Messages: {len(messages)} | Topics: {len(topics_summary)}

## 主题摘要

- **总消息数**: {len(messages)}
- **识别主题数**: {len(topics_summary)}
- **最活跃主题**: {topics_summary[0]['topic'] if topics_summary else 'N/A'} ({topics_summary[0]['message_count'] if topics_summary else 0} 条消息)
- **参与人数**: {stats.get('unique_senders', 0)}

## 主题详情

"""
    
    for i, topic_data in enumerate(topics_summary, 1):
        report += f"""### 主题 {i}: {topic_data['topic']}

- **消息数量**: {topic_data['message_count']} 条
- **参与人数**: {topic_data['participant_count']} 人
- **参与者**: {', '.join(topic_data['participants'][:10])}
- **时间范围**: {topic_data['time_range']}

**代表性消息**:

"""
        for j, msg in enumerate(topic_data['representative_messages'], 1):
            report += f"{j}. [{msg['time']}] {msg['sender']}: {msg['content']}\n"
        
        report += "\n"
    
    # 保存报告
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n[INFO] 已生成报告: {output_file}")
    print(f"[INFO] 识别 {len(topics_summary)} 个主题")
    
    if topics_summary:
        print(f"\n[INFO] 最活跃的主题:")
        for i, topic_data in enumerate(topics_summary[:5], 1):
            print(f"  {i}. {topic_data['topic']}: {topic_data['message_count']} 条消息, {topic_data['participant_count']} 人参与")
    
    return topics_summary


def main():
    import argparse
    parser = argparse.ArgumentParser(description='分析讨论主题')
    parser.add_argument('--input', required=True, help='输入文件路径（预处理后的消息）')
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
        args.output = f"./feishu_analysis/reports/{name_without_prefix}_topic_analysis.md"
    
    # 确保输出目录存在
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    
    # 分析主题
    analyze_topics(args.input, args.output)


if __name__ == '__main__':
    main()
