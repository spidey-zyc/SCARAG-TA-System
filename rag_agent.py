# rag_agent.py
import re
from typing import List, Dict, Optional, Tuple
from openai import OpenAI
from config import (
    OPENAI_API_KEY,
    OPENAI_API_BASE,
    TEXT_MODEL_NAME,   # 文本模型
    VISION_API_KEY,    # 视觉Key
    VISION_API_BASE,   # 视觉Base
    VISION_MODEL_NAME, # 视觉模型
    TOP_K,
)
from vector_store import VectorStore

class RAGAgent:
    def __init__(self):
        # 1. 初始化文本专用客户端 (用于: Embedding, 纯文本问答, 意图重写, Rerank)
        self.text_client = OpenAI(
            api_key=OPENAI_API_KEY, 
            base_url=OPENAI_API_BASE
        )
        self.text_model = TEXT_MODEL_NAME

        # 2. 初始化视觉专用客户端 (用于: 图片分析)
        self.vision_client = OpenAI(
            api_key=VISION_API_KEY, 
            base_url=VISION_API_BASE
        )
        self.vision_model = VISION_MODEL_NAME

        # 初始化向量库
        self.vector_store = VectorStore()

        # 🚀 升级点 3: 思维链 (CoT) System Prompt
        self.system_prompt = """你是一名专业的计算机科学课程助教。你的目标是“教会学生思考”，并善于利用图文结合的方式进行讲解。

请严格遵循以下流程：
1. **意图判断**：如果问题模糊，先反问；如果清晰，继续。
2. **图文讲解 (核心)**：
   - 在提供的 Context 中，如果看到 **【🔴 此处关联了图片】** 的标记，这代表屏幕上会显示一张相关图片。
   - 你**必须**在回答中明确引用这张图片。例如说：“**请看下图**，我们可以看到...”、“**如图所示**，这个结构...”
   - **严禁**忽略图片，严禁只讲文字。必须结合图片里的视觉信息（如“图中红色的节点”、“左边的流程”）进行解释。
3. **知识整合**：基于 Context 提取事实，标注来源 `[文件名, 第X页]`。
4. **巩固测试**：讲解结束后，必须出一道练习题并附带解析。

**语气要求**：亲切、循循善诱。
"""

    def understand_image(self, image_base64: str) -> str:
        """
        [保留原有功能] 视觉分析
        """
        print("📸 [Agent] 正在进行深度视觉理解与描述...")
        vision_analysis_prompt = """
你是一个辅助检索系统。请详细分析这张图片，生成搜索关键词。
1. 若包含文字（题目、文档）：请完整提取文字。
2. 若是图表/架构图：请详细描述视觉内容、核心概念及组件关系。
要求：直接输出分析结果。
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
                max_tokens=1000
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"❌ 视觉分析失败: {e}")
            return ""

    def rewrite_query(self, query: str, chat_history: List[Dict]) -> str:
        """
        🚀 升级点 1: 多轮对话意图重写
        解决 '它是什么' 这种指代不明的问题
        """
        if not chat_history:
            return query

        # 取最近两轮对话作为参考
        recent_history = chat_history[-4:]
        
        rewrite_prompt = f"""
你是一个查询重写助手。基于以下对话历史，将用户的最新问题重写为一个独立、语义完整的搜索语句。
重点：替换代词（如"它"、"这个"）为具体名词。

历史对话：
{recent_history}

用户最新问题：{query}

请直接输出重写后的问题，不要包含任何解释。
"""
        try:
            # print("🤔 正在理解上下文...", end="\r")
            response = self.text_client.chat.completions.create(
                model=self.text_model,
                messages=[{"role": "user", "content": rewrite_prompt}],
                temperature=0.1
            )
            new_query = response.choices[0].message.content.strip()
            print(f"🔄 [Agent] 问题重写: '{query}' -> '{new_query}'")
            return new_query
        except Exception as e:
            print(f"⚠️ 重写失败: {e}")
            return query

    def rerank_results(self, query: str, results: List[Dict], top_k: int) -> List[Dict]:
        """
        🚀 升级点 2: 检索结果重排序 (LLM Rerank)
        让大模型从初筛结果中挑出最相关的
        """
        if not results:
            return []
            
        print(f"⚖️ [Agent] 正在对 {len(results)} 条检索结果进行精选...")
        
        # 构造给 LLM 看的候选列表 (只截取前200字节省Token)
        candidates_str = ""
        for i, res in enumerate(results):
            candidates_str += f"[ID:{i}] 内容: {res['content'][:200]}...\n\n"

        rerank_prompt = f"""
请针对问题：“{query}”
从以下候选片段中，选出最能回答该问题的 {top_k} 个片段的ID。
要求：只输出ID列表，格式如 [0, 2, 5]。不要输出其他文字。

