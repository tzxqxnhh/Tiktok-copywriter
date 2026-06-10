# 抖音爆款文案生成工具 -- Gradio 应用入口 + 工作流编排
import os
import sys
from pathlib import Path
from datetime import datetime

import gradio as gr

from config import (
    DATA_DIR, CHROMA_DB_DIR, HISTORY_DB_PATH, TEMPLATES_PATH,
    ensure_directories, check_api_keys, CTA_KEYWORDS
)
from database.vector_store import (
    init_vector_store, add_to_knowledge_base, get_document_count
)
from database.chat_history import (
    init_db, create_session, delete_session, get_sessions,
    add_message, get_session_messages, update_session_title
)
from workflow import node1_sim_search
from workflow import node2_knowledge
from workflow import node3_generator
from workflow import node4_analyzer
from workflow import node5_scorer


# ============================================================
# 核心函数：可测试的业务逻辑
# ============================================================

def run_generation_workflow(product_name, selling_points, vector_store):
    """
    执行文案生成工作流（5个节点）
    参数:
      - product_name: 商品名称
      - selling_points: 卖点描述
      - vector_store: ChromaDB collection 实例
    返回:
      - (formatted_output: str, error: str or None)
    """
    # 输入验证
    if not product_name or not product_name.strip():
        return None, "请输入商品名称和卖点"

    if not selling_points or not selling_points.strip():
        return None, "请输入商品名称和卖点"

    product_name = product_name.strip()
    selling_points = selling_points.strip()

    try:
        # Node1: 模拟搜索
        sim_results = node1_sim_search.sim_search(product_name, selling_points)

        # Node2: 知识库检索
        templates = node2_knowledge.retrieve_templates(
            f"{product_name} {selling_points}",
            vector_store
        )

        # Node3: LLM生成
        copies = node3_generator.generate_copies(
            product_name, selling_points, sim_results, templates
        )

        # Node4: 代码分析
        analysis = node4_analyzer.analyze_copies(copies)

        # Node5: LLM打分
        scoring = node5_scorer.score_and_recommend(analysis)

        # 格式化输出
        output = format_output(copies, analysis, scoring)
        return output, None

    except Exception as e:
        return None, f"生成失败: {str(e)}"


def format_output(copies, analysis, scoring):
    """
    将工作流结果格式化为 Markdown 展示文本
    参数:
      - copies: 3条文案的文本列表
      - analysis: Node4输出的分析结果
      - scoring: Node5输出的评分结果
    返回:
      - Markdown 格式字符串
    """
    style_names = ["剧情", "痛点", "悬念"]

    lines = ["## 生成结果", ""]

    for i, (copy_text, anal) in enumerate(zip(copies, analysis)):
        style = style_names[i] if i < len(style_names) else f"风格{i+1}"
        cta_text = "有" if anal["has_cta"] else "无"
        emoji_count = anal["emoji_count"]
        word_count = anal["word_count"]

        lines.append("---")
        lines.append("")
        lines.append(f"### 文案{i+1}（{style}风）")
        lines.append(f"**字数**: {word_count} | **emoji**: {emoji_count} | **CTA**: {cta_text}")
        lines.append("")
        lines.append(f"> {copy_text}")
        lines.append("")

    # 推荐结果
    lines.append("---")
    lines.append("")
    lines.append("## 推荐结果")
    lines.append("")

    best = scoring.get("best_recommendation", "文案1")
    reason = scoring.get("reason", "")
    lines.append(f"**最佳推荐**: {best}")
    lines.append("")
    lines.append("**推荐理由**:")
    lines.append(reason)
    lines.append("")

    # 评分表格
    scores = scoring.get("scores", [])
    if scores:
        lines.append("**详细评分**:")
        lines.append("")

        # 表头
        dims = ["吸引力", "信息量", "可读性", "转化潜力", "情感感染力"]
        header = "| 维度 | " + " | ".join(f"文案{i+1}" for i in range(len(scores))) + " |"
        sep = "|------|" + "|".join(["-------"] * len(scores)) + "|"

        lines.append(header)
        lines.append(sep)

        for dim in dims:
            values = []
            for s in scores:
                d = s.get("dimensions", {})
                values.append(str(d.get(dim, "-")))
            lines.append(f"| {dim} | " + " | ".join(values) + " |")

        # 总分行
        total_values = [f"**{s.get('total_score', 0)}**" for s in scores]
        lines.append(f"| **总分** | " + " | ".join(total_values) + " |")

    lines.append("")
    return "\n".join(lines)


def validate_knowledge_input(text=None, file=None):
    """
    验证知识库输入
    参数:
      - text: 粘贴的文本
      - file: 上传的文件路径
    返回:
      - error: str or None
    """
    if not text and not file:
        return "请提供文本内容或上传文件"

    if file and not text:
        # 检查文件扩展名
        if not file.lower().endswith(".txt"):
            return "仅支持 .txt 文件"

    return None


# ============================================================
# Gradio 应用
# ============================================================

