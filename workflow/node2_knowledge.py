# 节点2: 知识库检索 -- 从 ChromaDB 向量库语义检索相关模板

def retrieve_templates(query, vector_store, k=5):
    """
    从向量库中检索相关文案模板
    使用集合内置 embedding 函数，确保与数据写入时维度一致
    参数:
      - query: 用户输入的商品名称+卖点
      - vector_store: ChromaDB collection 实例
      - k: 返回条数
    返回:
      - 按相关度排序的 k 条模板文本列表
    """
    results = vector_store.query(
        query_texts=[query],
        n_results=k
    )

    if results.get("documents") and results["documents"][0]:
        return list(results["documents"][0])

    return []
