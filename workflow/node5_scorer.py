# 节点5: LLM打分排序 -- 使用 DeepSeek API 对文案进行5维度评分
import os
import json

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from config import DEEPSEEK_API_BASE, LLM_MODEL


def _build_scoring_llm():
    """构建评分 LLM 实例"""
    return ChatOpenAI(
        model=LLM_MODEL,
        openai_api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
        openai_api_base=DEEPSEEK_API_BASE,
        temperature=0.3,
        max_tokens=2048
    )


def _build_scoring_prompt():
    """构建评分 Prompt 模板"""
    return ChatPromptTemplate.from_messages([
        ("system", """你是一位专业的抖音文案评审专家。
请从以下5个维度对每条文案进行打分（1-10分）：
1. 吸引力 - 能否在3秒内抓住观众注意力
2. 信息量 - 是否清晰传达了商品卖点
3. 可读性 - 语言是否流畅、口语化
4. 转化潜力 - 能否有效引导用户行动
5. 情感感染力 - 是否能引起观众情感共鸣

请严格按照JSON格式输出结果，不要包含任何额外的说明文字。"""),
        ("human", """请对以下3条文案进行打分排序：
{copies_data}

请按以下JSON格式输出（直接输出JSON，不要有其他文字）：
{{
  "scores": [
    {{
      "index": 1,
      "style": "剧情",
      "dimensions": {{
        "吸引力": 9,
        "信息量": 7,
        "可读性": 8,
        "转化潜力": 9,
        "情感感染力": 8
      }},
      "total_score": 41
    }}
  ],
  "ranking": [1, 3, 2],
  "best_recommendation": "文案1",
  "reason": "推荐理由"
}}""")
    ])


def _format_copies_data(copies_with_analysis):
    """格式化文案数据为评分用文本"""
    lines = []
    style_map = {0: "剧情", 1: "痛点", 2: "悬念"}

    for i, copy_data in enumerate(copies_with_analysis):
        style = style_map.get(i, f"风格{i+1}")
        lines.append(f"--- 文案{i+1}（{style}）---")
        lines.append(f"正文: {copy_data['text']}")
        lines.append(f"字数: {copy_data['word_count']}")
        lines.append(f"emoji数量: {copy_data['emoji_count']}")
        lines.append(f"包含CTA: {'是' if copy_data['has_cta'] else '否'}")
        lines.append("")

    return "\n".join(lines)


def score_and_recommend(copies_with_analysis):
    """
    对3条文案进行5维度打分和排序推荐
    参数:
      - copies_with_analysis: Node4输出的分析结果列表（3条）
    返回:
      - dict: {scores, ranking, best_recommendation, reason}
    """
    llm = _build_scoring_llm()
    prompt = _build_scoring_prompt()

    copies_text = _format_copies_data(copies_with_analysis)

    chain = prompt | llm | StrOutputParser()
    llm_output = chain.invoke({"copies_data": copies_text})

    # 解析 JSON 输出
    try:
        # 尝试直接解析
        result = json.loads(llm_output)
    except json.JSONDecodeError:
        # 尝试从输出中提取 JSON
        import re
        match = re.search(r'\{.*\}', llm_output, re.DOTALL)
        if match:
            result = json.loads(match.group())
        else:
            # 返回默认错误结果
            result = {
                "scores": [
                    {"index": i+1, "style": s, "dimensions": {
                        "吸引力": 0, "信息量": 0, "可读性": 0,
                        "转化潜力": 0, "情感感染力": 0
                    }, "total_score": 0}
                    for i, s in enumerate(["剧情", "痛点", "悬念"])
                ],
                "ranking": [1, 2, 3],
                "best_recommendation": "解析失败",
                "reason": "LLM返回格式错误，无法解析评分结果"
            }

    # 重新计算 total_score 以确保一致性
    if "scores" in result:
        for s in result["scores"]:
            if "dimensions" in s and "total_score" in s:
                s["total_score"] = sum(s["dimensions"].values())

    return result
