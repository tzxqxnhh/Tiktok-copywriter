# 节点3: LLM文案生成 -- 使用 DeepSeek API 生成3种风格文案
import os

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from config import DEEPSEEK_API_BASE, LLM_MODEL


def _build_llm():
    """构建 LLM 实例"""
    return ChatOpenAI(
        model=LLM_MODEL,
        openai_api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
        openai_api_base=DEEPSEEK_API_BASE,
        temperature=0.8,
        max_tokens=2048
    )


def _build_prompt():
    """构建 Prompt 模板"""
    return ChatPromptTemplate.from_messages([
        ("system", """你是一位资深抖音运营专家，擅长撰写高转化率的短视频文案。
你的任务是根据提供的商品信息和参考素材，生成3条不同风格的爆款文案。

要求：
1. 每条文案控制在 50-120 字以内（适合抖音口播）
2. 风格必须覆盖以下3种：剧情、痛点、悬念
3. 每条文案必须包含明确的 Call to Action（引导用户行动）
4. 语言口语化、接地气，符合抖音用户习惯
5. 适当使用 emoji 增强表现力（每条约2-4个）

输出格式：
【剧情】
文案正文...

【痛点】
文案正文...

【悬念】
文案正文..."""),
        ("human", """请为以下商品生成3条爆款文案：

商品名称：{product_name}
卖点描述：{selling_points}

参考爆款样本（同类优质文案Top10）：
{sim_search_results}

参考文案模板（知识库检索到的相关模板）：
{templates}""")
    ])


def _format_sim_results(sim_search_results):
    """格式化模拟搜索结果为人可读的文本"""
    if not sim_search_results:
        return "暂无参考样本"

    lines = []
    for item in sim_search_results:
        lines.append(
            f"[{item.get('index', '?')}] ({item.get('style', '未知')}风) "
            f"点赞{item.get('likes', 0):,} - {item.get('title', '')}"
            f"\n    {item.get('content', '')}"
        )
    return "\n".join(lines)


def _format_templates(templates):
    """格式化模板列表为人可读的文本"""
    if not templates:
        return "暂无参考模板"

    lines = []
    for i, tpl in enumerate(templates, 1):
        lines.append(f"{i}. {tpl}")
    return "\n".join(lines)


def _parse_copies(llm_output):
    """从LLM输出中解析3条文案"""
    copies = []
    current_style = None
    current_text = []

    for line in llm_output.strip().split("\n"):
        line = line.strip()
        if not line:
            if current_style and current_text:
                copies.append("\n".join(current_text))
                current_text = []
                current_style = None
            continue

        # 检测风格标签
        if line.startswith("【") and "】" in line:
            if current_style and current_text:
                copies.append("\n".join(current_text))
                current_text = []
            current_style = line
        elif current_style:
            current_text.append(line)

    # 添加最后一段
    if current_style and current_text:
        copies.append("\n".join(current_text))

    # 如果解析出的条数不够3条，用整个文本按双换行分割
    if len(copies) < 3:
        parts = [p.strip() for p in llm_output.split("\n\n") if p.strip()]
        # 过滤掉风格标签行
        filtered = []
        for part in parts:
            lines = part.split("\n")
            content_lines = [
                l for l in lines
                if not (l.strip().startswith("【") and "】" in l.strip())
            ]
            if content_lines:
                filtered.append("\n".join(content_lines))
        if len(filtered) >= 3:
            copies = filtered[:3]

    # 确保返回3条文案
    while len(copies) < 3:
        copies.append("（生成失败，请重试）")

    return copies[:3]


def generate_copies(product_name, selling_points, sim_search_results, templates):
    """
    调用 LLM 生成3条不同风格的爆款文案
    参数:
      - product_name: 商品名称
      - selling_points: 卖点描述
      - sim_search_results: Node1返回的模拟搜索结果
      - templates: Node2返回的参考模板列表
    返回:
      - list[str]: 3条文案文本
    """
    llm = _build_llm()
    prompt = _build_prompt()

    # 格式化输入
    sim_text = _format_sim_results(sim_search_results)
    templates_text = _format_templates(templates)

    # 构建链并调用
    chain = prompt | llm | StrOutputParser()
    llm_output = chain.invoke({
        "product_name": product_name,
        "selling_points": selling_points,
        "sim_search_results": sim_text,
        "templates": templates_text,
    })

    # 解析输出
    return _parse_copies(llm_output)
