# SCARAG - Intelligent Course Assistant (Multimodal Edition)

**SCARAG** 是一个企业级的多模态 RAG（检索增强生成）智能课程助教系统。

该项目不仅仅是一个文档问答机器人，它深度集成了视觉语义理解能力。系统能够自动从复杂的课程资料（PDF/PPTX）中提取插图、架构图和板书，利用 **Qwen-VL** 视觉大模型对其进行“语义转译”，并结合 **ChromaDB** 向量检索和 **LLM 重排序 (Rerank)** 技术，为学生提供“图文并茂、有理有据”的精准答疑体验。

---

## ✨ 核心特性 (Key Features)

### 1. 📸 深度多模态 RAG (Multimodal RAG)
* **智能图文分离**：`document_loader.py` 自动解析 PDF 和 PPTX，将文本与图片分离。图片被归档至 `static/images` 目录，实现静态资源化。
* **视觉语义索引**：利用 **Qwen-VL-Plus** 模型，将非结构化的图片转换为高密度的语义描述文本（Caption），存入向量库。即使用户的问题仅涉及图片内容（如“解释一下这张死锁原理图”），系统也能精准召回。

### 2. 🧠 高级检索架构 (Advanced Retrieval)
* **混合向量库**：基于 **ChromaDB** 构建本地向量索引，支持增量更新。
* **LLM 重排序 (Rerank)**：`rag_agent.py` 内置 Rerank 机制。在向量检索召回 Top-K 结果后，利用 LLM 对结果的相关性进行二次打分和精选，大幅减少“幻觉”和无关信息的干扰。
* **思维链 (CoT) 引导**：系统提示词包含思维链逻辑，引导模型“先检索、再看图、后回答”。

### 3. 🖼️ 可视化证据锚点 (Visual Grounding)
* **原生图片渲染**：当前端检索到包含图片的知识点时，Chainlit 界面会自动渲染原始图片。
* **图文联动回答**：Agent 会根据上下文中的 `[IMAGE_REF]` 标记，在生成的文字回答中自然地引用图片（例如“请参考下图...”），模拟真实的助教讲解场景。

### 4. ⚙️ 全功能会话管理
* **多主题切换**：支持在 UI 面板中动态切换不同的课程知识库（如“操作系统”、“数据结构”）。
* **历史记录回放**：完整的对话历史记录（JSON 格式）存储与回放功能。
* **实时文件处理**：支持用户在对话框直接上传课件，后台自动触发数据处理流水线。

---

## 🏗️ 系统架构 (System Architecture)

### 项目文件结构

```text
SCARAG/
├── app_cl.py                 # [入口] Chainlit 主应用程序 (UI, 路由, 静态挂载)
├── config.py                 # [配置] 模型 Key, 路径, 向量库参数
├── process_data.py           # [ETL] 数据处理管道 (加载 -> 切分 -> 视觉分析 -> 入库)
├── rag_agent.py              # [核心] 智能体逻辑 (Query重写 -> 检索 -> Rerank -> 生成)
├── document_loader.py        # [工具] 文档加载器 (支持 PDF/PPTX/TXT, 图片提取)
├── text_splitter.py          # [工具] 文本切分器 (基于语义的滑动窗口切分)
├── vector_store.py           # [存储] ChromaDB 封装类
├── chat_manager.py           # [管理] 会话历史记录管理
├── inspect_db.py             # [调试] 向量数据库检视工具
├── simulate_search.py        # [调试] 命令行搜索模拟工具
├── requirements.txt          # 项目依赖
├── data/                     # [输入] 原始课程资料 (按主题分类)
├── static/                   # [输出] 静态资源 (前端可访问)
│   └── images/               # 自动提取并归档的图片库
└── vector_db/                # ChromaDB 持久化存储文件
```

### 🔄 数据处理流 (Data Pipeline)

1.  **Ingestion**: `DocumentLoader` 扫描 `data/` 目录。
2.  **Extraction**:
    * **文本**: 提取后经 `TextSplitter` 切分为 Chunk。
    * **图片**: 提取二进制数据 -> 保存至 `static/images/` -> 调用 **Qwen-VL-Plus** 生成描述 -> 描述文本作为 Chunk。
