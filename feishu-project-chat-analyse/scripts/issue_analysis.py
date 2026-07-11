#!/usr/bin/env python3
"""
问题追踪分析
- 识别提出的问题
- 追踪问题解决状态
- 统计解决时间
"""
import os
import json
import re
from datetime import datetime


def analyze_issues(input_file, output_file):
    """分析问题"""
    
    # 读取预处理后的消息
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    chat_name = data.get('chat_name', '')
    messages = data.get('messages', [])
    
    print(f"[INFO] 分析 {len(messages)} 条消息中的问题...")
    
    # 问题关键词
    issue_keywords = [
        '问题', 'bug', '错误', '异常', '失败', '报错',
        'issue', 'error', 'fail', 'crash', 'exception',
        '怎么', '为什么', '如何', '能否', '可以'
    ]
    
    # 解决关键词
    resolution_keywords = [
        '解决', '修复', '搞定', '好了', '已修', '修好',
        'fix', 'solve', 'resolve', 'done', 'fixed',
        '已解决', '已修复', '已搞定'
    ]
    
    # 识别问题
    issues = []
    current_issue = None
    
    for i, msg in enumerate(messages):
        content = msg.get('content', '')
        sender = msg.get('sender', '')
        time_str = msg.get('time', '')
        
        # 检查是否提出问题
        is_issue = any(keyword in content for keyword in issue_keywords)
        
        # 检查是否解决问题
        is_resolution = any(keyword in content for keyword in resolution_keywords)
        
        if is_issue and not current_issue:
            # 新问题
            current_issue = {
                'issue': content,
                'raised_by': sender,
                'raised_at': time_str,
                'raised_at_index': i,
                'related_messages': [
                    {
                        'time': time_str,
                        'sender': sender,
                        'content': content[:100]
                    }
                ],
                'resolved': False,
                'resolved_by': None,
                'resolved_at': None,
                'resolution': None
            }
        elif current_issue:
            # 问题相关消息
            current_issue['related_messages'].append({
                'time': time_str,
                'sender': sender,
                'content': content[:100]
            })
            
            # 检查是否解决
            if is_resolution:
                current_issue['resolved'] = True
                current_issue['resolved_by'] = sender
                current_issue['resolved_at'] = time_str
                current_issue['resolution'] = content
                
                # 计算解决时间（简化处理）
                try:
                    raised = datetime.fromisoformat(current_issue['raised_at'].replace('Z', '+00:00'))
                    resolved = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                    resolution_time = (resolved - raised).total_seconds() / 3600  # 小时
                    current_issue['resolution_time_hours'] = resolution_time
                except:
                    current_issue['resolution_time_hours'] = None
                
                issues.append(current_issue)
                current_issue = None
    
    # 如果还有未解决的问题
    if current_issue:
        issues.append(current_issue)
    
    print(f"[INFO] 识别 {len(issues)} 个问题")
    
    # 统计
    resolved_count = sum(1 for issue in issues if issue['resolved'])
    unresolved_count = len(issues) - resolved_count
    
    # 生成报告
    report = f"""# {chat_name} - 问题追踪

> **Skill**: Feishu Project Chat Analyzer v0.1.0  
> **公众号简介**: 分享各种Agent实战经验，欢迎交流  
> 
> Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Messages: {len(messages)} | Issues: {len(issues)}

## 问题摘要

- **总消息数**: {len(messages)}
- **识别问题数**: {len(issues)}
- **已解决**: {resolved_count}
- **未解决**: {unresolved_count}

## 问题详情

"""
    
    for i, issue in enumerate(issues, 1):
        status = "✅ 已解决" if issue['resolved'] else "❌ 未解决"
        
        report += f"""### 问题 {i}: {issue['issue'][:50]}...

- **状态**: {status}
- **提出者**: {issue['raised_by']}
- **提出时间**: {issue['raised_at']}

**问题描述**:

{issue['issue']}

"""
        
        if issue['resolved']:
            report += f"""**解决信息**:

- **解决者**: {issue['resolved_by']}
- **解决时间**: {issue['resolved_at']}
- **解决时长**: {issue.get('resolution_time_hours', 'N/A')} 小时

**解决方案**:

{issue['resolution']}

"""
        
        report += "**相关讨论**:\n\n"
        for msg in issue['related_messages'][:5]:
            report += f"- [{msg['time']}] {msg['sender']}: {msg['content']}\n"
        
        report += "\n---\n\n"
    
    # 保存报告
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n[INFO] 已生成报告: {output_file}")
    print(f"[INFO] 已解决: {resolved_count}, 未解决: {unresolved_count}")
    
    if issues:
        print(f"\n[INFO] 前3个问题:")
        for i, issue in enumerate(issues[:3], 1):
            status = "✅" if issue['resolved'] else "❌"
            print(f"  {i}. {status} {issue['issue'][:50]}...")
    
    return issues


def main():
    import argparse
    parser = argparse.ArgumentParser(description='分析问题')
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
        args.output = f"./feishu_analysis/reports/{name_without_prefix}_issue_analysis.md"
    
    # 确保输出目录存在
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    
    # 分析问题
    analyze_issues(args.input, args.output)


if __name__ == '__main__':
    main()
