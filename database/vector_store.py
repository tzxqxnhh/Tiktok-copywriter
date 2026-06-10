# 向量库 -- ChromaDB 初始化 + 模板灌库 + 增删查操作
import os
import json
import uuid
from pathlib import Path

from chromadb import PersistentClient, EmbeddingFunction
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document

from config import (
    CHROMA_DB_DIR, COLLECTION_NAME, RETRIEVAL_TOP_K,
    EMBEDDING_MODEL, SILICONFLOW_API_BASE, TEMPLATES_PATH
)


class SiliconFlowEmbeddingFunction(EmbeddingFunction):
    """封装 LangChain OpenAIEmbeddings 为 ChromaDB EmbeddingFunction，确保 add 和 query 使用同一个 embedding 模型"""

    def __init__(self, api_key, api_base, model_name):
        self._ef = OpenAIEmbeddings(
            model=model_name,
            openai_api_key=api_key,
            openai_api_base=api_base
        )

    def __call__(self, input):
        """ChromaDB 调用接口：接收文本列表，返回向量列表"""
        return self._ef.embed_documents(input)


def _get_chroma_embedding_function():
    """获取 ChromaDB 兼容的 embedding 函数，使用 SiliconFlow API 的 BAAI/bge-m3 模型 (1024维)"""
    return SiliconFlowEmbeddingFunction(
        api_key=os.environ.get("SILICONFLOW_API_KEY", ""),
        api_base=SILICONFLOW_API_BASE,
        model_name=EMBEDDING_MODEL
    )


def _get_embedding_function():
    """获取 LangChain embedding 函数（向后兼容，供外部直接调用）"""
    return OpenAIEmbeddings(
        model=EMBEDDING_MODEL,
        openai_api_key=os.environ.get("SILICONFLOW_API_KEY", ""),
        openai_api_base=SILICONFLOW_API_BASE
    )


def init_vector_store():
    """
    初始化 ChromaDB 向量库
    1. 连接到 data/chroma_db/ 持久化目录
    2. 检查 collection 是否存在
    3. 如果不存在，从 templates/copy_templates.json 加载数据并灌库
    4. 返回 Chroma 实例
    """
    CHROMA_DB_DIR.mkdir(parents=True, exist_ok=True)

    client = PersistentClient(path=str(CHROMA_DB_DIR))
    embedding_fn = _get_chroma_embedding_function()

    # 检查 collection 是否存在，传入 embedding 函数确保维度一致
    try:
        collection = client.get_collection(
            name=COLLECTION_NAME,
            embedding_function=embedding_fn
        )
    except ValueError:
        # 已有 collection 但 embedding 函数不匹配（如从旧版升级），删除后重建
        try:
            client.delete_collection(name=COLLECTION_NAME)
        except Exception:
            pass
        collection = client.create_collection(
            name=COLLECTION_NAME,
            embedding_function=embedding_fn
        )
    except Exception:
        collection = client.create_collection(
            name=COLLECTION_NAME,
            embedding_function=embedding_fn
        )

    # 如果为空，从模板文件灌入数据
    if collection.count() == 0:
        if TEMPLATES_PATH.exists():
            with open(TEMPLATES_PATH, "r", encoding="utf-8") as f:
                templates = json.load(f)

            texts = [t["content"] for t in templates]
            metadatas = [
                {"style": t["style"], "source": t.get("source", "预置模板")}
                for t in templates
            ]
            ids = [t["id"] for t in templates]

            collection.add(
                documents=texts,
                metadatas=metadatas,
                ids=ids
            )

    return collection


def add_document(chroma_collection, text, metadata):
    """
    添加单条文档到向量库
    参数:
      - chroma_collection: ChromaDB collection 实例
      - text: 文档文本内容
      - metadata: 文档元数据字典
    返回:
      - doc_id: 文档ID字符串
    """
    doc_id = str(uuid.uuid4())
    chroma_collection.add(
        documents=[text],
        metadatas=[metadata],
        ids=[doc_id]
    )
    return doc_id


def add_documents(chroma_collection, texts, metadatas):
    """
    批量添加文档到向量库
    参数:
      - chroma_collection: ChromaDB collection 实例
      - texts: 文本列表
      - metadatas: 元数据字典列表
    返回:
      - doc_ids: 文档ID字符串列表
    """
    if not texts:
        return []

    doc_ids = [str(uuid.uuid4()) for _ in texts]
    chroma_collection.add(
        documents=texts,
        metadatas=metadatas,
        ids=doc_ids
    )
    return doc_ids


def search(chroma_collection, query, k=None, embedding_fn=None):
    """
    语义检索 top-k 文档
    参数:
      - chroma_collection: ChromaDB collection 实例
      - query: 查询文本
      - k: 返回条数，默认使用 RETRIEVAL_TOP_K
      - embedding_fn: 可选的 embedding 函数，用于测试注入；为 None 时使用集合内置 embedding 函数
    返回:
      - list[Document]: langchain Document 对象列表
    """
    if k is None:
        k = RETRIEVAL_TOP_K

    if embedding_fn is not None:
        # 向后兼容：使用外部传入的 embedding 函数（用于测试 mock 场景）
        query_embedding = embedding_fn.embed_query(query)
        results = chroma_collection.query(
            query_embeddings=[query_embedding],
            n_results=k
        )
    else:
        # 使用集合内置的 embedding 函数，确保 add 和 query 维度一致
        results = chroma_collection.query(
            query_texts=[query],
            n_results=k
        )

    documents = []
    if results.get("documents") and results["documents"][0]:
        for i, doc_text in enumerate(results["documents"][0]):
            metadata = results["metadatas"][0][i] if results.get("metadatas") else {}
            doc = Document(page_content=doc_text, metadata=metadata)
            documents.append(doc)

    return documents


def get_document_count(chroma_collection):
    """
    获取向量库中的文档总数
    参数:
      - chroma_collection: ChromaDB collection 实例
    返回:
      - int: 文档总数
    """
    return chroma_collection.count()


def add_to_knowledge_base(chroma_collection, text=None, title=None, style=None, file=None):
    """
    前端添加文档接口 -- 从文本或文件添加到知识库
    参数:
      - chroma_collection: ChromaDB collection 实例
      - text: 用户粘贴的文本内容 (与file二选一)
      - title: 可选标题
      - style: 内容类型标签
      - file: 上传的 .txt 文件路径 (与text二选一)
    返回:
      - 操作结果消息字符串
    """
    # 读取内容
    if text:
        content = text
    elif file:
        with open(file, "r", encoding="utf-8") as f:
            content = f.read()
    else:
        raise ValueError("请提供文本内容或上传文件")

    # 构建元数据
    metadata = {
        "style": style or "未分类",
        "source": "用户上传"
    }
    if title:
        metadata["title"] = title

    # 添加到向量库
    doc_id = add_document(chroma_collection, content, metadata)
    total = get_document_count(chroma_collection)

    return f"添加成功: 文档 {doc_id[:8]} 已入库 (共{total}条)"
