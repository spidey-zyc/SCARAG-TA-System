# SCARAG - Intelligent Course Assistant (Multimodal Edition)

**SCARAG** 是一个基于 RAG (Retrieval-Augmented Generation) 和视觉语义理解的智能课程助教系统。

**[v1.1.0 重大更新]**：系统现已升级为**多模态 RAG**。它不仅能理解课程资料中的文字，还能提取、理解并检索 PDF/PPT 中的**图片信息**（如架构图、流程图、公式截图）。当回答涉及这些图片时，助教会在对话界面直接展示原始图片，实现“图文并茂”的教学体验。

## ✨ 主要功能 (Features)

### 1. 📸 多模态知识库 (Multimodal RAG)

- **图片提取与隔离**: 自动从 PDF/PPTX 中提取图片，并按学科主题（Theme）隔离存储在 `static/images` 目录下。
- **视觉语义索引**: 使用 **Qwen-VL-Plus** 视觉大模型为每一张图片生成详细的语义描述（Caption），实现“以文搜图”。
- **图文联动**: 检索到的图片描述不仅作为上下文喂给模型，还会触发前端的**图片渲染**机制。

### 2. 🖼️ 可视化证据展示 (Visual Grounding)

- **[新增] 前端图片渲染**: 当检索结果包含图片资源时，Chainlit 界面会自动解析元数据，并在助教的回答下方直接展示原始图片。
- **引用增强**: 侧边栏的引用来源现在包含图片预览（如果适用），不仅仅是枯燥的文字。

### 3. 📂 知识库增强检索 (Text RAG)

- 基于本地课程资料（PDF, PPTX, TXT 等）构建向量数据库。
- 能够回答专业课程问题，并提供精确的 **引用来源** 和 **页码**。

### 4. ⚙️ 强大的会话管理

- 支持多会话切换、重命名、删除。
- 历史记录自动归档与回放。
- 全新设计的欢迎界面与深度定制的 CSS 样式。

## 📂 项目结构 (Project Structure)

本次更新引入了静态资源目录和辅助脚本，新的文件树如下：

```
RAG-PROGRAMS/
├── .chainlit/                  # Chainlit UI 配置
├── chat/                       # 存放用户的对话历史记录 (JSON)
├── data/                       # [输入区] 存放原始课程资料 (按主题分类)
│   └── computer_network/       # 例如：计算机网络课件
├── static/                     # [新增][输出区] 静态资源目录 (前端挂载点)
│   └── images/                 # [新增] 自动提取出的图片库
│       └── computer_network/   # 按主题隔离存储的图片文件
├── vector_db/                  # 向量数据库文件 (ChromaDB)
├── app_cl.py                   # [核心] 主应用程序 (新增静态挂载与图片渲染逻辑)
├── config.py                   # [核心] 全局配置 (新增视觉模型与路径配置)
├── process_data.py             # [核心] 数据处理管道 (新增视觉理解流程)
├── document_loader.py          # [核心] 文档加载器 (新增图片提取功能)
├── rag_agent.py                # [核心] 智能体 (新增图文联动提示词)
├── vector_store.py             # 向量库逻辑
├── text_splitter.py            # 文本切分器
├── fix_paths.py                # [新增] 实用工具：修复/更新数据库中的图片路径
├── ingest_orphaned_images.py   # [新增] 实用工具：将现有图片“补录”进数据库
└── requirements.txt            # 项目依赖
```

## 🛠️ 核心逻辑变更说明

本次更新对原有代码架构进行了以下关键调整：

### 1. 数据处理流 (`process_data.py` & `document_loader.py`)

- **分流处理策略**:
  - **文本块**: 依然通过 `TextSplitter` 进行切分。
  - **图片块**: **新增逻辑**。图片被视为不可分割的“原子知识点”，跳过切分步骤。
- **视觉增强**:
  - 在入库前，脚本会筛选出 `is_image=True` 的块，调用 **Qwen-VL-Plus** 生成语义描述（例如：“这是一张二叉树结构图...”）。
  - 该描述被写入 `content` 用于检索，而图片的本地路径被写入 `metadata['image_path']` 用于前端展示。

### 2. 智能体提示词 (`rag_agent.py`)

- **Prompt 工程**: 更新了 `system_prompt`。
  - 新增了 **“图文联动”** 原则，强制要求模型在回答时如果引用了图片内容，必须使用“如图所示”等引导语。
  - 防止模型因为“看不见”文件而产生幻觉或拒绝回答。

### 3. 前端渲染逻辑 (`app_cl.py`)

- **静态资源挂载**: 使用 FastAPI 的 `app.mount` 将本地 `static` 目录挂载为 Web 可访问路径。
- **混合渲染管线**:
  - 在处理检索结果时，除了拼接文本，还会检查 Metadata 中的 `image_path`。
  - **Elements 合并**: 修复了消息更新时的逻辑，确保图片元素 (`cl.Image`) 和侧边栏引用 (`cl.Text`) 能够共存，不会互相覆盖。

## 🚀 快速开始

### 1. 环境准备

```
# 克隆仓库
git clone [https://github.com/spidey-zyc/RAG-programs](https://github.com/spidey-zyc/RAG-programs)
cd RAG-programs

# 安装依赖 (新增了 pillow, pymupdf 等库)
pip install -r requirements.txt
```

### 2. 配置 Key

请在 `config.py` 中填入您的 API Key（支持 OpenAI 格式，推荐使用阿里云 DashScope）：

- `OPENAI_API_KEY`: 用于文本 Embedding 和问答。
- `VISION_API_KEY`: **[新增]** 用于图片语义分析 (Qwen-VL)。

### 3. 数据处理 (构建多模态索引)

将 PDF/PPT 放入 `data/您的主题名/` 目录下，然后运行：

```python
# 例如处理计算机网络主题
python process_data.py --theme computer_network --incremental
```

> *脚本会自动提取图片 -> 生成描述 -> 存入向量库。*

### 4. 启动应用

```python
chainlit run app_cl.py #-w开发时使用

```

## 🔧 常见问题 (FAQ)

Q: 为什么检索到了内容但图片不显示？

A: 请检查数据库中的 image_path 是否正确。如果您手动移动了图片文件夹，或者数据库中缺失了路径信息，可以运行以下脚本进行“急救”：

```
# 自动扫描 static 目录下的孤儿图片，并将其“补录”进数据库
python ingest_orphaned_images.py
```

> *注意：此脚本会以文件名为描述进行索引，不消耗视觉模型 Token，是快速修复显示问题的最佳方案。*

Q: 如何节省视觉模型的 Token 消耗？

A: 同上，使用 ingest_orphaned_images.py 可以跳过昂贵的视觉分析步骤。