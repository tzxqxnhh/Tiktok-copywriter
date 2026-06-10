# 抖音爆款文案生成工具 -- 全局配置
import os
from pathlib import Path

# API 配置
DEEPSEEK_API_BASE = "https://api.deepseek.com"
SILICONFLOW_API_BASE = "https://api.siliconflow.cn/v1"

# 模型
LLM_MODEL = "deepseek-chat"
EMBEDDING_MODEL = "BAAI/bge-m3"

# 路径
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
CHROMA_DB_DIR = DATA_DIR / "chroma_db"
HISTORY_DB_PATH = DATA_DIR / "chat_history.db"
TEMPLATES_PATH = BASE_DIR / "templates" / "copy_templates.json"

# 向量库
COLLECTION_NAME = "douyin_copy_templates"
RETRIEVAL_TOP_K = 5

# CTA 关键词列表
CTA_KEYWORDS = [
    "点击", "购买", "下单", "关注", "抢购",
    "立即", "收藏", "分享", "评论", "领取",
    "赶紧", "抓紧", "行动"
]

# Emoji 正则模式 - 覆盖主流 emoji Unicode 范围
EMOJI_PATTERN = (
    "["
    "\U0001F600-\U0001F64F"   # 表情符号 (Emoticons)
    "\U0001F300-\U0001F5FF"   # 符号和象形文字 (Misc Symbols)
    "\U0001F680-\U0001F6FF"   # 交通和地图符号 (Transport)
    "\U0001F1E0-\U0001F1FF"   # 旗帜 (Flags)
    "\U00002702-\U000027B0"   # 其他符号 (Dingbats)
    "\U0001F900-\U0001F9FF"   # 补充符号和象形文字 (Supplemental)
    "\U0001FA00-\U0001FA6F"   # 国际象棋符号等
    "\U0001FA70-\U0001FAFF"   # 扩展-A
    "\U00002600-\U000026FF"   # 杂项符号 (Misc)
    "]+"
)

# 文案风格类型
STYLES = ["剧情", "痛点", "悬念", "干货", "对比"]


def ensure_directories():
    """确保必要的目录存在"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CHROMA_DB_DIR.mkdir(parents=True, exist_ok=True)


def check_api_keys():
    """检查环境变量中的API密钥是否已设置，返回缺失的密钥列表"""
    missing = []
    if not os.environ.get("DEEPSEEK_API_KEY"):
        missing.append("DEEPSEEK_API_KEY")
    if not os.environ.get("SILICONFLOW_API_KEY"):
        missing.append("SILICONFLOW_API_KEY")
    return missing
