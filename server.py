# 抖音爆款文案生成工具 -- FastAPI 服务器入口
# 替代 Gradio 前端，使用 Vue 3 + REST API 架构

import os
import sys
import asyncio
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

# 初始化基础设施
from config import (
    ensure_directories, check_api_keys, STYLES, DATA_DIR
)
ensure_directories()

missing_keys = check_api_keys()
if missing_keys:
    print(f"[警告] 缺少环境变量: {', '.join(missing_keys)}")
    print("请设置后再使用，否则 LLM 功能将不可用")

# 初始化全局服务实例
from database.vector_store import (
    init_vector_store, add_to_knowledge_base, get_document_count,
    list_documents, delete_document, delete_documents
)
from database.chat_history import (
    init_db, create_session, delete_session, get_sessions,
    add_message, get_session_messages, update_session_title
)

# 知识库分页大小（与 main.py 中 create_app() 内定义的 KB_PAGE_SIZE 保持一致）
KB_PAGE_SIZE = 20

try:
    vector_store = init_vector_store()
    print(f"[信息] 向量库初始化成功，文档数: {vector_store.count()}")
except Exception as e:
    print(f"[错误] 向量库初始化失败: {e}")
    vector_store = None

try:
    db_conn = init_db()
    print("[信息] 数据库初始化成功")
except Exception as e:
    print(f"[错误] 数据库初始化失败: {e}")
    db_conn = None

# 导入 main.py 中的纯函数（无副作用，不启动 Gradio 应用）
from main import (
    run_generation_workflow, format_output,
    validate_knowledge_input, build_kb_list_rows, format_kb_page_info
)

# ============================================================
# FastAPI 应用 + 中间件
# ============================================================

app = FastAPI(title="抖音爆款文案生成工具 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# Pydantic 模型
# ============================================================

class GenerateRequest(BaseModel):
    product_name: str
    selling_points: str
    session_id: str | None = None
    mode: str = "copywriting"
    styles: list[str] | None = None
    count: int = 3
    user_expectation: str | None = None
    director_style: str = "剧情"

class BatchDeleteRequest(BaseModel):
    ids: list[str]

class CreateSessionRequest(BaseModel):
    title: str | None = None

# ============================================================
# 健康检查 + 配置 API
# ============================================================

@app.get("/api/config")
async def get_config():
    """返回应用配置"""
    return {
        "styles": STYLES,
        "api_keys_configured": len(check_api_keys()) == 0,
    }

# ============================================================
# 会话 API
# ============================================================

@app.get("/api/sessions")
async def list_sessions():
    """获取所有会话列表"""
    if db_conn is None:
        raise HTTPException(503, "数据库未初始化")
    sessions = get_sessions(db_conn)
    return {"sessions": sessions}


@app.post("/api/sessions")
async def create_new_session(req: CreateSessionRequest):
    """创建新会话"""
    if db_conn is None:
        raise HTTPException(503, "数据库未初始化")
    session_id = create_session(db_conn, title=req.title)
    sessions = get_sessions(db_conn)
    # 找到刚创建的会话
    created = next((s for s in sessions if s["id"] == session_id), None)
    return {
        "session_id": session_id,
        "title": created["title"] if created else "",
        "created_at": created["created_at"] if created else "",
    }


@app.delete("/api/sessions/{session_id}")
async def remove_session(session_id: str):
    """删除指定会话"""
    if db_conn is None:
        raise HTTPException(503, "数据库未初始化")
    success = delete_session(db_conn, session_id)
    if not success:
        raise HTTPException(404, "会话不存在")
    return {"success": True}


@app.get("/api/sessions/{session_id}/messages")
async def get_messages(session_id: str):
    """获取会话的消息历史"""
    if db_conn is None:
        raise HTTPException(503, "数据库未初始化")
    messages = get_session_messages(db_conn, session_id)
    return {"messages": messages}

# ============================================================
# 生成 API
# ============================================================

@app.post("/api/generate")
async def generate(req: GenerateRequest):
    """执行文案生成工作流"""
    if vector_store is None:
        raise HTTPException(503, "向量库未初始化")
    if db_conn is None:
        raise HTTPException(503, "数据库未初始化")

    # 输入验证
    if not req.product_name or not req.product_name.strip():
        return {"output": None, "session_id": None, "error": "请输入商品名称和卖点"}

    if not req.selling_points or not req.selling_points.strip():
        return {"output": None, "session_id": None, "error": "请输入商品名称和卖点"}

    # 映射前端模式到内部标识
    mode_key = "director" if req.mode == "director" else "copywriting"

    # 在线程池中运行同步 LLM 调用，避免阻塞事件循环
    try:
        output, error = await asyncio.to_thread(
            run_generation_workflow,
            req.product_name,
            req.selling_points,
            vector_store,
            mode=mode_key,
            styles=list(req.styles) if req.styles else None,
            count=req.count,
            user_expectation=req.user_expectation,
            director_style=req.director_style,
        )
    except Exception as e:
        return {"output": None, "session_id": None, "error": f"生成失败: {str(e)}"}

    if error:
        return {"output": output, "session_id": None, "error": error}

    # 保存到数据库
    session_id = req.session_id
    if session_id is None:
        session_id = create_session(db_conn, title=req.product_name)
    else:
        update_session_title(db_conn, session_id, req.product_name)

    # 构建用户输入描述
    mode_label = "导演模式" if mode_key == "director" else "文案模式"
    user_input = f"商品: {req.product_name}\n卖点: {req.selling_points}"
    if mode_key == "director":
        user_input += f"\n用户期望: {req.user_expectation or '无'}"
    else:
        styles_str = ', '.join(req.styles) if req.styles else ''
        user_input += f"\n风格: {styles_str}\n数量: {req.count}"
    user_input += f"\n模式: {mode_label}"

    add_message(db_conn, session_id, "user", user_input, "input")
    add_message(db_conn, session_id, "assistant", output, "result")

    return {"output": output, "session_id": session_id, "error": None}

# ============================================================
# 知识库 API
# ============================================================

@app.get("/api/knowledge-base")
async def list_knowledge_base(
    style: str = Query("全部"),
    offset: int = Query(0),
    limit: int = Query(20),
):
    """分页列出知识库文档（支持风格筛选）"""
    if vector_store is None:
        raise HTTPException(503, "向量库未初始化")

    style_val = None if style == "全部" else style
    page_data = list_documents(
        vector_store, offset=offset, limit=limit, style_filter=style_val
    )

    total = page_data["total"]
    docs = page_data["documents"]

    # 使用 main.py 的纯函数构建前端所需数据
    rows, checkbox_choices = build_kb_list_rows(docs, offset)
    page_info = format_kb_page_info(total, offset, limit)

    # 提取文档数据供前端详情展示
    current_docs = [
        {"id": d["id"], "content": d["content"], "metadata": d["metadata"]}
        for d in docs
    ]

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "page_info": page_info,
        "rows": rows,
        "checkbox_choices": checkbox_choices,
        "documents": current_docs,
    }


