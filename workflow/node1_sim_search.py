# 节点1: 模拟搜索插件 -- 根据商品名称动态生成10条模拟爆款文案
import random


# 预置10条基础模板，覆盖5种风格
BASE_TEMPLATES = [
    # 剧情 x3
    {
        "title": "买{product_name}之前一定要看！",
        "style": "剧情",
        "content": "昨天逛商场看到{product_name}，试了一下当场就震惊了！回家后马上网上下单，用了3天后只想说：为什么没早点买？姐妹们冲！"
    },
    {
        "title": "被{product_name}种草的第30天",
        "style": "剧情",
        "content": "闺蜜推荐了{product_name}，开始我还不信，结果用了半个月，我自己都惊呆了。今天朋友看到也问我要链接，好东西果然藏不住！"
    },
    {
        "title": "我妈用了一次{product_name}就抢走了",
        "style": "剧情",
        "content": "刚买的{product_name}被我妈看到，她说试一下结果直接拿走了！我又下单买了一个，现在家里人手一个，这谁顶得住啊？"
    },
    # 痛点 x2
    {
        "title": "用了{product_name}才知道之前白花钱了",
        "style": "痛点",
        "content": "以前总觉得这类东西都差不多，买了不少便宜的都不好用。狠心入手{product_name}之后，终于知道什么叫一分钱一分货！早买早享受！"
    },
    {
        "title": "每天都在后悔没早点买{product_name}",
        "style": "痛点",
        "content": "你是不是也纠结了好久要不要买{product_name}？我以前就是，研究了3个月才下单。现在天天用，每次用都后悔：为什么犹豫那么久？"
    },
    # 悬念 x2
    {
        "title": "千万别买{product_name}！除非你看完这个",
        "style": "悬念",
        "content": "我测评了十几款，最后只推荐{product_name}。原因很简单：性价比最高！但是有3个缺点你必须知道，不然买了会后悔。点进来我告诉你！"
    },
    {
        "title": "卖爆的{product_name}到底值不值得买？",
        "style": "悬念",
        "content": "全网都在推的{product_name}到底好不好用？我自费买了一个月才敢说真话。结论出乎意料...视频看到最后有惊喜！"
    },
    # 干货 x2
    {
        "title": "{product_name}使用避坑指南，这3点最重要",
        "style": "干货",
        "content": "作为一个用了2年{product_name}的老用户，整理了5条干货建议：选择时要看3个关键参数，使用方法很多人搞错，保养小技巧能多用2年！点赞收藏！"
    },
    {
        "title": "手把手教你选{product_name}，不花冤枉钱",
        "style": "干货",
        "content": "市面上的{product_name}价格从几十到几千都有，到底差在哪？今天一篇给你讲清楚：核心看这4点，学会了你就是半个专家，再也不怕被忽悠！"
    },
    # 对比 x1
    {
        "title": "{product_name} vs 同价位产品，差距太大了",
        "style": "对比",
        "content": "花了3000块买来同价位3款产品做对比，{product_name}的表现真的惊艳到我了。具体数据说话：从5个维度全面碾压，有些差距肉眼可见！"
    },
]


def sim_search(product_name, selling_points):
    """
    模拟搜索插件 -- 根据商品名称和卖点返回10条模拟爆款文案
    参数:
      - product_name: 商品名称
      - selling_points: 卖点描述
    返回:
      - 10条模拟爆款文案列表
    """
    results = []
    for i, template in enumerate(BASE_TEMPLATES):
        content = template["content"].replace("{product_name}", product_name)
        title = template["title"].replace("{product_name}", product_name)
        likes = random.randint(50000, 300000)

        results.append({
            "index": i + 1,
            "title": title,
            "style": template["style"],
            "likes": likes,
            "content": content,
        })

    return results
