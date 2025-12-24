# config.py
import os
# ==========================================
# 1. 文本模型配置 (纯文本对话时使用)
# ==========================================
# 使用你原有的 Key (用于 Embedding 和 文本模型)
OPENAI_API_KEY = "sk-4cbc56e56f164c02a63563e9462e271f"
OPENAI_API_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# 文本模型名称 (纯文本输入时使用 qwen-max)
TEXT_MODEL_NAME = "qwen-max" 
OPENAI_EMBEDDING_MODEL = "text-embedding-v4"


# ==========================================
# 2. 视觉模型配置 (有图片时使用)
# ==========================================
# 视觉模型专用 Key (你提供的)
VISION_API_KEY = "sk-4cbc56e56f164c02a63563e9462e271f"
VISION_API_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# 视觉模型名称 (有图片输入时使用)
VISION_MODEL_NAME = "qwen-vl-plus"


# ==========================================
# 3. 其他常规配置
# ==========================================
# 数据目录配置
DATA_DIR = os.path.join(".", "data")
# [新增] 提取图片的存储根目录
IMAGES_DIR = os.path.join(".", "static", "images")

# "." 代表当前运行目录
STATIC_DIR = os.path.join(".", "static")

# 向量数据库配置
VECTOR_DB_PATH = os.path.join(".", "vector_db")
COLLECTION_NAME = "data_structure"

# 文本处理配置
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
MAX_TOKENS = 2000

# RAG配置
TOP_K = 5