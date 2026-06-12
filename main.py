# 有bug，已弃用
# 抖音爆款文案生成工具 -- Gradio 应用入口 + 工作流编排
import os
import sys
from pathlib import Path
from datetime import datetime

import gradio as gr

from config import (
    DATA_DIR, CHROMA_DB_DIR, HISTORY_DB_PATH, TEMPLATES_PATH, STYLES,
    ensure_directories, check_api_keys, CTA_KEYWORDS
)
from database.vector_store import (
    init_vector_store, add_to_knowledge_base, get_document_count,
    list_documents, delete_document, delete_documents
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

def run_generation_workflow(product_name, selling_points, vector_store,
                            mode="copywriting", styles=None, count=3,
                            user_expectation=None, director_style="剧情"):
    """
    执行文案生成工作流（5个节点）
    参数:
      - product_name: 商品名称
      - selling_points: 卖点描述
      - vector_store: ChromaDB collection 实例
      - mode: 生成模式 ("copywriting" 或 "director")
      - styles: 文案风格列表（仅文案模式使用）
      - count: 每种风格的生成条数（仅文案模式使用，默认 3）
      - user_expectation: 用户期望（仅导演模式使用，可选）
      - director_style: 导演风格选择（仅导演模式使用，默认 "剧情"）
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
    if user_expectation:
        user_expectation = user_expectation.strip()

    try:
        # Node1: 模拟搜索
        sim_results = node1_sim_search.sim_search(product_name, selling_points)

        # Node2: 知识库检索（传入风格过滤）
        templates = node2_knowledge.retrieve_templates(
            f"{product_name} {selling_points}",
            vector_store,
            style_filter=styles if styles else None
        )

        # Node3: LLM生成（count = 每种风格的条数）
        copies = node3_generator.generate_copies(
            product_name, selling_points, sim_results, templates,
            mode=mode, styles=styles, count=count,
            user_expectation=user_expectation,
            director_style=director_style
        )

        # 展开风格列表：每种风格重复 count 次，匹配实际生成的文案
        if mode == "director":
            expanded_styles = None
        elif styles:
            expanded_styles = [s for s in styles for _ in range(count)]
        else:
            expanded_styles = ["剧情", "痛点", "悬念"]  # 默认3条各1种

        # Node4: 代码分析
        analysis = node4_analyzer.analyze_copies(copies)

        # Node5: LLM打分
        scoring = node5_scorer.score_and_recommend(analysis, mode=mode, styles=expanded_styles)

        # 格式化输出
        output = format_output(copies, analysis, scoring, mode=mode, styles=expanded_styles)
        return output, None

    except Exception as e:
        return None, f"生成失败: {str(e)}"


def format_output(copies, analysis, scoring, mode="copywriting", styles=None):
    """
    将工作流结果格式化为 Markdown 展示文本
    参数:
      - copies: 文案的文本列表
      - analysis: Node4输出的分析结果
      - scoring: Node5输出的评分结果
      - mode: 生成模式 ("copywriting" 或 "director")
      - styles: 文案风格列表（仅文案模式使用）
    返回:
      - Markdown 格式字符串
    """
    # 导演模式使用故事板渲染
    if mode == "director":
        return _format_director_output(copies, analysis, scoring)

    # 文案模式
    styles = styles or ["剧情", "痛点", "悬念"]

    lines = ["## 生成结果", ""]

    for i, (copy_text, anal) in enumerate(zip(copies, analysis)):
        style = styles[i] if i < len(styles) else f"风格{i+1}"
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


def _format_director_output(copies, analysis, scoring):
    """
    格式化导演模式输出为分镜脚本 Markdown
    参数:
      - copies: 分镜脚本文本列表（通常1条）
      - analysis: Node4输出的分析结果
      - scoring: Node5输出的评分结果
    返回:
      - Markdown 格式字符串
    """
    lines = ["## 分镜脚本生成结果", ""]

    storyboard_text = copies[0] if copies else ""

    # 直接渲染分镜脚本文本，保留原始格式
    lines.append("---")
    lines.append("")

    # 按行渲染，对各类型行做轻量格式化
    for line in storyboard_text.strip().split("\n"):
        stripped = line.strip()
        if not stripped:
            lines.append("")
        elif stripped.startswith("🎬"):
            # 场景标题行：加粗
            lines.append(f"**{stripped}**")
        elif stripped.startswith("Step ") or stripped.startswith("测试"):
            # 步骤/测试标识行
            lines.append(f"**{stripped}**")
        elif any(stripped.startswith(t) for t in [
            "开篇：", "冲突/危机：", "产品登场：", "反转/惊喜：",
            "痛点开头：", "放大焦虑：", "引出产品：", "展示效果：",
            "神秘开头：", "紧张铺垫：", "意外反转：", "产品露出：",
            "知识点开场：", "常见误区：", "纠错画面：", "产品植入：",
            "普通方案展示：", "实测对比：", "性价比总结：",
            "对比画面：", "产品特写：", "细节特写：",
            "人物反应：", "结尾：",
        ]):
            # 段落标记行：加粗
            lines.append(f"**{stripped}**")
        elif stripped.startswith("（") and "）" in stripped:
            # 画面指导/括号说明：斜体灰色
            lines.append(f"*{stripped}*")
        else:
            lines.append(f"> {stripped}")

    lines.append("")
    lines.append("---")
    lines.append("")

    # 字数统计
    if analysis:
        anal = analysis[0]
        lines.append("**分镜脚本统计**:")
        lines.append(f"- 总字数: {anal['word_count']} | emoji数量: {anal['emoji_count']} | 包含CTA: {'是' if anal['has_cta'] else '否'}")
        lines.append("")

    # 评分
    scores = scoring.get("scores", [])
    if scores:
        s = scores[0]
        reason = scoring.get("reason", "")
        lines.append("**评分详情**:")
        lines.append("")

        dims = ["吸引力", "信息量", "可读性", "转化潜力", "情感感染力"]
        dim_scores = s.get("dimensions", {})
        for dim in dims:
            lines.append(f"- {dim}: **{dim_scores.get(dim, '-')}** / 10")
        lines.append(f"- **总分**: **{s.get('total_score', 0)}** / 50")
        lines.append("")

        if reason:
            lines.append(f"**评审意见**: {reason}")
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


def build_kb_list_rows(docs, offset):
    """将文档列表转换为侧边栏 Dataframe 行和 CheckboxGroup choices
    参数:
      - docs: 文档列表 [{"id": str, "content": str, "metadata": dict}]
      - offset: 分页偏移量
    返回:
      - (rows, checkbox_choices) 元组
    """
    rows = []
    checkbox_choices = []
    for i, doc in enumerate(docs):
        row_num = offset + i + 1
        summary = doc["content"][:40].replace("\n", " ") if doc["content"] else ""
        style_label = doc["metadata"].get("style", "未分类")
        rows.append([f"#{row_num}", summary, style_label])
        checkbox_choices.append((f"#{row_num} {summary[:30]} [{style_label}]", doc["id"]))
    if not rows:
        rows = [["-", "暂无数据", "-"]]
        checkbox_choices = [("暂无数据", "")]
    return rows, checkbox_choices


def format_kb_page_info(total, offset, limit):
    """计算分页信息文本
    参数:
      - total: 文档总数
      - offset: 当前偏移量
      - limit: 每页条数
    返回:
      - 分页信息字符串，如 "第 1 页 / 共 3 页"
    """
    total_pages = max(1, (total + limit - 1) // limit)
    current_page = (offset // limit) + 1 if total > 0 else 1
    return f"第 {current_page} 页 / 共 {total_pages} 页"


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
        kb_offset = gr.State(0)
        kb_style_filter_state = gr.State("全部")
        kb_batch_delete_mode = gr.State(False)
        kb_batch_selected_ids = gr.State([])
        kb_current_page_docs = gr.State([])

        # 左侧栏 + 右侧主区域
        with gr.Row():
            # ============ 左侧栏 ============
            with gr.Column(scale=3):
                # 会话面板（文案生成 Tab 时显示）
                with gr.Column(visible=True) as session_panel:
                    gr.Markdown("# 抖音爆款文案生成")

                    # 会话列表
                    gr.Markdown("### 会话列表")

                    # 预加载已有会话，解决首次访问时列表为空的问题
                    initial_sessions = get_sessions(db_conn)
                    initial_choices = [
                        (f"{s['title']} ({s['created_at']})", s['id'])
                        for s in initial_sessions
                    ]
                    session_radio = gr.Radio(
                        choices=initial_choices, label="历史会话",
                        interactive=True
                    )
                    new_session_btn = gr.Button("+ 新建会话", variant="secondary")
                    delete_session_btn = gr.Button("删除选中会话", variant="stop", size="sm")

                # 知识库侧边栏面板（知识库管理 Tab 时显示）
                with gr.Column(visible=False) as kb_sidebar_panel:
                    gr.Markdown("### 知识库文档")

                    # 工具栏：风格筛选 + 批量删除 + 退出
                    with gr.Row():
                        kb_sidebar_style = gr.Dropdown(
                            choices=["全部"] + STYLES,
                            value="全部",
                            label="风格筛选",
                            scale=3
                        )
                        kb_batch_delete_btn = gr.Button(
                            "🗑️ 批量删除", variant="secondary", scale=1
                        )
                        kb_exit_delete_btn = gr.Button(
                            "退出删除", variant="secondary", scale=1,
                            visible=False
                        )

                    # 文档列表（普通模式）
                    kb_sidebar_list = gr.Dataframe(
                        headers=["#", "摘要", "风格"],
                        row_count=40,
                        interactive=False,
                    )

                    # 确认删除行（删除确认时显示）
                    with gr.Row(visible=False) as kb_confirm_row:
                        kb_confirm_text = gr.Markdown("")
                        kb_confirm_btn = gr.Button("确认删除", variant="stop")
                        kb_cancel_btn = gr.Button("取消", variant="secondary")

                    # 批量删除选择框（删除模式时显示）
                    kb_sidebar_checkboxes = gr.CheckboxGroup(
                        choices=[], label="选择要删除的文档",
                        visible=False
                    )

                    # 分页控制
                    with gr.Row():
                        kb_sidebar_prev_btn = gr.Button("◀ 上一页", size="sm")
                        kb_sidebar_page_info = gr.Markdown("第 1 页 / 共 1 页")
                        kb_sidebar_next_btn = gr.Button("下一页 ▶", size="sm")

            # ============ 右侧主区域 ============
            with gr.Column(scale=7):
                with gr.Tabs() as tabs:
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

                        # 模式选择
                        mode_radio = gr.Radio(
                            choices=["文案模式", "导演模式"],
                            value="文案模式",
                            label="生成模式"
                        )

                        # 导演模式：用户期望输入 + 导演风格选择
                        user_expectation_input = gr.Textbox(
                            label="用户期望",
                            placeholder="描述你想要的故事情节或视频风格，例如：都市白领的清晨困局",
                            lines=2,
                            visible=False
                        )
                        director_style_radio = gr.Radio(
                            choices=STYLES,
                            value="剧情",
                            label="导演风格",
                            visible=False,
                            interactive=True
                        )

                        # 文案模式：自定义参数
                        with gr.Row(visible=True) as custom_params_row:
                            style_checkbox = gr.CheckboxGroup(
                                choices=STYLES,
                                value=["剧情", "痛点", "悬念"],
                                label="选择风格",
                                interactive=True
                            )
                            count_slider = gr.Slider(
                                minimum=1,
                                maximum=10,
                                value=3,
                                step=1,
                                label="每种风格生成数量"
                            )

                        with gr.Row():
                            generate_btn = gr.Button("生成文案", variant="primary")
                            clear_btn = gr.Button("清空", variant="secondary")

                        output_md = gr.Markdown(
                            label="生成结果",
                            value="*等待输入商品信息...*"
                        )

                    # Tab2: 知识库管理（精简版：文档列表已移至左侧栏）
                    with gr.TabItem("知识库管理"):
                        # 详情面板（初始隐藏）
                        kb_detail_panel = gr.Row(visible=False)
                        with kb_detail_panel:
                            kb_detail_content = gr.Textbox(
                                label="完整内容", lines=8, interactive=False
                            )
                            kb_detail_meta = gr.Markdown(value="")

                        kb_delete_feedback = gr.Markdown(value="")

                        # 添加区域
                        gr.Markdown("---")
                        gr.Markdown("### 添加新内容")
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
                            choices=STYLES,
                            value="剧情"
                        )
                        knowledge_btn = gr.Button("添加到知识库", variant="primary")
                        knowledge_feedback = gr.Markdown(value="")

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

        def on_generate(product_name, selling_points, session_id,
                        mode, user_expectation, director_style,
                        styles, count):
            """生成文案"""
            # 判断模式：Gradio Radio 值映射为内部标识
            mode_key = "director" if mode == "导演模式" else "copywriting"

            output, error = run_generation_workflow(
                product_name, selling_points, vector_store,
                mode=mode_key, styles=list(styles) if styles else None,
                count=int(count) if count else 3,
                user_expectation=user_expectation,
                director_style=director_style
            )

            if error:
                return output or f"*错误: {error}*", session_id, refresh_session_list()

            # 保存到数据库
            if session_id is None:
                session_id = create_session(db_conn, title=product_name)
            else:
                update_session_title(db_conn, session_id, product_name)

            # 构建用户输入描述
            mode_label = "导演模式" if mode_key == "director" else "文案模式"
            user_input = f"商品: {product_name}\n卖点: {selling_points}"
            if mode_key == "director":
                user_input += f"\n用户期望: {user_expectation}"
            else:
                user_input += f"\n风格: {', '.join(styles or [])}\n数量: {count}"
            user_input += f"\n模式: {mode_label}"

            add_message(db_conn, session_id, "user", user_input, "input")
            add_message(db_conn, session_id, "assistant", output, "result")

            return output, session_id, refresh_session_list()

        generate_btn.click(
            on_generate,
            inputs=[product_input, selling_input, current_session_id,
                    mode_radio, user_expectation_input, director_style_radio,
                    style_checkbox, count_slider],
            outputs=[output_md, current_session_id, session_radio]
        )

        def on_mode_change(mode):
            """切换模式时控制UI组件可见性"""
            is_director = (mode == "导演模式")
            return [
                gr.update(visible=is_director),      # user_expectation_input
                gr.update(visible=is_director),      # director_style_radio
                gr.update(visible=not is_director),   # custom_params_row
            ]

        mode_radio.change(
            on_mode_change,
            inputs=[mode_radio],
            outputs=[user_expectation_input, director_style_radio, custom_params_row]
        )

        def on_clear():
            """清空输入"""
            return "", "", "", "*等待输入商品信息...*"

        clear_btn.click(
            on_clear,
            outputs=[product_input, selling_input, user_expectation_input, output_md]
        )

        # ================================================
        # Tab 切换事件
        # ================================================

        def on_tab_select(tab_label):
            """切换 Tab 时控制左侧栏面板的显隐"""
            # Gradio 6.x 传递 gr.SelectData 对象，需提取 label 值
            if hasattr(tab_label, 'value'):
                tab_label = tab_label.value
            if tab_label == "知识库管理":
                # 显示知识库侧边栏，隐藏会话面板，加载数据
                rows, checkbox_c, page_info, current_docs = _kb_load_data("全部", 0)
                return (
                    gr.update(visible=False),     # session_panel
                    gr.update(visible=True),      # kb_sidebar_panel
                    rows,                         # kb_sidebar_list
                    checkbox_c,                   # kb_sidebar_checkboxes (choices)
                    page_info,                    # kb_sidebar_page_info
                    0,                            # kb_offset (重置)
                    "全部",                       # kb_style_filter_state (重置)
                    current_docs,                 # kb_current_page_docs
                )
            else:
                # 显示会话面板，隐藏知识库侧边栏
                return (
                    gr.update(visible=True),      # session_panel
                    gr.update(visible=False),     # kb_sidebar_panel
                    gr.update(),                  # kb_sidebar_list (no change)
                    gr.update(),                  # kb_sidebar_checkboxes (no change)
                    gr.update(),                  # kb_sidebar_page_info (no change)
                    gr.update(),                  # kb_offset (no change)
                    gr.update(),                  # kb_style_filter_state (no change)
                    gr.update(),                  # kb_current_page_docs (no change)
                )

        tabs.select(
            on_tab_select,
            inputs=[tabs],
            outputs=[session_panel, kb_sidebar_panel,
                     kb_sidebar_list, kb_sidebar_checkboxes,
                     kb_sidebar_page_info, kb_offset,
                     kb_style_filter_state, kb_current_page_docs]
        )

        # ================================================
        # 知识库管理回调
        # ================================================
        KB_PAGE_SIZE = 40

        def _kb_load_data(style_filter, offset):
            """通用加载函数：根据筛选和分页参数获取数据，返回所有需要的UI更新"""
            style_val = None if style_filter == "全部" else style_filter
            page_data = list_documents(
                vector_store, offset=offset, limit=KB_PAGE_SIZE,
                style_filter=style_val
            )
            total = page_data["total"]
            docs = page_data["documents"]

            # 使用纯函数构建显示数据
            rows, checkbox_choices = build_kb_list_rows(docs, offset)
            page_info = format_kb_page_info(total, offset, KB_PAGE_SIZE)

            # 提取当前页文档数据（供详情查找）
            current_docs = [
                {"id": d["id"], "content": d["content"], "metadata": d["metadata"]}
                for d in docs
            ]

            # 构建 CheckboxGroup 更新
            checkbox_update = gr.update(choices=checkbox_choices, value=[])

            return rows, checkbox_update, page_info, current_docs

        def on_kb_style_change(style):
            """风格筛选变更，重置到首页"""
            rows, checkbox_c, page_info, current_docs = _kb_load_data(style, 0)
            return rows, checkbox_c, page_info, 0, style, current_docs

        def on_kb_prev_page(style_filter, offset):
            """上一页"""
            new_offset = max(0, offset - KB_PAGE_SIZE)
            rows, checkbox_c, page_info, current_docs = _kb_load_data(style_filter, new_offset)
            return rows, checkbox_c, page_info, new_offset, current_docs

        def on_kb_next_page(style_filter, offset):
            """下一页"""
            page_data = list_documents(
                vector_store, offset=0, limit=1,
                style_filter=(None if style_filter == "全部" else style_filter)
            )
            total = page_data["total"]
            max_offset = max(0, ((total - 1) // KB_PAGE_SIZE) * KB_PAGE_SIZE)
            new_offset = min(offset + KB_PAGE_SIZE, max_offset)
            rows, checkbox_c, page_info, current_docs = _kb_load_data(style_filter, new_offset)
            return rows, checkbox_c, page_info, new_offset, current_docs

        def on_kb_sidebar_row_select(evt: gr.SelectData, current_docs):
            """点击侧边栏文档列表行，在右侧显示详情"""
            if not current_docs:
                return gr.update(visible=False), "", "*暂无文档数据*"

            row_idx = evt.index[0] if evt.index else None
            if row_idx is None or row_idx >= len(current_docs):
                return gr.update(visible=False), "", "*无效选择*"

            doc = current_docs[row_idx]
            content = doc["content"]
            meta = doc["metadata"]
            meta_text = (
                f"**文档ID**: {doc['id']}\n\n"
                f"**风格**: {meta.get('style', '未分类')}\n\n"
                f"**来源**: {meta.get('source', '未知')}\n\n"
                f"**标题**: {meta.get('title', '无')}"
            )
            return gr.update(visible=True), content, meta_text

        def on_kb_batch_delete_click(mode, selected_ids, style_filter, offset):
            """批量删除按钮点击处理"""
            if not mode:
                # 进入删除模式：隐藏 Dataframe，显示 CheckboxGroup 和退出按钮
                rows, checkbox_c, page_info, current_docs = _kb_load_data(style_filter, offset)
                return (
                    gr.update(visible=False),     # kb_sidebar_list
                    checkbox_c,                   # kb_sidebar_checkboxes (含 choices + visible=True)
                    gr.update(visible=False),     # kb_confirm_row
                    gr.update(value=""),          # kb_confirm_text
                    True,                         # kb_batch_delete_mode
                    gr.update(visible=True),      # kb_exit_delete_btn
                    [],                           # kb_batch_selected_ids (清空)
                    page_info,                    # kb_sidebar_page_info
                    offset,                       # kb_offset
                    "",                           # kb_delete_feedback
                    current_docs,                 # kb_current_page_docs
                )
            else:
                # 已在删除模式：检查是否有选中项
                if not selected_ids or len(selected_ids) == 0:
                    # 无选中项，提示
                    rows, checkbox_c, page_info, current_docs = _kb_load_data(style_filter, offset)
                    return (
                        gr.update(visible=False),     # kb_sidebar_list
                        checkbox_c,                   # kb_sidebar_checkboxes
                        gr.update(visible=False),     # kb_confirm_row
                        gr.update(value=""),          # kb_confirm_text
                        True,                         # kb_batch_delete_mode
                        gr.update(visible=True),      # kb_exit_delete_btn
                        [],                           # kb_batch_selected_ids
                        page_info,                    # kb_sidebar_page_info
                        offset,                       # kb_offset
                        "*请先选择要删除的文档*",       # kb_delete_feedback
                        current_docs,                 # kb_current_page_docs
                    )
                # 有选中项，显示确认行
                rows, checkbox_c, page_info, current_docs = _kb_load_data(style_filter, offset)
                confirm_text = f"确定要删除选中的 **{len(selected_ids)}** 条文档吗？"
                return (
                    gr.update(visible=False),         # kb_sidebar_list
                    checkbox_c,                       # kb_sidebar_checkboxes
                    gr.update(visible=True),          # kb_confirm_row
                    gr.update(value=confirm_text),    # kb_confirm_text
                    True,                             # kb_batch_delete_mode
                    gr.update(visible=True),          # kb_exit_delete_btn
                    selected_ids,                     # kb_batch_selected_ids
                    page_info,                        # kb_sidebar_page_info
                    offset,                           # kb_offset
                    "",                               # kb_delete_feedback
                    current_docs,                     # kb_current_page_docs
                )

        def on_kb_confirm_delete(selected_ids, style_filter, offset):
            """确认批量删除"""
            if selected_ids and len(selected_ids) > 0:
                try:
                    count = delete_documents(vector_store, selected_ids)
                    feedback = f"成功删除 {count} 条文档"
                except Exception as e:
                    feedback = f"删除失败: {str(e)}"
            else:
                feedback = ""

            # 重新加载，退出删除模式
            rows, checkbox_c, page_info, current_docs = _kb_load_data(style_filter, offset)
            return (
                gr.update(rows=rows, visible=True),   # kb_sidebar_list
                gr.update(visible=False),              # kb_sidebar_checkboxes
                gr.update(visible=False),              # kb_confirm_row
                gr.update(value=""),                   # kb_confirm_text
                False,                                 # kb_batch_delete_mode
                gr.update(visible=False),              # kb_exit_delete_btn
                [],                                    # kb_batch_selected_ids
                page_info,                             # kb_sidebar_page_info
                offset,                                # kb_offset
                feedback,                              # kb_delete_feedback
                current_docs,                          # kb_current_page_docs
            )

        def on_kb_cancel_delete(style_filter, offset):
            """取消删除，回到删除选择模式"""
            rows, checkbox_c, page_info, current_docs = _kb_load_data(style_filter, offset)
            return (
                gr.update(visible=False),              # kb_sidebar_list
                checkbox_c,                            # kb_sidebar_checkboxes
                gr.update(visible=False),              # kb_confirm_row
                gr.update(value=""),                   # kb_confirm_text
                True,                                  # kb_batch_delete_mode
                gr.update(visible=True),               # kb_exit_delete_btn
                [],                                    # kb_batch_selected_ids
                page_info,                             # kb_sidebar_page_info
                offset,                                # kb_offset
                "",                                    # kb_delete_feedback
                current_docs,                          # kb_current_page_docs
            )

        def on_kb_exit_delete(style_filter, offset):
            """退出批量删除模式，恢复普通视图"""
            rows, checkbox_c, page_info, current_docs = _kb_load_data(style_filter, offset)
            return (
                gr.update(rows=rows, visible=True),    # kb_sidebar_list
                gr.update(visible=False),              # kb_sidebar_checkboxes
                gr.update(visible=False),              # kb_confirm_row
                gr.update(value=""),                   # kb_confirm_text
                False,                                 # kb_batch_delete_mode
                gr.update(visible=False),              # kb_exit_delete_btn
                [],                                    # kb_batch_selected_ids
                page_info,                             # kb_sidebar_page_info
                offset,                                # kb_offset
                "",                                    # kb_delete_feedback
                current_docs,                          # kb_current_page_docs
            )

        def on_kb_checkbox_change(selected):
            """CheckboxGroup 选择变化，更新已选 ID 列表"""
            return selected if selected else []

        def on_add_knowledge(text, file, style, style_filter, offset):
            """添加到知识库并刷新列表"""
            error = validate_knowledge_input(text=text or None, file=file.name if file else None)
            if error:
                rows, checkbox_c, page_info, current_docs = _kb_load_data(style_filter, offset)
                return rows, checkbox_c, page_info, offset, current_docs, f"*错误: {error}*"

            try:
                file_path = file.name if file else None
                result = add_to_knowledge_base(
                    vector_store,
                    text=text or None,
                    file=file_path,
                    style=style
                )
                feedback = f"**{result}**"
            except Exception as e:
                feedback = f"*添加失败: {str(e)}*"

            # 刷新列表
            rows, checkbox_c, page_info, current_docs = _kb_load_data(style_filter, offset)
            return rows, checkbox_c, page_info, offset, current_docs, feedback

        # ================================================
        # 知识库事件绑定
        # ================================================

        # 风格筛选
        kb_sidebar_style.change(
            on_kb_style_change,
            inputs=[kb_sidebar_style],
            outputs=[kb_sidebar_list, kb_sidebar_checkboxes,
                     kb_sidebar_page_info, kb_offset,
                     kb_style_filter_state, kb_current_page_docs]
        )

        # 上一页
        kb_sidebar_prev_btn.click(
            on_kb_prev_page,
            inputs=[kb_sidebar_style, kb_offset],
            outputs=[kb_sidebar_list, kb_sidebar_checkboxes,
                     kb_sidebar_page_info, kb_offset, kb_current_page_docs]
        )

        # 下一页
        kb_sidebar_next_btn.click(
            on_kb_next_page,
            inputs=[kb_sidebar_style, kb_offset],
            outputs=[kb_sidebar_list, kb_sidebar_checkboxes,
                     kb_sidebar_page_info, kb_offset, kb_current_page_docs]
        )

        # 点击文档行查看详情
        kb_sidebar_list.select(
            on_kb_sidebar_row_select,
            inputs=[kb_current_page_docs],
            outputs=[kb_detail_panel, kb_detail_content, kb_detail_meta]
        )

        # 批量删除按钮
        kb_batch_delete_btn.click(
            on_kb_batch_delete_click,
            inputs=[kb_batch_delete_mode, kb_batch_selected_ids,
                    kb_sidebar_style, kb_offset],
            outputs=[kb_sidebar_list, kb_sidebar_checkboxes,
                     kb_confirm_row, kb_confirm_text,
                     kb_batch_delete_mode, kb_exit_delete_btn,
                     kb_batch_selected_ids,
                     kb_sidebar_page_info, kb_offset,
                     kb_delete_feedback, kb_current_page_docs]
        )

        # 确认删除
        kb_confirm_btn.click(
            on_kb_confirm_delete,
            inputs=[kb_batch_selected_ids, kb_sidebar_style, kb_offset],
            outputs=[kb_sidebar_list, kb_sidebar_checkboxes,
                     kb_confirm_row, kb_confirm_text,
                     kb_batch_delete_mode, kb_exit_delete_btn,
                     kb_batch_selected_ids,
                     kb_sidebar_page_info, kb_offset,
                     kb_delete_feedback, kb_current_page_docs]
        )

        # 取消删除
        kb_cancel_btn.click(
            on_kb_cancel_delete,
            inputs=[kb_sidebar_style, kb_offset],
            outputs=[kb_sidebar_list, kb_sidebar_checkboxes,
                     kb_confirm_row, kb_confirm_text,
                     kb_batch_delete_mode, kb_exit_delete_btn,
                     kb_batch_selected_ids,
                     kb_sidebar_page_info, kb_offset,
                     kb_delete_feedback, kb_current_page_docs]
        )

        # 退出删除模式
        kb_exit_delete_btn.click(
            on_kb_exit_delete,
            inputs=[kb_sidebar_style, kb_offset],
            outputs=[kb_sidebar_list, kb_sidebar_checkboxes,
                     kb_confirm_row, kb_confirm_text,
                     kb_batch_delete_mode, kb_exit_delete_btn,
                     kb_batch_selected_ids,
                     kb_sidebar_page_info, kb_offset,
                     kb_delete_feedback, kb_current_page_docs]
        )

        # CheckboxGroup 选择变化
        kb_sidebar_checkboxes.change(
            on_kb_checkbox_change,
            inputs=[kb_sidebar_checkboxes],
            outputs=[kb_batch_selected_ids]
        )

        # 添加到知识库
        knowledge_btn.click(
            on_add_knowledge,
            inputs=[knowledge_text, knowledge_file, knowledge_style,
                    kb_sidebar_style, kb_offset],
            outputs=[kb_sidebar_list, kb_sidebar_checkboxes,
                     kb_sidebar_page_info, kb_offset,
                     kb_current_page_docs, knowledge_feedback]
        )

        # 首次加载知识库侧边栏数据（预填充，侧边栏初始隐藏）
        initial_page_data = list_documents(vector_store, offset=0, limit=KB_PAGE_SIZE, style_filter=None)
        initial_docs = initial_page_data["documents"]
        initial_total = initial_page_data["total"]

        init_rows, init_checkbox_choices = build_kb_list_rows(initial_docs, 0)
        init_current_docs = [
            {"id": d["id"], "content": d["content"], "metadata": d["metadata"]}
            for d in initial_docs
        ]
        init_page_info = format_kb_page_info(initial_total, 0, KB_PAGE_SIZE)

        kb_sidebar_list.value = init_rows
        kb_sidebar_checkboxes.choices = init_checkbox_choices
        kb_sidebar_page_info.value = init_page_info
        kb_current_page_docs.value = init_current_docs

    return app


if __name__ == "__main__":
    app = create_app()
    app.launch(server_port=7860)
