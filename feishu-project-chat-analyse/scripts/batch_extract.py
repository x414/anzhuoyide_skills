#!/usr/bin/env python3
"""
批量提取飞书聊天记录 - 标准化脚本

用法:
    # 从文件读取群列表
    python3 batch_extract.py --groups-file groups.txt --output-dir ./data/

    # 直接指定群名（逗号分隔）
    python3 batch_extract.py --groups "群A,群B,群C" --output-dir ./data/

    # 使用配置文件
    python3 batch_extract.py --config ./config.yaml --groups-file groups.txt

    # 增量模式（跳过已提取的群）
    python3 batch_extract.py --groups-file groups.txt --incremental

    # 限制并发数
    python3 batch_extract.py --groups-file groups.txt --max-workers 1
"""
import os
import sys
import json
import time
import argparse
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# 将脚本目录加入路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import load_config, setup_display, setup_logging, CONFIG
from incremental_state import IncrementalState

# 尝试导入提取函数
try:
    from extract_chat_messages_v6 import extract_group
    EXTRACTOR = 'v6'
except ImportError:
    print("[ERROR] extract_chat_messages_v6.py not found")
    sys.exit(1)


def parse_groups_file(filepath):
    """从文件解析群名列表"""
    groups = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                groups.append(line)
    return groups


def extract_single(group_name, output_dir, cookies_file, state, incremental=True):
    """
    提取单个群的聊天记录

    Returns:
        dict: 提取结果信息
    """
    import re
    safe_name = re.sub(r'[^\w一-鿿_-]', '_', group_name)
    safe_name = re.sub(r'_+', '_', safe_name).strip('_')

    output_file = os.path.join(output_dir, f"{safe_name}.txt")

    result = {
        'group_name': group_name,
        'output_file': output_file,
        'status': 'pending',
        'chars': 0,
        'lines': 0,
        'duration': 0,
        'error': None,
    }

    try:
        # 检查增量状态
        if incremental and os.path.exists(output_file):
            # 读取现有内容检查是否需要重新提取
            with open(output_file, 'r', encoding='utf-8') as f:
                existing = f.read()

            if state.is_fully_extracted(group_name, existing):
                result['status'] = 'skipped'
                result['chars'] = len(existing)
                result['lines'] = existing.count('\n')
                print(f"  [SKIP] {group_name} - already extracted ({len(existing)} chars)")
                return result

        # 执行提取
        print(f"  [EXTRACT] {group_name}...")
        start_time = time.time()

        chars = extract_group(group_name, output_file)

        duration = time.time() - start_time

        # 读取结果
        if os.path.exists(output_file):
            with open(output_file, 'r', encoding='utf-8') as f:
                content = f.read()
            result['chars'] = len(content)
            result['lines'] = content.count('\n')
            result['status'] = 'success'

            # 记录状态
            state.record_extracted(
                group_name,
                content_hash=state._hash_content(content),
                msg_count=result['lines'],
                chars=result['chars']
            )
        else:
            result['status'] = 'failed'
            result['error'] = 'Output file not created'

        result['duration'] = round(duration, 2)
        print(f"  [DONE] {group_name}: {result['chars']} chars, {result['lines']} lines, {duration:.1f}s")

    except Exception as e:
        result['status'] = 'failed'
        result['error'] = str(e)
        print(f"  [ERROR] {group_name}: {e}")

    return result


