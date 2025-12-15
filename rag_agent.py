# rag_agent.py
from typing import List, Dict, Optional, Tuple
from openai import OpenAI
from config import (
    OPENAI_API_KEY,
    OPENAI_API_BASE,
    TEXT_MODEL_NAME,   # 导入文本模型名
    VISION_API_KEY,    # 导入视觉Key
    VISION_API_BASE,   # 导入视觉Base URL
    VISION_MODEL_NAME, # 导入视觉模型名
    TOP_K,
)
from vector_store import VectorStore

class RAGAgent:
    def __init__(self):
        # 1. 初始化文本专用客户端 (使用原 Key)
        # 用于: Embedding, 纯文本问答
        self.text_client = OpenAI(
            api_key=OPENAI_API_KEY, 
            base_url=OPENAI_API_BASE
        )
        self.text_model = TEXT_MODEL_NAME

        # 2. 初始化视觉专用客户端 (使用新 Key)
        # 用于: 包含图片的问答
        self.vision_client = OpenAI(
            api_key=VISION_API_KEY, 
            base_url=VISION_API_BASE
        )
        self.vision_model = VISION_MODEL_NAME

        # 初始化向量库
        self.vector_store = VectorStore()

        self.system_prompt = """你是一名专业的课程助教。你的任务是根据提供的课程材料（Context）回答学生的问题。

请遵循以下原则：
1. **基于事实**：严格依据提供的上下文（Context）内容回答，不要编造信息。
2. **引用来源**：在回答的关键信息后，请注明来源，格式为 [文件名, 第X页]。
3. **诚实原则**：如果上下文中没有包含回答问题所需的信息，请明确告知学生“当前课程资料中未包含此信息”，不要试图用你自己的外部知识去“猜”答案，除非学生明确要求你扩展知识。
4. **语气风格**：保持亲切、鼓励、专业的教学语气。
5. **格式清晰**：使用 Markdown 格式（如列表、粗体）使答案易读。
"""

    # rag_agent.py 中修改或添加这个方法

    def understand_image(self, image_base64: str) -> str:
        """
        升级版视觉分析：
        - 如果是题目/文档：提取文字。
        - 如果是图表/实物：生成详细的语义描述。
        """
        print("📸 [Agent] 正在进行深度视觉理解与描述...")
        
        # 核心提示词：指导模型根据图片类型采取不同策略
        vision_analysis_prompt = """
你是一个辅助检索系统。请详细分析这张图片，目的是为了生成一段**搜索关键词**，以便在课程资料库中找到相关内容。

请按照以下逻辑处理：
1. **如果是包含大量文字的图片（如题目、幻灯片、文档截图）**：
   - 请直接、完整地提取出图片中的所有文字。不要遗漏题目细节。

2. **如果是图表、架构图、流程图或无文字图片**：
   - 请详细描述图片的**视觉内容**、**核心概念**、**组件名称**以及它们之间的**逻辑关系**。
   - 例如：“这是一个二叉树的结构图，根节点是A，左子节点是B...”或“这是一张展示TCP三次握手流程的时序图”。

**要求**：直接输出分析结果（文字或描述），不要包含“这是一张图片”之类的废话。
"""

        try:
            response = self.vision_client.chat.completions.create(
                model=self.vision_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": vision_analysis_prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}
                            }
                        ]
                    }
                ],
                max_tokens=1000 # 稍微调大一点，以容纳详细描述
            )
            analysis_result = response.choices[0].message.content
            print(f"👁️ [Agent] 视觉分析结果: {analysis_result[:50]}...")
            return analysis_result
        except Exception as e:
            print(f"❌ 视觉分析失败: {e}")
            return ""

    def retrieve_context(
        self, query: str, top_k: int = TOP_K
    ) -> Tuple[str, List[Dict]]:
        """检索并构建上下文"""
        results = self.vector_store.search(query, top_k=top_k)
        
        context_parts = []
        for i, res in enumerate(results, 1):
            meta = res["metadata"]
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
        image_base64: Optional[str] = None  # 支持接收图片
    ) -> str:
        """生成回答：自动路由到不同的模型"""
        
        # 1. 基础消息构建
        messages = [{"role": "system", "content": self.system_prompt}]

        if chat_history:
            messages.extend(chat_history[-4:])

        # 2. 构造用户 Prompt 模板
        user_input_template = f"""
以下是相关的课程材料片段：
{context}

---------------------
学生问题：{query}

请根据以上材料（如果有图片，请结合图片内容）回答问题：
"""

        # 3. 🔀 核心路由逻辑
        if image_base64:
            # === 场景 A: 有图片，调用 Vision Model ===
            # print(f"📸 [Agent] 检测到图片输入，切换至视觉模型: {self.vision_model}")
            client = self.vision_client
            model_to_use = self.vision_model
            
            # 构造多模态消息 (List格式)
            content_payload = [
                {"type": "text", "text": user_input_template},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_base64}"
                    }
                }
            ]
            messages.append({"role": "user", "content": content_payload})
            
        else:
            # === 场景 B: 纯文本，调用 Text Model ===
            # print(f"📝 [Agent] 纯文本输入，使用文本模型: {self.text_model}")
            client = self.text_client
            model_to_use = self.text_model
            
            # 构造普通文本消息 (String格式)
            messages.append({"role": "user", "content": user_input_template})

        try:
            response = client.chat.completions.create(
                model=model_to_use, 
                messages=messages, 
                temperature=0.3, 
                max_tokens=2000
            )
            return response.choices[0].message.content
        except Exception as e:
            error_msg = str(e)
            print(f"❌ 模型调用出错 ({model_to_use}): {error_msg}")
            
            # 自动降级保护：如果 Vision 模型挂了且是纯文本请求，尝试用 Text 模型
            if image_base64 and "text" in str(model_to_use): 
                 return f"视觉模型调用失败: {error_msg}。"
            
            return f"生成回答时出错: {error_msg}"

    def answer_question(
        self, query: str, chat_history: Optional[List[Dict]] = None, top_k: int = TOP_K
    ) -> str:
        """回答问题主入口 (主要供控制台或不带图的UI使用)"""
        # 1. 检索
        context, retrieved_docs = self.retrieve_context(query, top_k=top_k)

        # 2. 如果检索结果为空的兜底策略
        if not context:
            context = "（未检索到特别相关的课程材料，请根据通用知识谨慎回答，并告知学生资料库中无此内容）"

        # 3. 生成 (不传入图片参数，自动使用文本模型)
        answer = self.generate_response(query, context, chat_history)

        return answer

    def chat(self) -> None:
        """控制台交互模式 (纯文本)"""
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
                
                # 调用 answer_question，它会调用 generate_response(image_base64=None)
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