3.  **Embedding**: 调用 `text-embedding-v4` 将所有 Chunk 向量化。
4.  **Storage**: 存入 `vector_db` (ChromaDB)，图片 Chunk 携带 `image_path` 元数据。

---

## 🚀 快速开始 (Quick Start)

### 1. 环境准备
确保 Python 版本 >= 3.10。

```bash
# 克隆项目
git clone [https://github.com/your-repo/SCARAG.git](https://github.com/your-repo/SCARAG.git)
cd SCARAG

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置 API Key
本项目默认使用阿里云 DashScope (通义千问) 服务。请打开 `config.py` 并填入您的 API Key：

```python
# config.py

# 用于文本生成 (Qwen-Max) 和 Embedding
OPENAI_API_KEY = "sk-xxxxxxxxxxxxxxxxxxxxxxxx"

# 用于视觉理解 (Qwen-VL-Plus)
VISION_API_KEY = "sk-xxxxxxxxxxxxxxxxxxxxxxxx"

# 确认 Base URL (通常无需修改)
OPENAI_API_BASE = "[https://dashscope.aliyuncs.com/compatible-mode/v1](https://dashscope.aliyuncs.com/compatible-mode/v1)"
```

### 3. 构建知识库
将您的课程资料（PDF, PPTX, TXT）放入 `data/` 目录下的子文件夹中（例如 `data/OS_2025/`）。
运行数据处理脚本，构建索引：

```bash
# 语法: python process_data.py --theme <主题文件夹名> [选项]

# 示例：处理操作系统课程，增量更新模式
python process_data.py --theme OS_2025 --incremental
```

**可选参数：**
* `--incremental`: 增量模式，不删除旧数据。
* `--text_only`: 仅处理文本（跳过图片分析，节省 Token）。
* `--image_only`: 仅处理图片（适合已处理过文本，需补录图片的场景）。

### 4. 启动应用
使用 Chainlit 启动 Web 界面：

```bash
chainlit run app_cl.py
```
访问浏览器 `http://localhost:8000` 即可开始使用。

---

## 💡 使用指南 (Usage Guide)

### 侧边栏设置面板
启动应用后，点击底部的设置图标（或在移动端打开菜单），您可以：
* **切换/新建对话**：加载之前的问答历史。
* **切换知识库主题**：在“数据结构”和“操作系统”等不同课程间切换。
* **上传文件**：直接在聊天框拖入 PDF/PPT，系统会自动将其保存至当前主题并触发处理流程。

### 调试工具
如果发现检索效果不佳，可以使用以下脚本进行诊断：

* **检查数据库内容**：
    ```bash
    python inspect_db.py
    ```
    查看向量库中实际存储的 Chunk 数量、内容预览及元数据。

* **模拟后端检索**：
    ```bash
    python simulate_search.py
    ```
    在不启动 Web UI 的情况下，测试 RAG 的检索召回率和 Rerank 效果。

---

## 🔧 常见问题 (FAQ)

**Q1: 为什么图片无法在聊天界面显示？**
A: 请检查以下几点：
1. 确保 `process_data.py` 成功运行，且图片已生成在 `static/images/<theme>/` 目录下。
2. 确保 `app_cl.py` 中正确挂载了静态目录（代码中已包含 `app.mount("/static", ...)`）。
3. 使用 `inspect_db.py` 检查数据库中图片 Chunk 的 `metadata['image_path']` 字段是否指向了正确的相对路径。

**Q2: 视觉模型 (Qwen-VL) 消耗 Token 太多怎么办？**
A: 构建知识库时，您可以先运行 `--text_only` 快速处理文本。对于图片，可以精选资料后，单独运行 `--image_only`。

**Q3: 支持哪些文件格式？**
A: 目前核心支持 `.pdf`, `.pptx` (PowerPoint), 和 `.txt`。`.docx` 支持基础文本提取。

**Q4: 为什么回答中有时候会说“如图所示”，有时候没有？**
A: 这是 RAG Agent 的智能特性。`rag_agent.py` 会检测检索到的上下文中是否包含图片元数据。只有当检索结果确实包含图片证据时，System Prompt 才会强制模型结合图片回答，避免产生“幻觉”。