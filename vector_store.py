import os
from typing import List, Dict
import uuid

import chromadb
from chromadb.config import Settings
from openai import OpenAI
from tqdm import tqdm

from config import (
    VECTOR_DB_PATH,
    COLLECTION_NAME,
    OPENAI_API_KEY,
    OPENAI_API_BASE,
    OPENAI_EMBEDDING_MODEL,
    TOP_K,
)


class VectorStore:

    def __init__(
        self,
        db_path: str = VECTOR_DB_PATH,
        collection_name: str = COLLECTION_NAME, # 默认值保留，但允许覆盖
        api_key: str = OPENAI_API_KEY,
        api_base: str = OPENAI_API_BASE,
    ):
        self.db_path = db_path
        
        # 【关键修改】对 collection_name 进行简单清洗，Chroma 要求名称不能含空格等特殊字符
        # 这里我们将空格替换为下划线，确保兼容性
        safe_name = collection_name.strip().replace(" ", "_").replace("-", "_")
        self.collection_name = safe_name

        self.client = OpenAI(api_key=api_key, base_url=api_base)

        os.makedirs(db_path, exist_ok=True)
        self.chroma_client = chromadb.PersistentClient(
            path=db_path, settings=Settings(anonymized_telemetry=False)
        )

        # 【关键修改】使用传入的 safe_name 创建或获取集合
        print(f"📚 [VectorStore] 正在连接集合: {self.collection_name}")
        self.collection = self.chroma_client.get_or_create_collection(
            name=self.collection_name, 
            metadata={"description": f"Theme: {collection_name}"}
        )

    def get_embedding(self, text: str) -> List[float]:
        """获取文本的向量表示

        TODO: 使用OpenAI API获取文本的embedding向量

        """
        # 替换换行符以避免某些模型表现不佳
        text = text.replace("\n", " ")
        try:
            response = self.client.embeddings.create(
                input=[text],
                model=OPENAI_EMBEDDING_MODEL
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"Error getting embedding: {e}")
            return []

    def add_documents(self, chunks: List[Dict[str, str]]) -> None:
        """添加文档块到向量数据库
        TODO: 实现文档块添加到向量数据库
        要求：
        1. 遍历文档块
        2. 获取文档块内容
        3. 获取文档块元数据
        5. 打印添加进度
        """
        batch_size = 10  # 每次处理50条，避免API超时
        
# --- 第一步：准备数据 (速度很快，不需要进度条，或者简单打印) ---
        ids = []
        documents = []
        metadatas = []
        
        print(f"正在准备 {len(chunks)} 条文档数据...")
        for chunk in chunks:
            # 构造元数据
            meta = {
                "filename": chunk["filename"],
                "filetype": chunk["filetype"],
                "page_number": chunk["page_number"],
                "chunk_id": chunk["chunk_id"],
                "image_path": chunk.get("image_path", "") 
            }
            
            # ChromaDB 需要唯一的ID，这里使用 uuid
            ids.append(str(uuid.uuid4()))
            documents.append(chunk["content"])
            metadatas.append(meta)

        # --- 第二步：分批调用 Embedding API 并存储 (这是最慢的步骤，加上进度条) ---
        total_chunks = len(documents)
        print("开始调用 Embedding API 并写入数据库...")
        
        # [关键修改] tqdm 加在这里，监控 API 调用进度
        for i in tqdm(range(0, total_chunks, batch_size), desc="Embedding进度", unit="批"):
            batch_docs = documents[i : i + batch_size]
            batch_ids = ids[i : i + batch_size]
            batch_metas = metadatas[i : i + batch_size]
            
            try:
                # 1. 调用 OpenAI 获取向量
                response = self.client.embeddings.create(
                    input=batch_docs,
                    model=OPENAI_EMBEDDING_MODEL
                )
                batch_embeddings = [data.embedding for data in response.data]
                
                # 2. 写入 ChromaDB
                self.collection.add(
                    ids=batch_ids,
                    embeddings=batch_embeddings,
                    documents=batch_docs,
                    metadatas=batch_metas
                )
            except Exception as e:
                print(f"\n[Error] 第 {i} 到 {i+batch_size} 条数据处理失败: {e}")
                # 可以在这里选择 continue 跳过，或者 break 停止
    def search(self, query: str, top_k: int = TOP_K) -> List[Dict]:
        """搜索相关文档

        TODO: 实现向量相似度搜索
        要求：
        1. 首先获取查询文本的embedding向量（调用self.get_embedding）
        2. 使用self.collection进行向量搜索, 得到top_k个结果
        3. 格式化返回结果，每个结果包含：
           - content: 文档内容
           - metadata: 元数据（文件名、页码等）
        4. 返回格式化的结果列表
        """

        # 1. 获取查询向量
        query_embedding = self.get_embedding(query)
        if not query_embedding:
            return []

        # 2. 向量搜索
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k
        )

        # 3. 格式化结果
        formatted_results = []
        if results["documents"]:
            # Chroma 返回的是列表的列表
            for i in range(len(results["documents"][0])):
                formatted_results.append({
                    "content": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "score": results["distances"][0][i] if "distances" in results else 0
                })
        
        return formatted_results

    def clear_collection(self) -> None:
        """清空collection"""
        self.chroma_client.delete_collection(name=self.collection_name)
        self.collection = self.chroma_client.create_collection(
            name=self.collection_name, metadata={"description": "课程向量数据库"}
        )
        print("向量数据库已清空")

    def get_collection_count(self) -> int:
        """获取collection中的文档数量"""
        return self.collection.count()
