import os
import argparse
from document_loader import DocumentLoader
from text_splitter import TextSplitter
from vector_store import VectorStore
from config import DATA_DIR, CHUNK_SIZE, CHUNK_OVERLAP, VECTOR_DB_PATH

import base64
from tqdm import tqdm
from rag_agent import RAGAgent # 用于调用 Vision API
import argparse


# 你的基础数据路径
BASE_DATA_DIR = os.path.join(".", "data")

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def process_images_with_vision_model(chunks,theme_name):
    """
    遍历文档块，找到图片块，调用视觉模型生成描述
    """
    agent = RAGAgent(initial_theme=theme_name) # 实例化以使用其中的 vision_client
    processed_chunks = []
    
    print("\n👁️ 正在进行图片语义分析与描述生成 (这可能需要一些时间)...")
    
    image_chunks = [c for c in chunks if c.get("is_image")]
    text_chunks = [c for c in chunks if not c.get("is_image")]
    
    # 先把纯文本放进去
    processed_chunks.extend(text_chunks)
    
    for chunk in tqdm(image_chunks, desc="分析图片", unit="张"):
        try:
            img_path = chunk["image_path"]
            if not os.path.exists(img_path):
                continue
                
            base64_img = encode_image(img_path)
            
            # 使用 Agent 中已有的方法生成描述
            # 注意：这里我们复用 understand_image，但提示词是针对通用搜索优化的
            description = agent.understand_image(base64_img)
            
            if description:
                # 更新内容：加上文件名作为前缀，增强检索相关性
                final_content = f"【图片内容描述】(文件: {chunk['filename']}, 页码: {chunk['page_number']})\n{description}"
                chunk["content"] = final_content
                # 移除 is_image 标记，或者保留它用于后续逻辑，这里我们要保留 image_path
                processed_chunks.append(chunk)
                
        except Exception as e:
            print(f"处理图片 {chunk.get('image_path')} 失败: {e}")
    
    return processed_chunks









def main():
    # 1. 解析参数
    parser = argparse.ArgumentParser()
    parser.add_argument("--theme", type=str, default="Default", help="指定主题文件夹") # 默认为 Default
    parser.add_argument("--incremental", action="store_true", help="增量更新模式")
    parser.add_argument("--text_only", action="store_true", help="仅处理文本(快速模式)")
    parser.add_argument("--image_only", action="store_true", help="仅处理图片(后台模式)")
    args = parser.parse_args()

    # 2. 确定路径
    # 如果是 Default，可能指向根 data 目录，或者 data/Default，根据你的文件结构决定
    # 这里假设 data 下面全是子文件夹
    theme_name = args.theme
    if theme_name == "default":
        # 如果你想把 data 根目录作为默认
        target_dir = BASE_DATA_DIR 
    else:
        target_dir = os.path.join(BASE_DATA_DIR, theme_name)

    if not os.path.exists(target_dir):
        print(f"目录不存在: {target_dir}")
        return

    print(f"📂 处理目录: {target_dir}")
    print(f"📚 目标主题(Collection): {theme_name}")

    # 3. 初始化 (传入 collection_name)
    loader = DocumentLoader(data_dir=target_dir)
    splitter = TextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    
    # 【关键修改】在这里传入 theme_name
    vector_store = VectorStore(
        db_path=VECTOR_DB_PATH, 
        collection_name=theme_name 
    )
    
    # 4. 清理策略 (针对当前 collection)
    if args.image_only:
        print("➕ 后台图片处理模式：强制使用增量更新...")
        args.incremental = True

    if not args.incremental:
        print(f"🧹 全量模式：清空主题【{theme_name}】的数据...")
        vector_store.clear_collection() # 这只会清空当前主题，不会影响其他主题
    else:
        print("➕ 增量模式：保留旧数据...")

    # 5. 加载文档
    documents = loader.load_all_documents(specific_dir=target_dir)
    if not documents:
        print("⚠️ 该目录下没有文档")
        return

    # 6. 分流处理
    all_chunks = []
    
    # --- 分支 A: 处理文本 (只要没开启 image_only 就跑文本) ---
    if not args.image_only:
        print("🚀 [Text Mode] 正在处理文本...")
        raw_text_docs = [d for d in documents if not d.get("is_image")]
        text_chunks = splitter.split_documents(raw_text_docs)
        all_chunks.extend(text_chunks)
    else:
        print("⏩ [Text Mode] 跳过文本处理")

    # --- 分支 B: 处理图片 (只要没开启 text_only 就跑图片) ---
    if not args.text_only:
        print("👁️ [Vision Mode] 正在分析图片...")
        raw_image_docs = [d for d in documents if d.get("is_image")]
        
        image_chunks_formatted = []
        for i, img_doc in enumerate(raw_image_docs):
            img_doc["chunk_id"] = f"img_{i}"
            image_chunks_formatted.append(img_doc)
        
        if image_chunks_formatted:
            processed_imgs = process_images_with_vision_model(image_chunks_formatted,theme_name=theme_name)
            all_chunks.extend(processed_imgs)
    else:
        print("⏩ [Vision Mode] 跳过图片处理 (将在后台运行)")

    # 7. 写入数据库
    if all_chunks:
        print(f"💾 写入 {len(all_chunks)} 条数据...")
        
        # 清洗 metadata 防止 None 报错
        for chunk in all_chunks:
            if "is_image" in chunk: del chunk["is_image"]
            if chunk.get("image_path") is None: chunk["image_path"] = ""
                
        vector_store.add_documents(all_chunks)
        print("✅ 处理完成！")
    else:
        print("⚠️ 本次没有生成任何数据片段。")

if __name__ == "__main__":
    main()