def create_app():
    """创建并配置 Gradio 应用"""
    # 确保目录和 API 密钥
    ensure_directories()

    missing_keys = check_api_keys()
    if missing_keys:
        print(f"[警告] 缺少环境变量: {', '.join(missing_keys)}")
        print("请设置后再启动应用，否则 LLM 功能将不可用")

    # 初始化服务
    vector_store = init_vector_store()
    db_conn = init_db()

    # 构建 Gradio 界面
    with gr.Blocks(title="抖音爆款文案生成工具") as app:
        # 状态
        current_session_id = gr.State(None)

        # 左侧栏
        with gr.Row():
            with gr.Column(scale=3):
                gr.Markdown("# 抖音爆款文案生成")

                # 会话列表
                gr.Markdown("### 会话列表")
                session_radio = gr.Radio(
                    choices=[], label="历史会话",
                    interactive=True
                )
                new_session_btn = gr.Button("+ 新建会话", variant="secondary")
                delete_session_btn = gr.Button("删除选中会话", variant="stop", size="sm")

            # 右侧主区域
            with gr.Column(scale=7):
                with gr.Tabs():
                    # Tab1: 文案生成
                    with gr.TabItem("文案生成"):
                        product_input = gr.Textbox(
                            label="商品名称",
                            placeholder="输入商品名称，例如：迷你便携风扇"
                        )
                        selling_input = gr.Textbox(
                            label="卖点描述",
                            placeholder="描述商品的核心卖点，例如：风力大、续航长、小巧便携",
                            lines=3
                        )
                        with gr.Row():
                            generate_btn = gr.Button("生成文案", variant="primary")
                            clear_btn = gr.Button("清空", variant="secondary")

                        output_md = gr.Markdown(
                            label="生成结果",
                            value="*等待输入商品信息...*"
                        )

                    # Tab2: 知识库管理
                    with gr.TabItem("知识库管理"):
                        knowledge_text = gr.Textbox(
                            label="粘贴文案内容",
                            placeholder="在此粘贴要添加到知识库的文案内容...",
                            lines=5
                        )
                        knowledge_file = gr.File(
                            label="或上传 .txt 文件",
                            file_types=[".txt"]
                        )
                        knowledge_style = gr.Dropdown(
                            label="内容类型",
                            choices=["剧情", "痛点", "悬念", "干货", "对比"],
                            value="剧情"
                        )
                        knowledge_btn = gr.Button("添加到知识库", variant="primary")
                        knowledge_feedback = gr.Markdown(value="")

                        # 显示文档数量
                        doc_count_text = gr.Markdown(
                            value=f"当前知识库文档数: {get_document_count(vector_store)}"
                        )

        # ================================================
        # 事件处理
        # ================================================

        def refresh_session_list():
            """刷新会话列表"""
            sessions = get_sessions(db_conn)
            choices = []
            for s in sessions:
                choices.append((f"{s['title']} ({s['created_at']})", s['id']))
            return gr.update(choices=choices)

        def on_new_session():
            """新建会话"""
            sid = create_session(db_conn)
            return sid, "", "", "*新会话已创建，请输入商品信息...*", refresh_session_list()

        new_session_btn.click(
            on_new_session,
            outputs=[current_session_id, product_input, selling_input, output_md, session_radio]
        )

        def on_select_session(session_choice):
            """选择历史会话"""
            if session_choice:
                # session_choice 是选中的值（session_id）
                messages = get_session_messages(db_conn, session_choice)
                history_text = ""
                for msg in messages:
                    role = "用户" if msg["role"] == "user" else "助手"
                    if msg["msg_type"] == "result":
                        history_text = msg["content"]
                return session_choice, history_text or "*暂无生成记录*"
            return None, "*请选择会话*"

        session_radio.change(
            on_select_session,
            inputs=[session_radio],
            outputs=[current_session_id, output_md]
        )

        def on_delete_session(session_id):
            """删除会话"""
            if session_id:
                delete_session(db_conn, session_id)
                return None, "", "", "*会话已删除*", refresh_session_list()
            return session_id, "", "", "*请先选择要删除的会话*", refresh_session_list()

        delete_session_btn.click(
            on_delete_session,
            inputs=[current_session_id],
            outputs=[current_session_id, product_input, selling_input, output_md, session_radio]
        )

        def on_generate(product_name, selling_points, session_id):
            """生成文案"""
            output, error = run_generation_workflow(
                product_name, selling_points, vector_store
            )

            if error:
                return output or f"*错误: {error}*", session_id, refresh_session_list()

            # 保存到数据库
            if session_id is None:
                session_id = create_session(db_conn, title=product_name)
            else:
                update_session_title(db_conn, session_id, product_name)

            add_message(db_conn, session_id, "user",
                        f"商品: {product_name}\n卖点: {selling_points}", "input")
            add_message(db_conn, session_id, "assistant", output, "result")

            return output, session_id, refresh_session_list()

        generate_btn.click(
            on_generate,
            inputs=[product_input, selling_input, current_session_id],
            outputs=[output_md, current_session_id, session_radio]
        )

        def on_clear():
            """清空输入"""
            return "", "", "*等待输入商品信息...*"

        clear_btn.click(
            on_clear,
            outputs=[product_input, selling_input, output_md]
        )

        def on_add_knowledge(text, file, style):
            """添加到知识库"""
            error = validate_knowledge_input(text=text or None, file=file.name if file else None)
            if error:
                return f"*错误: {error}*", gr.update()

            try:
                file_path = file.name if file else None
                result = add_to_knowledge_base(
                    vector_store,
                    text=text or None,
                    file=file_path,
                    style=style
                )
                count = get_document_count(vector_store)
                return f"**{result}**", f"当前知识库文档数: {count}"
            except Exception as e:
                return f"*添加失败: {str(e)}*", gr.update()

        knowledge_btn.click(
            on_add_knowledge,
            inputs=[knowledge_text, knowledge_file, knowledge_style],
            outputs=[knowledge_feedback, doc_count_text]
        )

    return app


if __name__ == "__main__":
    app = create_app()
    app.launch(server_port=7860)
