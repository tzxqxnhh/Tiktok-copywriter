# 节点3: LLM文案生成 -- 使用 DeepSeek API 生成3种风格文案
import os

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from config import DEEPSEEK_API_BASE, LLM_MODEL, DIRECTOR_STYLE_PROMPTS


def _build_llm():
    """构建 LLM 实例"""
    return ChatOpenAI(
        model=LLM_MODEL,
        openai_api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
        openai_api_base=DEEPSEEK_API_BASE,
        temperature=0.8,
        max_tokens=2048
    )


def _build_copywriting_prompt(styles=None, count=3):
    """构建文案模式 Prompt 模板，风格和数量可参数化
    参数:
      - styles: 文案风格列表
      - count: 每种风格的生成条数
    """
    styles = styles or ["剧情", "痛点", "悬念"]
    per_style = count or 3
    total = per_style * len(styles)
    style_list_str = "、".join(styles)

    # 构建输出格式示例 - 每种风格出现 per_style 次
    output_example = ""
    for s in styles:
        for _ in range(per_style):
            output_example += f"\n【{s}】\n文案正文...\n"

    return ChatPromptTemplate.from_messages([
        ("system", f"""你是一位资深抖音运营专家，擅长撰写高转化率的短视频文案。
你的任务是根据提供的商品信息和参考素材，为每种风格各生成{per_style}条不同角度的爆款文案，共{len(styles)}种风格合计{total}条。

要求：
1. 每条文案控制在 50-120 字以内（适合抖音口播）
2. 风格必须覆盖以下{len(styles)}种：{style_list_str}，每种风格生成{per_style}条
3. 每条文案必须包含明确的 Call to Action（引导用户行动）
4. 语言口语化、接地气，符合抖音用户习惯
5. 适当使用 emoji 增强表现力（每条约2-4个）

输出格式：{output_example}"""),
        ("human", f"""请为以下商品生成{total}条爆款文案（每种风格{per_style}条）：

商品名称：{{product_name}}
卖点描述：{{selling_points}}

参考爆款样本（同类优质文案Top10）：
{{sim_search_results}}

参考文案模板（知识库检索到的相关模板）：
{{templates}}""")
    ])


def _build_director_prompt(director_style="剧情"):
    """构建导演模式 Prompt 模板
    参数:
      - director_style: 导演风格（"剧情"/"痛点"/"悬念"/"干货"/"对比"）
    """
    style_prompt = DIRECTOR_STYLE_PROMPTS.get(
        director_style,
        DIRECTOR_STYLE_PROMPTS["剧情"]
    )
    return ChatPromptTemplate.from_messages([
        ("system", style_prompt),
        ("human", """请为以下商品生成一个短视频分镜脚本：

商品名称：{product_name}
卖点描述：{selling_points}
用户期望：{user_expectation}

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


def _parse_copies(llm_output, mode="copywriting", count=3):
    """从LLM输出中解析文案
    参数:
      - llm_output: LLM 原始输出文本
      - mode: 模式 ("copywriting" 或 "director")
      - count: 期望的文案数量（仅文案模式使用）
    返回:
      - list[str]: 解析后的文案列表
    """
    # 导演模式直接返回原始输出
    if mode == "director":
        return [llm_output.strip()]

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

    # 如果解析出的条数不够，用整个文本按双换行分割
    if len(copies) < count:
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
        if len(filtered) >= count:
            copies = filtered[:count]

    # 确保返回指定数量的文案
    while len(copies) < count:
        copies.append("（生成失败，请重试）")

    return copies[:count]


def generate_copies(product_name, selling_points, sim_search_results, templates,
                    mode="copywriting", styles=None, count=3, user_expectation=None,
                    director_style="剧情"):
    """
    调用 LLM 生成文案
    参数:
      - product_name: 商品名称
      - selling_points: 卖点描述
      - sim_search_results: Node1返回的模拟搜索结果
      - templates: Node2返回的参考模板列表
      - mode: 生成模式 ("copywriting" 或 "director")
      - styles: 文案风格列表（仅文案模式使用，默认 ["剧情", "痛点", "悬念"]）
      - count: 每种风格的生成条数（仅文案模式使用，默认 3）
      - user_expectation: 用户期望（仅导演模式使用，可选）
      - director_style: 导演风格选择（仅导演模式使用，默认 "剧情"）
    返回:
      - list[str]: 文案文本列表
    """
    llm = _build_llm()

    # 格式化输入
    sim_text = _format_sim_results(sim_search_results)
    templates_text = _format_templates(templates)

    if mode == "director":
        prompt = _build_director_prompt(director_style=director_style)
        chain = prompt | llm | StrOutputParser()
        llm_output = chain.invoke({
            "product_name": product_name,
            "selling_points": selling_points,
            "user_expectation": user_expectation or "",
            "sim_search_results": sim_text,
            "templates": templates_text,
        })
        return _parse_copies(llm_output, mode=mode, count=1)
    else:
        styles = styles or ["剧情", "痛点", "悬念"]
        per_style = count or 3
        total_count = per_style * len(styles)
        prompt = _build_copywriting_prompt(styles=styles, count=per_style)
        chain = prompt | llm | StrOutputParser()
        llm_output = chain.invoke({
            "product_name": product_name,
            "selling_points": selling_points,
            "sim_search_results": sim_text,
            "templates": templates_text,
        })
        return _parse_copies(llm_output, mode=mode, count=total_count)
