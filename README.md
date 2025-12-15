# RAG 我们喜欢你
这是一个RAG任务家人们，你们需要在这里拉取代码并更新
教程：https://blog.csdn.net/sculpta/article/details/104448310

# SCARAG - Intelligent Course Assistant

**SCARAG** 是一个基于 RAG (Retrieval-Augmented Generation) 和视觉语义理解的智能课程助教系统。它能够结合本地知识库（PDF/PPT）和用户上传的图片，提供精准的专业问题解答。

## ✨ 主要功能 (Features)

### 1. 📂 知识库增强检索 (RAG)
- 基于本地课程资料（PDF, PPTX, TXT 等）构建向量数据库。
- 能够回答专业课程问题，并提供精确的 **引用来源** 和 **页码**。

### 2.视觉语义理解 (Multimodal Support)
- **[新增]** 支持 **图片输入**：用户可以直接拖拽上传题目截图、架构图或流程图。
- 系统会自动分析图片中的语义信息，结合图片内容在知识库中进行检索。

### 3. 交互界面 
- **[新增]** 全新设计的欢迎界面。
- 深度定制的 CSS 样式，提供流畅的视觉体验。
- 解决了 Markdown 渲染与 HTML 组件的兼容性问题。

### 4. ⚙️ 强大的会话管理
- 支持多会话切换、重命名。
- 完整的删除逻辑：支持删除特定会话或整个知识库主题，并自动清理 UI 状态。
- 历史记录自动归档与回放。

## 🛠️ 技术栈

- **框架**: [Chainlit](https://github.com/Chainlit/chainlit) (v2.x)
- **大模型**: 
- **向量库**: 
- **后端**: Python 3.10+

## 🚀 快速开始

### 1. 环境准备

```bash
# 克隆仓库
git clone https://github.com/spidey-zyc/RAG-programs
cd RAG-programs

# 创建并激活 Conda 环境
conda create -n RAG python=3.10
conda activate RAG

# 安装依赖
pip install -r requirements.txt
```


### 2.配置
确保项目根目录下存在 .chainlit/config.toml 文件，并开启了 HTML 支持以渲染自定义 UI：
```Ini, TOML
[features]
unsafe_allow_html = true

[ui]
custom_css = "/public/custom.css"
```

### 3.运行
```bash
chainlit run app_cl.py -w
```

### 4.项目结构
```plaintext
RAG-PROGRAMS/
├── .chainlit/          # Chainlit 配置文件
│   └── config.toml     # UI 与 安全设置
├── data/               # 存放上传的知识库文件 (按主题分类)
├── public/
│   └── custom.css      # [新增] 自定义样式文件
├── vector_db/          # 向量数据库存储路径
├── app_cl.py           # [核心] 主应用程序入口
├── chat_manager.py     # [核心] 会话管理逻辑
├── rag_agent.py        # [核心] RAG 检索与生成逻辑
├── process_data.py     # 数据预处理脚本
└── requirements.txt    # 项目依赖
```

### 5.更新日志：
- 12.15 11:55 实现可交互UI界面，新增图片视觉语义理解功能，实现会话和主题的切换