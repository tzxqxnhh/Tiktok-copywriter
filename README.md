# 抖音爆款文案生成工具 v2.0

基于 AI 的抖音短视频爆款文案自动生成工具。通过 5 节点工作流编排，结合 LLM 大语言模型与向量知识库，支持**文案模式**（多风格口播文案）和**导演模式**（分镜脚本），一键生成高转化率带货内容。

## 功能特性

- **双模式生成**：文案模式（多条风格化口播文案 + 五维度评分）+ 导演模式（完整分镜脚本）
- **5 种文案风格**：剧情、痛点、悬念、干货、对比，每种风格独立 prompt 调优
- **智能工作流**：5 节点流水线（模拟搜索 -> 知识库检索 -> LLM 生成 -> 代码分析 -> LLM 评分）
- **向量知识库**：基于 ChromaDB 的语义检索，预置 25 条模板，支持风格过滤检索 + 用户自定义扩充
- **知识库可视化管理**：文档列表、风格筛选、分页浏览、详情查看、单条/批量删除
- **多会话管理**：基于 SQLite 的会话历史，支持新建、切换、删除会话
- **双入口架构**：Vue 3 + FastAPI（推荐，端口 8000）+ Gradio（保留，端口 7860）

## 项目结构

```
项目根目录/
├── server.py                 # FastAPI 应用入口 + 11 个 REST API 端点（推荐）
├── main.py                   # Gradio 应用入口 + 工作流编排（保留）
├── config.py                 # 全局配置（API、路径、风格列表等）
├── requirements.txt          # Python 依赖（Gradio 版）
├── requirements-server.txt   # Python 依赖（FastAPI 版）
│
├── frontend/                 # Vue 3 前端
│   ├── index.html            #   主页面 + Vue 3 CDN
│   ├── css/style.css         #   全局样式 + Markdown 渲染
│   └── js/
│       ├── api.js            #   fetch API 封装层
│       └── app.js            #   Vue 3 根组件 + 业务逻辑
│
├── workflow/                 # 工作流节点模块
│   ├── node1_sim_search.py   #   节点1: 模拟搜索
│   ├── node2_knowledge.py    #   节点2: ChromaDB 知识库检索（支持风格过滤）
│   ├── node3_generator.py    #   节点3: DeepSeek LLM 文案/分镜生成
│   ├── node4_analyzer.py     #   节点4: 代码分析（字数/emoji/CTA）
│   └── node5_scorer.py       #   节点5: LLM 五维度评分排序
│
├── database/                 # 数据层模块
│   ├── vector_store.py       #   ChromaDB 向量库（增删检索/列表/风格过滤）
│   └── chat_history.py       #   SQLite 多会话管理
│
├── templates/
│   └── copy_templates.json   # 预置 25 条爆款文案模板（只读）
│
├── data/                     # 运行时数据（不入 git）
│   ├── chroma_db/            #   ChromaDB 持久化文件
│   └── chat_history.db       #   SQLite 对话历史数据库
│
├── tests/                    # 单元测试（pytest，共 148 个）
├── docs/                     # 项目文档与规格说明
│   ├── spec.md               #   产品规格 + 迭代计划
│   ├── v2.0-report.md        #   v2.0 版本报告（最新）
│   ├── v1.2-report.md        #   v1.2 版本报告
│   ├── v1.1-report.md        #   v1.1 版本报告
│   └── v1.0-report.md        #   v1.0 版本报告
│
├── AGENTS.md                 # Agent 入口页
└── SKILL.md                  # TDD 开发规范
```

## 工作流架构

```
用户输入（商品名称 + 卖点描述 + 模式/风格/数量参数）
       |
   Node1: 模拟搜索    --> 生成 10 条参考爆款文案样本
   Node2: 知识库检索   --> ChromaDB 语义检索 top-5 模板（支持风格过滤）
       |
   Node3: LLM 生成     --> DeepSeek 生成多条风格化文案 / 完整分镜脚本
       |
   Node4: 代码分析     --> 字数统计 / emoji 计数 / CTA 检测
       |
   Node5: LLM 评分     --> 5 维度打分 + 排名 + 最佳推荐
       |
   格式化输出          --> Markdown（文案模式：表格+推荐 / 导演模式：分镜脚本+评分）
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
pip install -r requirements.txt        # Gradio 版依赖
pip install -r requirements-server.txt # FastAPI 版依赖

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
# 推荐：Vue 3 + FastAPI（端口 8000）
python server.py

# 保留：Gradio 版（端口 7860）
python main.py
```