{candidates_str}
"""
        try:
            response = self.text_client.chat.completions.create(
                model=self.text_model,
                messages=[{"role": "user", "content": rerank_prompt}],
                temperature=0
            )
            content = response.choices[0].message.content
            # 提取数字 ID
            selected_ids = [int(d) for d in re.findall(r'\d+', content)]
            
            # 根据 ID 获取对应的文档
            final_results = [results[i] for i in selected_ids if i < len(results)]
            
            # 兜底：如果筛选结果为空，回退到默认前K个
            if not final_results:
                return results[:top_k]
                
            return final_results
        except Exception as e:
            print(f"⚠️ 重排序失败，使用默认排序: {e}")
            return results[:top_k]

    def retrieve_context(
        self, query: str, top_k: int = TOP_K
    ) -> Tuple[str, List[Dict]]:
        """检索并构建上下文 (包含 Rerank 逻辑)"""
        
        # 1. 扩大检索范围 (检索 2 倍数量，用于筛选)
        initial_k = top_k * 2
        initial_results = self.vector_store.search(query, top_k=initial_k)
        
        # 2. 智能重排序
        final_results = self.rerank_results(query, initial_results, top_k)
        
        # # 3. 格式化上下文
        # context_parts = []
        # for i, res in enumerate(final_results, 1):
        #     meta = res["metadata"]
        #     source_info = f"来源: {meta['filename']}"
        #     if meta.get('page_number') > 0:
        #         source_info += f" (第 {meta['page_number']} 页/幻灯片)"
            
        #     context_str = f"--- 文档片段 {i} ---\n{source_info}\n内容:\n{res['content']}\n"
        #     context_parts.append(context_str)
            
        # return "\n".join(context_parts), final_results
    
        # 3. 格式化上下文 (🚀 关键修改在这里)
        context_parts = []
        for i, res in enumerate(final_results, 1):
            meta = res["metadata"]
            source_info = f"来源: {meta['filename']}"
            if meta.get('page_number') > 0:
                source_info += f" (第 {meta['page_number']} 页/幻灯片)"
            
            # 👇👇👇 新增逻辑：检查图片路径 👇👇👇
            image_hint = ""
            if meta.get("image_path") and str(meta.get("image_path")).strip() != "":
                image_hint = "\n【🔴 此处关联了图片】(请务必结合图片内容，使用'如图所示'等话术进行讲解)"
            
            # 将提示语拼接到 context 中，让 LLM 看到
            context_str = f"--- 文档片段 {i} ---\n{source_info}\n内容:\n{res['content']}{image_hint}\n"
            context_parts.append(context_str)
            
        return "\n".join(context_parts), final_results

    def generate_response(
        self,
        query: str,
        context: str,
        chat_history: Optional[List[Dict]] = None,
        image_base64: Optional[str] = None
    ) -> str:
        """生成回答：支持思维链 + 多模态"""
        
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

        # 3. 路由逻辑 (有图用 Vision 模型，无图用 Text 模型)
        if image_base64:
            client = self.vision_client
            model_to_use = self.vision_model
            # 构造多模态消息
            content_payload = [
                {"type": "text", "text": user_input_template},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
            ]
            messages.append({"role": "user", "content": content_payload})
        else:
            client = self.text_client
            model_to_use = self.text_model
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
            # 降级保护：如果 vision 模型挂了，尝试用 text 模型回复文字部分
            if image_base64 and "text" in str(model_to_use): 
                 return f"视觉模型调用失败: {error_msg}。"
            return f"生成回答时出错: {error_msg}"

    def answer_question(
        self, query: str, chat_history: Optional[List[Dict]] = None, top_k: int = TOP_K
    ) -> str:
        """回答问题主入口"""
        
        # 1. 意图重写 (Query Rewrite)
        search_query = query
        if chat_history:
            search_query = self.rewrite_query(query, chat_history)

        # 2. 检索 (包含 Rerank)
        context, retrieved_docs = self.retrieve_context(search_query, top_k=top_k)

        # 兜底策略
        if not context:
            context = "（未检索到特别相关的课程材料，请根据通用知识谨慎回答，并告知学生资料库中无此内容）"

        # 3. 生成回答
        answer = self.generate_response(query, context, chat_history)

        return answer

    def chat(self) -> None:
        """控制台交互模式"""
        print("=" * 60)
        print("🤖 欢迎使用智能课程助教系统 (Pro Max版)！(输入 'exit' 退出)")
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
                
                print("Thinking...", end="\r") 
                
                # 命令行模式不支持传图片，所以 image_base64=None
                # answer_question 内部会自动调用 rewrite -> retrieve(rerank) -> generate
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