def run_batch_extraction(groups, output_dir, cookies_file,
                         max_workers=1, incremental=True,
                         retry_count=3, retry_delay=5):
    """
    批量提取多个群的聊天记录

    Args:
        groups: 群名列表
        output_dir: 输出目录
        cookies_file: cookies 文件路径
        max_workers: 最大并发数（建议1-2，避免被封）
        incremental: 是否启用增量模式
        retry_count: 失败重试次数
        retry_delay: 重试间隔（秒）

    Returns:
        list: 所有群的提取结果
    """
    state = IncrementalState()
    results = []

    print(f"\n{'='*60}")
    print(f"批量提取任务")
    print(f"  总群数: {len(groups)}")
    print(f"  输出目录: {output_dir}")
    print(f"  并发数: {max_workers}")
    print(f"  增量模式: {'Yes' if incremental else 'No'}")
    print(f"{'='*60}\n")

    if max_workers == 1:
        # 串行模式（更稳定）
        for idx, group_name in enumerate(groups, 1):
            print(f"\n[{idx}/{len(groups)}] {group_name}")
            result = extract_single(group_name, output_dir, cookies_file, state, incremental)
            results.append(result)

            # 失败重试
            if result['status'] == 'failed' and retry_count > 0:
                for attempt in range(retry_count):
                    print(f"  [RETRY {attempt+1}/{retry_count}] {group_name}...")
                    time.sleep(retry_delay)
                    result = extract_single(group_name, output_dir, cookies_file, state, False)
                    if result['status'] == 'success':
                        results[-1] = result
                        break
    else:
        # 并发模式
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    extract_single, group_name, output_dir, cookies_file, state, incremental
                ): group_name
                for group_name in groups
            }

            for future in as_completed(futures):
                group_name = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    results.append({
                        'group_name': group_name,
                        'status': 'failed',
                        'error': str(e),
                    })

    return results


def generate_report(results, report_file):
    """生成提取报告"""
    total = len(results)
    success = sum(1 for r in results if r['status'] == 'success')
    skipped = sum(1 for r in results if r['status'] == 'skipped')
    failed = sum(1 for r in results if r['status'] == 'failed')
    total_chars = sum(r['chars'] for r in results)
    total_lines = sum(r['lines'] for r in results)
    total_duration = sum(r.get('duration', 0) for r in results)

    report = {
        'generated_at': datetime.now().isoformat(),
        'summary': {
            'total_groups': total,
            'success': success,
            'skipped': skipped,
            'failed': failed,
            'total_chars': total_chars,
            'total_lines': total_lines,
            'total_duration_sec': round(total_duration, 2),
        },
        'results': results,
    }

    os.makedirs(os.path.dirname(report_file), exist_ok=True)
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print("提取完成!")
    print(f"  成功: {success} | 跳过: {skipped} | 失败: {failed} | 总计: {total}")
    print(f"  总字符数: {total_chars:,}")
    print(f"  总行数: {total_lines:,}")
    print(f"  总耗时: {total_duration:.1f}s")
    print(f"  报告: {report_file}")
    print(f"{'='*60}")

    return report


def main():
    parser = argparse.ArgumentParser(description='批量提取飞书聊天记录')
    parser.add_argument('--groups-file', '-f', help='群名列表文件（每行一个群名）')
    parser.add_argument('--groups', '-g', help='群名列表（逗号分隔）')
    parser.add_argument('--output-dir', '-o', default='./feishu_analysis/data', help='输出目录')
    parser.add_argument('--cookies', '-c', default='./feishu_analysis/data/feishu_cookies.json', help='cookies文件')
    parser.add_argument('--config', help='配置文件路径')
    parser.add_argument('--max-workers', '-w', type=int, default=1, help='最大并发数（建议1-2）')
    parser.add_argument('--incremental', '-i', action='store_true', help='启用增量模式')
    parser.add_argument('--retry', '-r', type=int, default=3, help='失败重试次数')
    parser.add_argument('--report', default='./feishu_analysis/reports/batch_extraction_report.json', help='报告文件路径')
    args = parser.parse_args()

    # 加载配置
    load_config(args.config)

    # 设置显示环境
    setup_display()

    # 确定群列表
    if args.groups_file:
        groups = parse_groups_file(args.groups_file)
    elif args.groups:
        groups = [g.strip() for g in args.groups.split(',')]
    else:
        print("[ERROR] 请指定 --groups-file 或 --groups")
        parser.print_help()
        sys.exit(1)

    if not groups:
        print("[ERROR] 群列表为空")
        sys.exit(1)

    # 确保输出目录存在
    os.makedirs(args.output_dir, exist_ok=True)

    # 执行批量提取
    results = run_batch_extraction(
        groups=groups,
        output_dir=args.output_dir,
        cookies_file=args.cookies,
        max_workers=args.max_workers,
        incremental=args.incremental,
        retry_count=args.retry,
    )

    # 生成报告
    generate_report(results, args.report)


if __name__ == '__main__':
    main()
