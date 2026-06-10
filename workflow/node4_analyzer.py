# 节点4: 代码分析 -- 字数统计 / emoji计数 / CTA检测
import re

from config import CTA_KEYWORDS, EMOJI_PATTERN


def count_words(text):
    """
    统计包含标点符号在内的总字符数
    参数:
      - text: 文案文本
    返回:
      - int: 字符总数
    """
    return len(text)


def count_emoji(text):
    """
    使用 Unicode emoji 正则匹配，统计文本中 emoji 数量
    参数:
      - text: 文案文本
    返回:
      - int: emoji 数量
    """
    emoji_pattern = re.compile(EMOJI_PATTERN, flags=re.UNICODE)
    matches = emoji_pattern.findall(text)
    # 每个匹配可能包含多个 emoji 字符，需要逐字符计算
    total = 0
    for match in matches:
        total += len(match)
    return total


def check_cta(text):
    """
    检测文案是否包含 Call to Action 关键词
    参数:
      - text: 文案文本
    返回:
      - bool: 是否包含 CTA 关键词
    """
    for keyword in CTA_KEYWORDS:
        if keyword in text:
            return True
    return False


def analyze_copies(copies):
    """
    对多条文案进行代码分析
    参数:
      - copies: 3条文案的文本列表
    返回:
      - list[dict]: 每条文案的分析结果
    """
    results = []
    for copy_text in copies:
        results.append({
            "text": copy_text,
            "word_count": count_words(copy_text),
            "emoji_count": count_emoji(copy_text),
            "has_cta": check_cta(copy_text),
        })
    return results
