# 节点2: 知识库检索 -- 从 ChromaDB 向量库语义检索相关模板
from database.vector_store import search


def retrieve_templates(query, vector_store, k=5, style_filter=None):
    """
    从向量库中检索相关文案模板
    使用 vector_store.search() 统一检索接口
    参数:
      - query: 用户输入的商品名称+卖点
      - vector_store: ChromaDB collection 实例
      - k: 返回条数
      - style_filter: 可选的风格过滤列表（如 ["剧情", "痛点"]），
                      传入后先从 top_k*3 候选中按 style 元数据过滤，再截取 top_k
    返回:
      - 按相关度排序的 k 条模板文本列表
    """
    # 根据是否有风格过滤决定检索策略
    if style_filter:
        # 有风格过滤：检索更多候选，再在 Python 侧后置过滤
        results = search(vector_store, query, k=k * 3)
        # 按 style 元数据过滤
        filtered = [
            doc for doc in results
            if doc.metadata.get("style") in style_filter
        ]
        # 取前 k 条
        return [doc.page_content for doc in filtered[:k]]
    else:
        # 无风格过滤：正常检索
        results = search(vector_store, query, k=k)
        return [doc.page_content for doc in results]