启动后浏览器访问对应地址即可使用 Web 界面。

## 使用说明

### 文案模式

1. 点击「+ 新建会话」创建新会话
2. 输入商品名称和卖点描述
3. 勾选所需风格（剧情/痛点/悬念/干货/对比）
4. 拖动滑块设置每种风格的生成数量（1-10 条）
5. 点击「生成文案」，等待 LLM 生成 + 评分
6. 查看 Markdown 格式的文案列表和五维度评分表

### 导演模式

1. 切换到「导演模式」
2. 输入商品名称、卖点描述，可选填写用户期望
3. 选择导演风格（剧情/痛点/悬念/干货/对比）
4. 点击「生成文案」，获得完整分镜脚本（场景/人物/对话/镜头指导）+ 评分详情

### 知识库管理

1. 切换到「知识库管理」Tab
2. 左侧栏查看文档列表，支持风格筛选和分页
3. 点击文档行查看详情（内容 + 元数据）
4. 点击「批量删除」进入删除模式，勾选后确认删除
5. 在右侧粘贴文案或上传 `.txt` 文件，选择风格后添加到知识库

## 文案风格说明

| 风格 | 特点 | 适用场景 |
|------|------|----------|
| 剧情 | 讲故事、制造情感共鸣 | 生活好物、美妆护肤 |
| 痛点 | 戳中用户烦恼、给出解决方案 | 效率工具、家居收纳 |
| 悬念 | 引发好奇心、引导看完视频 | 电子产品、新奇商品 |
| 干货 | 知识科普、专业背书 | 健康食品、教育产品 |
| 对比 | 前后反差、效果展示 | 清洁用品、健身器材 |

## 评分维度

| 维度 | 说明 | 分值 |
|------|------|------|
| 吸引力 | 能否在 3 秒内抓住观众注意力 | 1-10 |
| 信息量 | 是否清晰传达了商品卖点 | 1-10 |
| 可读性 | 语言是否流畅、口语化 | 1-10 |
| 转化潜力 | 能否有效引导用户行动 | 1-10 |
| 情感感染力 | 是否能引起观众情感共鸣 | 1-10 |

## 技术栈

- **推荐前端**: Vue 3 CDN + marked.js（HTML/JS/CSS，无构建工具）
- **保留前端**: Gradio 6.x
- **后端**: FastAPI + Uvicorn（推荐）/ Gradio 内置服务器（保留）
- **LLM**: DeepSeek Chat API（via LangChain OpenAI compatible）
- **Embedding**: SiliconFlow BAAI/bge-m3（1024 维向量）
- **向量数据库**: ChromaDB（持久化模式）
- **会话存储**: SQLite（WAL 模式）
- **测试框架**: pytest 8.x（148 个单元测试）

## API 端点（FastAPI）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/config` | 应用配置（风格列表 + API 密钥状态） |
| GET | `/api/sessions` | 会话列表 |
| POST | `/api/sessions` | 新建会话 |
| DELETE | `/api/sessions/{id}` | 删除会话 |
| GET | `/api/sessions/{id}/messages` | 会话消息历史 |
| POST | `/api/generate` | 执行文案生成工作流 |
| GET | `/api/knowledge-base` | 分页列出知识库文档（支持风格筛选） |
| POST | `/api/knowledge-base` | 添加知识库内容（支持文件上传） |
| GET | `/api/knowledge-base/{id}` | 文档详情 |
| DELETE | `/api/knowledge-base/{id}` | 删除单条文档 |
| POST | `/api/knowledge-base/batch-delete` | 批量删除文档 |

## 运行测试

```bash
# 运行全部测试
pytest tests/ -v

# 运行单个测试文件
pytest tests/test_node3_generator.py -v
```

## License

MIT
