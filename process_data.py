import os
import argparse
from document_loader import DocumentLoader
from text_splitter import TextSplitter
from vector_store import VectorStore
from config import DATA_DIR, CHUNK_SIZE, CHUNK_OVERLAP, VECTOR_DB_PATH

# 你的基础数据路径
BASE_DATA_DIR = os.path.join(".", "data")

def main():
    # 1. 解析参数
    parser = argparse.ArgumentParser()
    parser.add_argument("--theme", type=str, default=None, help="指定主题文件夹")
    parser.add_argument("--incremental", action="store_true", help="增量更新模式")
    args = parser.parse_args()

    # 2. 确定路径
    if args.theme:
        target_dir = os.path.join(BASE_DATA_DIR, args.theme)
    else:
        target_dir = BASE_DATA_DIR # 默认处理全部

    if not os.path.exists(target_dir):
        print(f"目录不存在: {target_dir}")
        return

    print(f"📂 处理目录: {target_dir}")

    # 3. 初始化
    # 注意：DocumentLoader 会递归加载，所以如果是处理子文件夹，它只会加载该文件夹下的
    loader = DocumentLoader(data_dir=target_dir)
    splitter = TextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    vector_store = VectorStore(db_path=VECTOR_DB_PATH)

    # 4. 清理策略
    if not args.incremental:
        print("🧹 全量模式：清空数据库...")
        vector_store.clear_collection()
    else:
        print("➕ 增量模式：保留旧数据...")

    # 5. 执行处理
    documents = loader.load_all_documents()
    if not documents:
        print("⚠️ 该目录下没有文档")
        return

    chunks = splitter.split_documents(documents)
    
    print(f"💾 写入 {len(chunks)} 条数据...")
    vector_store.add_documents(chunks)
    
    print("✅ 完成！")

if __name__ == "__main__":
    main()