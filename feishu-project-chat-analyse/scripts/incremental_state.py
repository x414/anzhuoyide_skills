"""
增量提取状态管理
记录每个群的提取进度，支持断点续传和增量更新

用法:
    from incremental_state import IncrementalState

    state = IncrementalState('./extraction_state.json')

    # 记录提取
    state.record_extracted('<项目主群>', content_hash='abc123', msg_count=500)

    # 检查是否需要跳过
    if state.is_fully_extracted('<项目主群>', current_content):
        print("已提取过，跳过")
"""
import os
import json
import hashlib
from datetime import datetime


class IncrementalState:
    """管理提取状态的类"""

    def __init__(self, state_file='./feishu_analysis/data/extraction_state.json'):
        self.state_file = state_file
        self.state = self._load()

    def _load(self):
        """加载状态文件"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save(self):
        """保存状态文件"""
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)

    def _hash_content(self, content, max_len=5000):
        """
        计算内容的特征哈希
        取前 max_len 字符进行哈希，用于快速比对
        """
        if not content:
            return ""
        sample = content[:max_len].encode('utf-8', errors='ignore')
        return hashlib.md5(sample).hexdigest()

    def record_extracted(self, group_name, content_hash=None, msg_count=0,
                         last_msg_preview="", chars=0):
        """
        记录某个群的提取结果

        Args:
            group_name: 群名
            content_hash: 内容哈希（可选，会自动计算）
            msg_count: 提取的消息数量
            last_msg_preview: 最后一条消息的预览
            chars: 总字符数
        """
        key = self._safe_key(group_name)
        self.state[key] = {
            'group_name': group_name,
            'last_extracted': datetime.now().isoformat(),
            'content_hash': content_hash or '',
            'msg_count': msg_count,
            'last_msg_preview': last_msg_preview[:200],
            'chars': chars,
            'extract_count': self.state.get(key, {}).get('extract_count', 0) + 1,
        }
        self._save()

    def get_state(self, group_name):
        """获取某个群的提取状态"""
        key = self._safe_key(group_name)
        return self.state.get(key, {})

    def is_fully_extracted(self, group_name, current_content,
                           threshold_chars=100):
        """
        判断内容是否已完全提取过

        Args:
            group_name: 群名
            current_content: 当前获取到的内容
            threshold_chars: 内容重复多少字符视为相同

        Returns:
            bool: True 表示已提取过，可以跳过
        """
        key = self._safe_key(group_name)
        if key not in self.state:
            return False

        prev = self.state[key]
        prev_hash = prev.get('content_hash', '')

        if not prev_hash:
            return False

        current_hash = self._hash_content(current_content)

        # 如果哈希完全一致，说明内容没变
        if current_hash == prev_hash:
            return True

        # 如果当前内容比上次短很多，可能只是加载了部分内容
        current_chars = len(current_content) if current_content else 0
        prev_chars = prev.get('chars', 0)

        if current_chars > 0 and prev_chars > 0:
            # 如果当前内容长度不到上次的 90%，说明可能是新内容
            if current_chars < prev_chars * 0.9:
                return False
            # 如果长度接近，检查开头是否有重叠
            if current_content and current_chars > threshold_chars:
                overlap = self._compute_overlap(current_content[:threshold_chars * 2],
                                                prev.get('last_msg_preview', ''))
                if overlap > 0.8:
                    return True

        return False

    def should_continue_from(self, group_name, current_content):
        """
        判断是否应该从上次的位置继续提取
        返回建议的滚动轮次（0 表示从头开始）

        Args:
            group_name: 群名
            current_content: 当前可见内容

        Returns:
            int: 建议跳过的轮次，0 表示从头开始
        """
        key = self._safe_key(group_name)
        if key not in self.state:
            return 0

        prev = self.state[key]
        prev_chars = prev.get('chars', 0)
        current_chars = len(current_content) if current_content else 0

        # 如果当前内容比上次少很多，说明是新会话，从头开始
        if current_chars < prev_chars * 0.5:
            return 0

        # 估算已滚动的轮次（每轮大约增加 300-500 字符）
        estimated_rounds = prev_chars // 400
        return max(0, estimated_rounds - 5)  # 回退5轮以确保不遗漏

    def _compute_overlap(self, text1, text2, min_len=50):
        """计算两段文本的重叠度"""
        if not text1 or not text2:
            return 0.0

        # 取两段文本的开头进行比较
        len1 = min(len(text1), 500)
        len2 = min(len(text2), 500)

        sample1 = text1[:len1]
        sample2 = text2[:len2]

        # 简单哈希比对
        hash1 = set(self._hash_content(sample1[i:i + min_len])
                    for i in range(0, len(sample1) - min_len, min_len))
        hash2 = set(self._hash_content(sample2[i:i + min_len])
                    for i in range(0, len(sample2) - min_len, min_len))

        if not hash1 or not hash2:
            return 0.0

        intersection = len(hash1 & hash2)
        union = len(hash1 | hash2)

        return intersection / union if union > 0 else 0.0

    @staticmethod
    def _safe_key(name):
        """将群名转换为安全的字典 key"""
        import re
        safe = re.sub(r'[^\w一-鿿]', '_', name)
        return safe[:100]

    def list_extracted(self):
        """列出所有已提取过的群"""
        return [
            {
                'group_name': v['group_name'],
                'last_extracted': v['last_extracted'],
                'extract_count': v.get('extract_count', 1),
                'chars': v.get('chars', 0),
            }
            for v in self.state.values()
        ]

    def reset(self, group_name=None):
        """
        重置状态
        Args:
            group_name: 指定群名则只重置该群，None 则重置所有
        """
        if group_name:
            key = self._safe_key(group_name)
            if key in self.state:
                del self.state[key]
        else:
            self.state = {}
        self._save()
