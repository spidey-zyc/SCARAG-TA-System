import os
from document_loader import DocumentLoader
from text_splitter import TextSplitter
from vector_store import VectorStore

from config import DATA_DIR, CHUNK_SIZE, CHUNK_OVERLAP, VECTOR_DB_PATH


def main():
    if not os.path.exists(DATA_DIR):
        print(f"数据目录不存在: {DATA_DIR}")
        print("请创建数据目录并放入PDF、PPTX、DOCX或TXT文件")
        return

    # 初始化组件
    loader = DocumentLoader(
        data_dir=DATA_DIR,
    )
    splitter = TextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    vector_store = VectorStore(db_path=VECTOR_DB_PATH)
    vector_store.clear_collection()

    # 加载文档
    documents = loader.load_all_documents()
    if not documents:
        print("未找到任何文档")
        return

    # 切分文档
    chunks = splitter.split_documents(documents)

    # 存储到向量数据库
    vector_store.add_documents(chunks)
    
    print("\n数据处理完成！可以运行main.py开始对话")


if __name__ == "__main__":
    main()
