# rag_agent.py
from typing import List, Dict, Optional, Tuple
from openai import OpenAI
from config import (
    OPENAI_API_KEY,
    OPENAI_API_BASE,
    MODEL_NAME,
    TOP_K,
)
from vector_store import VectorStore

class RAGAgent:
    def __init__(
        self,
        model: str = MODEL_NAME,
    ):
        self.model = model
        self.client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_API_BASE)
        self.vector_store = VectorStore()

        # 定义系统提示词：设定角色和限制
        self.system_prompt = """你是一名专业的课程助教。你的任务是根据提供的课程材料（Context）回答学生的问题。

请遵循以下原则：
1. **基于事实**：严格依据提供的上下文（Context）内容回答，不要编造信息。
2. **引用来源**：在回答的关键信息后，请注明来源，格式为 [文件名, 第X页]。
3. **诚实原则**：如果上下文中没有包含回答问题所需的信息，请明确告知学生“当前课程资料中未包含此信息”，不要试图用你自己的外部知识去“猜”答案，除非学生明确要求你扩展知识。
4. **语气风格**：保持亲切、鼓励、专业的教学语气。
5. **格式清晰**：使用 Markdown 格式（如列表、粗体）使答案易读。
"""

    def retrieve_context(
        self, query: str, top_k: int = TOP_K
    ) -> Tuple[str, List[Dict]]:
        """检索并构建上下文"""
        results = self.vector_store.search(query, top_k=top_k)
        
        context_parts = []
        for i, res in enumerate(results, 1):
            meta = res["metadata"]
            # 格式化单个文档块
            source_info = f"来源: {meta['filename']}"
            if meta.get('page_number') > 0:
                source_info += f" (第 {meta['page_number']} 页/幻灯片)"
            
            context_str = f"--- 文档片段 {i} ---\n{source_info}\n内容:\n{res['content']}\n"
            context_parts.append(context_str)
            
        return "\n".join(context_parts), results

    def generate_response(
        self,
        query: str,
        context: str,
        chat_history: Optional[List[Dict]] = None,
    ) -> str:
        """生成回答"""
        messages = [{"role": "system", "content": self.system_prompt}]

        # 添加历史对话 (限制轮数，防止 Token 溢出)
        if chat_history:
            # 只取最近 4 轮对话
            recent_history = chat_history[-4:] 
            messages.extend(recent_history)

        # 构建包含上下文的用户 Prompt
        user_input_template = f"""
以下是相关的课程材料片段：
{context}

---------------------
学生问题：{query}

请根据以上材料回答问题：
"""
        messages.append({"role": "user", "content": user_input_template})

        try:
            response = self.client.chat.completions.create(
                model=self.model, 
                messages=messages, 
                temperature=0.3, # 降低温度以提高准确性
                max_tokens=1500
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"生成回答时出错: {str(e)}"

    def answer_question(
        self, query: str, chat_history: Optional[List[Dict]] = None, top_k: int = TOP_K
    ) -> str: # 修改返回类型为 str 简化处理
        """回答问题主入口"""
        # 1. 检索
        context, retrieved_docs = self.retrieve_context(query, top_k=top_k)

        # 2. 如果检索结果为空的兜底策略
        if not context:
            context = "（未检索到特别相关的课程材料，请根据通用知识谨慎回答，并告知学生资料库中无此内容）"

        # 3. 生成
        answer = self.generate_response(query, context, chat_history)

        return answer

    def chat(self) -> None:
        """控制台交互模式"""
        print("=" * 60)
        print("🤖 欢迎使用智能课程助教系统！(输入 'exit' 或 'quit' 退出)")
        print("=" * 60)

        chat_history = []

        while True:
            try:
                query = input("\n👤 学生: ").strip()

                if query.lower() in ["exit", "quit"]:
                    print("再见！")
                    break
                
                if not query:
                    continue
                
                print("Thinking...", end="\r") # 简单的等待提示
                answer = self.answer_question(query, chat_history=chat_history)

                print(f"\n🎓 助教: \n{answer}")

                # 更新历史
                chat_history.append({"role": "user", "content": query})
                chat_history.append({"role": "assistant", "content": answer})

            except KeyboardInterrupt:
                print("\n程序已终止")
                break
            except Exception as e:
                print(f"\n错误: {str(e)}")