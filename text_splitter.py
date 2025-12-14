from typing import List, Dict
from tqdm import tqdm
import re


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
    # 1. 首先按句子切分
        # 正则说明：匹配 。！？.!? 后面可能跟的引号，然后是空格或行尾
        sentence_endings = r'([。！？.!?]+[\"\']?(\s|$))'
        parts = re.split(sentence_endings, text)
        
        sentences = []
        current_sent = ""
        for part in parts:
            current_sent += part
            # 只有当包含结束符，或者字符串很长时，才视为一个句子结束
            if re.search(r'[。！？.!?]', part) or len(part.strip()) == 0:
                if current_sent.strip():
                    sentences.append(current_sent)
                current_sent = ""
        # 处理最后剩余的部分
        if current_sent.strip():
            sentences.append(current_sent)

        # 2. 组合句子为 Chunk (实现滑动窗口重叠)
        chunks = []
        current_chunk_sentences = [] # 当前块包含的句子列表
        current_len = 0 # 当前块的总长度

        for sentence in sentences:
            sent_len = len(sentence)

            # 如果加入新句子会超过 chunk_size
            if current_len + sent_len > self.chunk_size:
                # A. 先保存当前这满的一块
                if current_chunk_sentences:
                    chunk_text = "".join(current_chunk_sentences)
                    chunks.append(chunk_text)

                # B. 实现 Overlap：回溯，保留上一块末尾的内容
                # 我们要从 current_chunk_sentences 的末尾往回找，
                # 凑够 chunk_overlap 长度的句子，作为新块的开头
                overlap_buffer = []
                overlap_len = 0
                
                # 倒序遍历当前块的句子
                for old_sent in reversed(current_chunk_sentences):
                    if overlap_len + len(old_sent) <= self.chunk_overlap:
                        overlap_buffer.insert(0, old_sent) # 插到最前面
                        overlap_len += len(old_sent)
                    else:
                        break # 凑够了，停止
                
                # C. 重置当前块：Overlap的内容 + 当前这句新句子
                current_chunk_sentences = overlap_buffer
                current_len = overlap_len
            
            # 将新句子加入当前块
            current_chunk_sentences.append(sentence)
            current_len += sent_len

        # 3. 处理最后一个块
        if current_chunk_sentences:
            chunks.append("".join(current_chunk_sentences))

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
