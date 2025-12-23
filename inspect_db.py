import chromadb
from chromadb.config import Settings
import os
from config import VECTOR_DB_PATH

def inspect_vector_db():
    print(f"🕵️‍♂️ 正在检查向量数据库路径: {VECTOR_DB_PATH}")
    
    if not os.path.exists(VECTOR_DB_PATH):
        print("❌ 错误：数据库文件夹不存在！请先运行 process_data.py 处理数据。")
        return

    # 连接 ChromaDB
    client = chromadb.PersistentClient(
        path=VECTOR_DB_PATH, 
        settings=Settings(anonymized_telemetry=False)
    )

    # 1. 列出所有集合 (Collections)
    collections = client.list_collections()
    if not collections:
        print("⚠️ 数据库是空的，没有任何 Collection。")
        return

    print(f"\n📚 发现 {len(collections)} 个主题集合 (Collections):")
    for i, col in enumerate(collections):
        print(f"  {i+1}. [名称]: {col.name}")
        
        # 获取该集合中的所有数据概览
        count = col.count()
        print(f"     [总数据量]: {count} 条")
        
        if count == 0:
            continue

        # 2. 深入检查数据类型 (文本 vs 图片)
        # 我们获取所有 metadata 来分析
        all_data = col.get(include=["metadatas"])
        metadatas = all_data["metadatas"]
        
        image_chunks = 0
        text_chunks = 0
        valid_images = 0
        
        sample_img_meta = None
        
        for meta in metadatas:
            # 检查是否有 image_path 且不为空
            img_path = meta.get("image_path", "")
            if img_path and str(img_path).strip() != "":
                image_chunks += 1
                if os.path.exists(img_path):
                    valid_images += 1
                if sample_img_meta is None:
                    sample_img_meta = meta
            else:
                text_chunks += 1
        
        print(f"     [内容分布]: 📄 文本块: {text_chunks} | 🖼️ 图片块: {image_chunks}")
        print(f"     [图片有效性]: 物理文件存在: {valid_images} / {image_chunks}")
        
        if image_chunks == 0:
            print("     ⚠️ 警告: 该集合中没有图片块！(这就是为什么你搜不到图片)")
        else:
            print(f"     ✅ 正常: 包含图片数据。")
            if sample_img_meta:
                print(f"     🔎 图片元数据样本: {sample_img_meta}")

        # 3. 检查一下图片块的内容是否生成了描述
        if image_chunks > 0:
            # 只取 1 条图片块的内容看看
            results = col.get(where={"chunk_id": sample_img_meta["chunk_id"]}, include=["documents"])
            if results["documents"]:
                content_preview = results["documents"][0][:100].replace("\n", " ")
                print(f"     📝 图片描述预览: \"{content_preview}...\"")
                if "图片内容描述" not in content_preview and len(content_preview) < 50:
                    print("     ⚠️ 警告: 图片块的内容似乎没有被正确替换为AI描述，可能导致检索相关性极低！")

        print("-" * 50)

if __name__ == "__main__":
    inspect_vector_db()