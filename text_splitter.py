from typing import List, Dict
from tqdm import tqdm


class TextSplitter:
    def __init__(self, chunk_size: int, chunk_overlap: int):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split_text(self, text: str) -> List[str]:
        """将文本切分为块

        TODO: 实现文本切分算法
        要求：
        1. 将文本按照chunk_size切分为多个块
        2. 相邻块之间要有chunk_overlap的重叠（用于保持上下文连续性）
        3. 尽量在句子边界处切分（查找句子结束符：。！？.!?\n\n）
        4. 返回切分后的文本块列表
        """
        if not text:
            return []

        chunks = []

        return chunks

    def split_documents(self, documents: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """切分多个文档。
        对于PDF和PPT，已经按页/幻灯片分割，不再进行二次切分
        对于DOCX和TXT，进行文本切分
        """
        chunks_with_metadata = []

        for doc in tqdm(documents, desc="处理文档", unit="文档"):
            content = doc.get("content", "")
            filetype = doc.get("filetype", "")

            if filetype in [".pdf", ".pptx"]:
                chunk_data = {
                    "content": content,
                    "filename": doc.get("filename", "unknown"),
                    "filepath": doc.get("filepath", ""),
                    "filetype": filetype,
                    "page_number": doc.get("page_number", 0),
                    "chunk_id": 0,
                    "images": doc.get("images", []),
                }
                chunks_with_metadata.append(chunk_data)

            elif filetype in [".docx", ".txt"]:
                chunks = self.split_text(content)
                for i, chunk in enumerate(chunks):
                    chunk_data = {
                        "content": chunk,
                        "filename": doc.get("filename", "unknown"),
                        "filepath": doc.get("filepath", ""),
                        "filetype": filetype,
                        "page_number": 0,
                        "chunk_id": i,
                        "images": [],
                    }
                    chunks_with_metadata.append(chunk_data)

        print(f"\n文档处理完成，共 {len(chunks_with_metadata)} 个块")
        return chunks_with_metadata
