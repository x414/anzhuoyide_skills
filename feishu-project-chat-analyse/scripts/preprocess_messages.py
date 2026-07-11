#!/usr/bin/env python3
"""
预处理提取的飞书聊天消息
- 解析消息JSON格式
- 提取@提及
- 识别消息线程
- 标准化时间戳
- 过滤系统消息
"""
import os
import json
import re
import argparse
from datetime import datetime


def parse_message_content(content_str):
    """解析飞书消息内容（JSON格式）"""
    try:
        content = json.loads(content_str)
        
        # 提取文本
        text = content.get('text', '')
        
        # 提取@提及
        mentions = []
        if 'mentions' in content:
            for mention in content['mentions']:
                mentions.append({
                    'user_id': mention.get('user_id', ''),
                    'user_name': mention.get('user_name', ''),
                    'key': mention.get('key', '')
                })
        
        # 提取其他类型的内容
        msg_type = 'text'
        if 'image' in content:
            msg_type = 'image'
        elif 'file' in content:
            msg_type = 'file'
            text = content['file'].get('name', '[文件]')
        elif 'video' in content:
            msg_type = 'video'
            text = '[视频]'
        elif 'audio' in content:
            msg_type = 'audio'
            text = '[语音]'
        elif 'card' in content:
            msg_type = 'card'
            text = '[卡片消息]'
        
        return {
            'text': text,
            'mentions': mentions,
            'msg_type': msg_type
        }
    except:
        # 如果不是JSON，直接返回文本
        return {
            'text': content_str,
            'mentions': [],
            'msg_type': 'text'
        }


def extract_mentions_from_text(text):
    """从文本中提取@提及（备用方法）"""
    mentions = []
    pattern = r'@([^\s]+)'
    matches = re.findall(pattern, text)
    for match in matches:
        mentions.append({
            'user_name': match
        })
    return mentions


def normalize_timestamp(time_str):
    """标准化时间戳"""
    # 飞书时间格式可能是: "2026-06-17 10:30:00" 或 "昨天 10:30" 或 "10:30"
    
    # 尝试解析标准格式
    try:
        dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
        return dt.isoformat()
    except:
        pass
    
    # 尝试解析其他格式
    try:
        dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M')
        return dt.isoformat()
    except:
        pass
    
    # 如果无法解析，返回原始值
    return time_str


def is_system_message(message):
    """判断是否是系统消息"""
    text = message.get('content', '').lower()
    
    # 系统消息的特征
    system_keywords = [
        '加入了群聊',
        '退出了群聊',
        '修改了群名',
        '邀请了',
        '移除了',
        '设置了群公告',
        '开启了消息免打扰',
        '关闭了消息免打扰'
    ]
    
    return any(keyword in text for keyword in system_keywords)


def preprocess_messages(input_file, output_file):
    """预处理消息"""
    
    # 读取原始消息
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    chat_name = data.get('chat_name', '')
    messages = data.get('messages', [])
    
    print(f"[INFO] 读取 {len(messages)} 条消息")
    
    # 预处理消息
    processed_messages = []
    system_messages = []
    
    for msg in messages:
        # 过滤系统消息
        if is_system_message(msg):
            system_messages.append(msg)
            continue
        
        # 解析消息内容
        content = msg.get('content', '')
        parsed = parse_message_content(content)
        
        # 如果没有从JSON中提取到提及，尝试从文本中提取
        if not parsed['mentions'] and '@' in parsed['text']:
            parsed['mentions'] = extract_mentions_from_text(parsed['text'])
        
        # 标准化时间戳
        time_str = msg.get('time', '')
        normalized_time = normalize_timestamp(time_str)
        
        # 构建处理后的消息
        processed_msg = {
            'sender': msg.get('sender', ''),
            'time': normalized_time,
            'original_time': time_str,
            'content': parsed['text'],
            'msg_type': parsed['msg_type'],
            'mentions': parsed['mentions'],
            'has_mention': len(parsed['mentions']) > 0
        }
        
        processed_messages.append(processed_msg)
    
    print(f"[INFO] 处理后: {len(processed_messages)} 条消息")
    print(f"[INFO] 过滤系统消息: {len(system_messages)} 条")
    
    # 统计信息
    stats = {
        'total_messages': len(messages),
        'processed_messages': len(processed_messages),
        'system_messages': len(system_messages),
        'unique_senders': len(set(m['sender'] for m in processed_messages)),
        'messages_with_mentions': sum(1 for m in processed_messages if m['has_mention']),
        'msg_types': {}
    }
    
    for msg in processed_messages:
        msg_type = msg['msg_type']
        stats['msg_types'][msg_type] = stats['msg_types'].get(msg_type, 0) + 1
    
    # 发送者统计
    sender_stats = {}
    for msg in processed_messages:
        sender = msg['sender']
        if sender not in sender_stats:
            sender_stats[sender] = {
                'message_count': 0,
                'mentions_count': 0
            }
        sender_stats[sender]['message_count'] += 1
        if msg['has_mention']:
            sender_stats[sender]['mentions_count'] += 1
    
    # 保存结果
    result = {
        'chat_name': chat_name,
        'stats': stats,
        'sender_stats': sender_stats,
        'messages': processed_messages
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"\n[INFO] 已保存到: {output_file}")
    
    # 打印统计信息
    print(f"\n[INFO] 统计信息:")
    print(f"  总消息数: {stats['total_messages']}")
    print(f"  处理后: {stats['processed_messages']}")
    print(f"  系统消息: {stats['system_messages']}")
    print(f"  唯一发送者: {stats['unique_senders']}")
    print(f"  包含@提及: {stats['messages_with_mentions']}")
    
    print(f"\n[INFO] 消息类型:")
    for msg_type, count in stats['msg_types'].items():
        print(f"  {msg_type}: {count}")
    
    print(f"\n[INFO] 活跃发送者 (前10):")
    sorted_senders = sorted(sender_stats.items(), key=lambda x: x[1]['message_count'], reverse=True)
    for i, (sender, stats) in enumerate(sorted_senders[:10], 1):
        print(f"  {i}. {sender}: {stats['message_count']} 条消息, {stats['mentions_count']} 次@提及")
    
    return result


def main():
    parser = argparse.ArgumentParser(description='预处理飞书聊天消息')
    parser.add_argument('--input', required=True, help='输入文件路径')
    parser.add_argument('--output', help='输出文件路径')
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"[ERROR] 输入文件不存在: {args.input}")
        return
    
    # 生成输出文件名
    if not args.output:
        base_name = os.path.basename(args.input)
        name_without_ext = os.path.splitext(base_name)[0]
        args.output = f"./feishu_analysis/data/preprocessed_{name_without_ext}.json"
    
    # 预处理消息
    preprocess_messages(args.input, args.output)


if __name__ == '__main__':
    main()