@app.post("/api/knowledge-base")
async def add_knowledge(
    text: str = Form(""),
    style: str = Form("剧情"),
    title: str = Form(""),
    file: UploadFile | None = None,
):
    """添加内容到知识库（支持文本粘贴和文件上传）"""
    if vector_store is None:
        raise HTTPException(503, "向量库未初始化")

    # 验证输入（复用 main.py 的验证函数）
    text_val = text.strip() if text else None
    file_name = file.filename if file else None
    error = validate_knowledge_input(text=text_val, file=file_name)
    if error:
        return {"message": None, "error": error}

    temp_file_path = None
    try:
        # 处理文件上传
        if file and file.filename:
            temp_dir = DATA_DIR / "temp"
            temp_dir.mkdir(parents=True, exist_ok=True)
            temp_file_path = str(temp_dir / file.filename)
            content = await file.read()
            with open(temp_file_path, "wb") as f:
                f.write(content)

        # 调用已有的添加逻辑
        result = add_to_knowledge_base(
            vector_store,
            text=text_val if text_val else None,
            title=title.strip() if title else None,
            style=style,
            file=temp_file_path,
        )
        return {"message": result, "error": None}

    except Exception as e:
        return {"message": None, "error": f"添加失败: {str(e)}"}

    finally:
        # 清理临时文件
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except OSError:
                pass


@app.get("/api/knowledge-base/{doc_id}")
async def get_knowledge_doc(doc_id: str):
    """获取单个文档详情"""
    if vector_store is None:
        raise HTTPException(503, "向量库未初始化")

    # 通过 list_documents 获取全部文档后查找（简单方案，适用于中小规模）
    page_data = list_documents(vector_store, offset=0, limit=10000)
    for doc in page_data["documents"]:
        if doc["id"] == doc_id:
            return {
                "id": doc["id"],
                "content": doc["content"],
                "metadata": doc["metadata"],
            }
    raise HTTPException(404, "文档不存在")


@app.delete("/api/knowledge-base/{doc_id}")
async def remove_knowledge_doc(doc_id: str):
    """删除单条文档"""
    if vector_store is None:
        raise HTTPException(503, "向量库未初始化")

    success = delete_document(vector_store, doc_id)
    if not success:
        raise HTTPException(404, "文档不存在或删除失败")
    return {"success": True}


@app.post("/api/knowledge-base/batch-delete")
async def batch_delete_knowledge(req: BatchDeleteRequest):
    """批量删除文档"""
    if vector_store is None:
        raise HTTPException(503, "向量库未初始化")

    if not req.ids:
        return {"deleted_count": 0, "error": None}

    try:
        count = delete_documents(vector_store, req.ids)
        return {"deleted_count": count, "error": None}
    except Exception as e:
        return {"deleted_count": 0, "error": str(e)}

# ============================================================
# 静态文件服务（必须在 API 路由之后注册）
# ============================================================

frontend_dir = Path(__file__).parent / "frontend"
frontend_dir.mkdir(exist_ok=True)
(frontend_dir / "css").mkdir(exist_ok=True)
(frontend_dir / "js" / "components").mkdir(parents=True, exist_ok=True)

app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

# ============================================================
# 启动入口
# ============================================================

if __name__ == "__main__":
    print("=" * 50)
    print("  抖音爆款文案生成工具 (Vue 3 + FastAPI)")
    print(f"  启动地址: http://127.0.0.1:8000")
    print("=" * 50)
    uvicorn.run(app, host="127.0.0.1", port=8000)
