# 抖音爆款文案生成工具

基于 AI 的抖音短视频爆款文案自动生成工具，通过 5 节点工作流编排，结合 LLM 大语言模型与向量知识库，一键生成多种风格的高转化率带货文案。

## 功能特性

- **多风格文案生成**：支持剧情、痛点、悬念三种风格，覆盖抖音主流爆款文案类型
- **智能工作流**：5 节点流水线（模拟搜索 -> 知识库检索 -> LLM 生成 -> 代码分析 -> LLM 评分），自动化端到端生成
- **向量知识库**：基于 ChromaDB 的语义检索系统，预置 25 条爆款模板，支持用户自定义扩充
- **多维度评分**：从吸引力、信息量、可读性、转化潜力、情感感染力 5 个维度对生成文案自动打分
- **会话管理**：基于 SQLite 的多会话对话历史管理，支持新建、切换、删除会话
- **Web 界面**：基于 Gradio 的简洁交互界面，开箱即用

## 项目结构

```
codex-抖音爆款文案生成工具/
├── main.py                  # Gradio 应用入口 + 工作流编排
├── config.py                # 全局配置（API、路径、关键词等）
├── requirements.txt         # Python 依赖
├── workflow/                # 工作流节点模块
│   ├── node1_sim_search.py  # 节点1: 模拟搜索插件
│   ├── node2_knowledge.py   # 节点2: ChromaDB 知识库检索
│   ├── node3_generator.py   # 节点3: DeepSeek LLM 文案生成
│   ├── node4_analyzer.py    # 节点4: 代码分析（字数/emoji/CTA）
│   └── node5_scorer.py      # 节点5: LLM 五维度打分排序
├── database/                # 数据层模块
│   ├── vector_store.py      # ChromaDB 向量库操作
│   └── chat_history.py      # SQLite 会话管理
├── templates/               # 模板资源
│   └── copy_templates.json  # 预置 25 条爆款文案模板
├── tests/                   # 单元测试
│   ├── test_main.py
│   ├── test_node1_sim_search.py
│   ├── test_node2_knowledge.py
│   ├── test_node3_generator.py
│   ├── test_node4_analyzer.py
│   ├── test_node5_scorer.py
│   ├── test_vector_store.py
│   └── test_chat_history.py
└── docs/                    # 项目文档
    └── v1.0-report.md       # v1.0 版本报告
```

## 工作流架构

```
用户输入（商品名称 + 卖点描述）
       |
   Node1: 模拟搜索 --> 生成 10 条参考爆款文案样本
   Node2: 知识库检索 --> ChromaDB 语义检索相关模板
       |
   Node3: LLM 生成 --> DeepSeek 生成 3 种风格文案
       |
   Node4: 代码分析 --> 字数统计 / emoji 计数 / CTA 检测
       |
   Node5: LLM 评分 --> 5 维度打分 + 最佳推荐
       |
   格式化输出（Markdown 表格 + 推荐结果）
```

## 快速开始

### 环境要求

- Python 3.10+
- DeepSeek API Key（用于 LLM 文案生成和评分）
- SiliconFlow API Key（用于 Embedding 向量化）

### 安装

```bash
# 1. 克隆项目
git clone <repo-url>
cd codex-抖音爆款文案生成工具

# 2. 创建虚拟环境（推荐）
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置 API 密钥
# Windows
set DEEPSEEK_API_KEY=your-deepseek-api-key
set SILICONFLOW_API_KEY=your-siliconflow-api-key
# Linux/Mac
export DEEPSEEK_API_KEY=your-deepseek-api-key
export SILICONFLOW_API_KEY=your-siliconflow-api-key
```

### 启动应用

```bash
python main.py
```

启动后访问 `http://localhost:7860` 即可使用 Web 界面。

## 使用说明

### 文案生成

1. 点击「+ 新建会话」创建新会话
2. 在「商品名称」输入框中输入商品名称
3. 在「卖点描述」输入框中描述商品核心卖点
4. 点击「生成文案」按钮，等待几秒即可获得 3 条不同风格的爆款文案及评分

### 知识库管理

1. 切换到「知识库管理」标签页
2. 粘贴文案内容或上传 `.txt` 文件
3. 选择内容类型（剧情/痛点/悬念/干货/对比）
4. 点击「添加到知识库」完成入库

### 文案风格说明

| 风格 | 特点 | 适用场景 |
|------|------|----------|
| 剧情 | 讲故事、制造情感共鸣 | 生活好物、美妆护肤 |
| 痛点 | 戳中用户烦恼、给出解决方案 | 效率工具、家居收纳 |
| 悬念 | 引发好奇心、引导看完视频 | 电子产品、新奇商品 |

## 评分维度

| 维度 | 说明 | 分值 |
|------|------|------|
| 吸引力 | 能否在 3 秒内抓住观众注意力 | 1-10 |
| 信息量 | 是否清晰传达了商品卖点 | 1-10 |
| 可读性 | 语言是否流畅、口语化 | 1-10 |
| 转化潜力 | 能否有效引导用户行动 | 1-10 |
| 情感感染力 | 是否能引起观众情感共鸣 | 1-10 |

## 技术栈

- **UI 框架**: Gradio 5.x
- **LLM**: DeepSeek Chat API（via LangChain OpenAI compatible）
- **Embedding**: SiliconFlow BAAI/bge-m3（1024 维向量）
- **向量数据库**: ChromaDB（持久化存储）
- **会话存储**: SQLite（WAL 模式）
- **测试框架**: pytest 8.x

## 运行测试

```bash
pytest tests/ -v
```

## License

MIT
