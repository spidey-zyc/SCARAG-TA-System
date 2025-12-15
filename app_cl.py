import chainlit as cl
import textwrap
import base64
import os
import asyncio
import subprocess
import shutil
from rag_agent import RAGAgent
from chat_manager import ChatManager

# === HTML 内容定义 ===
# 注意：更新 Chainlit 后，这里可以使用 cl.Html 组件
# 我们可以恢复规范的 HTML 写法，不需要那个 "\u200B" 欺骗字符了
# 使用 textwrap.dedent 去除左侧缩进，防止 Markdown 将其识别为代码块
WELCOME_HTML = textwrap.dedent("""
<div class="mac-welcome-container">
    <div class="mac-title">SCARAG</div>
    <div class="mac-subtitle">Intelligent Course Assistant • Powered by RAG & Vision</div>
    
    <div class="mac-grid">
        <div class="mac-card">
            <span class="mac-card-icon">📂</span>
            <span class="mac-card-title">知识库检索</span>
            <span class="mac-card-desc">基于课程 PDF/PPT 资料，回答您的专业问题，并提供精确引用。</span>
        </div>
        <div class="mac-card">
            <span class="mac-card-icon">👁️</span>
            <span class="mac-card-title">视觉语义理解</span>
            <span class="mac-card-desc">拖拽上传题目截图或架构图，自动分析图片含义并进行搜索。</span>
        </div>
        <div class="mac-card">
            <span class="mac-card-icon">⚙️</span>
            <span class="mac-card-title">会话管理</span>
            <span class="mac-card-desc">支持历史记录回放、多主题切换与文件归档管理。</span>
        </div>
    </div>
</div>
""").strip()

# === 配置区 ===
BASE_DATA_PATH = "/Users/fangjie/Documents/code/RAG-programs/data"
PROCESS_SCRIPT_PATH = "/Users/fangjie/Documents/code/RAG-programs/process_data.py"

os.makedirs(BASE_DATA_PATH, exist_ok=True)

# === 辅助函数 ===
def clean_html(html_str):
    """
    移除 HTML 字符串中的换行和行首尾空格，将其压缩为一行。
    这能防止 Markdown 解析器错误地将其识别为“代码块”。
    """
    return "".join([line.strip() for line in html_str.split("\n")])

def get_themes():
    if not os.path.exists(BASE_DATA_PATH):
        return []
    themes = [d for d in os.listdir(BASE_DATA_PATH) if os.path.isdir(os.path.join(BASE_DATA_PATH, d))]
    return sorted(themes)

async def update_settings_panel(chat_manager, current_theme):
    history_chats = chat_manager.list_chats()
    chat_options = [c["filename"] for c in history_chats]
    if chat_manager.current_filename:
        current_selection = chat_manager.current_filename
    else:
        current_selection = "✨ 新建对话"
    existing_themes = get_themes()
    
    settings = await cl.ChatSettings(
        [
            cl.input_widget.Select(id="session_select", label="💬 切换/新建对话", values=["✨ 新建对话"] + chat_options, initial_value=current_selection),
            cl.input_widget.TextInput(id="rename_session", label="✏️ 重命名当前对话", initial_value=chat_manager.current_chat_name),
            cl.input_widget.Select(id="theme_select", label="📂 知识库主题 (上传目标)", values=existing_themes + ["🆕 创建新主题..."], initial_value=current_theme),
            cl.input_widget.TextInput(id="new_theme_name", label="✨ 新主题名称", initial_value=""),
            cl.input_widget.Select(id="delete_session", label="❌ 删除指定对话 (慎重)", values=["(不删除)"] + chat_options, initial_value="(不删除)"),
            cl.input_widget.Select(id="delete_theme", label="❌ 删除知识库主题 (慎重)", values=["(不删除)"] + existing_themes, initial_value="(不删除)")
        ]
    ).send()

# === 核心逻辑 ===

@cl.on_chat_start
async def start():
    cl.user_session.set("css", "/public/custom.css")
    
    agent = RAGAgent()
    chat_manager = ChatManager()
    chat_manager.create_new_chat()
    
    cl.user_session.set("agent", agent)
    cl.user_session.set("chat_manager", chat_manager)
    
    existing_themes = get_themes()
    default_theme = existing_themes[0] if existing_themes else "Default"
    cl.user_session.set("current_theme", default_theme)
    
    # === 使用 cl.Html 组件 (需要更新 chainlit) ===
    raw_html = WELCOME_HTML + f'<div style="text-align:center; color:#999; margin-top:10px; font-size:12px;">当前会话: {chat_manager.current_chat_name}</div>'
    final_html = clean_html(raw_html)
    
    # 这里的 display="inline" 会让它完美融入聊天流，不带任何边框
    welcome_msg = cl.Message(content=final_html)
    await welcome_msg.send()
    
    cl.user_session.set("welcome_msg_id", welcome_msg.id)

    await update_settings_panel(chat_manager, default_theme)

@cl.on_settings_update
async def on_settings_update(settings):
    """处理设置变更"""
    chat_manager = cl.user_session.get("chat_manager")
    
    selected_filename = settings["session_select"]
    new_name = settings["rename_session"]
    selected_theme = settings["theme_select"]
    new_theme_name_input = settings["new_theme_name"]
    delete_session_target = settings["delete_session"]
    delete_theme_target = settings["delete_theme"]

    need_refresh = False 

    # === 1. 删除对话逻辑 (已修复逻辑陷阱) ===
    if delete_session_target != "(不删除)":
        # [关键修复] 在删除动作发生前，先判断是否为当前会话
        is_deleting_current = (delete_session_target == chat_manager.current_filename)
        
        # 执行删除
        success = chat_manager.delete_chat(delete_session_target)
        
        if success:
            await cl.Message(content=f"🗑️ 已删除会话: `{delete_session_target}`").send()
            
            # [关键修复] 使用刚才保存的 is_deleting_current 变量来判断
            if is_deleting_current:
                # chat_manager 内部可能已经创建了新会话，这里我们只需要负责清理 UI
                cl.user_session.set("restored_history", []) # 清空历史变量
                
                # 重新显示欢迎页
                # 重新获取最新的 current_chat_name (因为 Manager 内部可能已经重置了)
                raw_html = WELCOME_HTML + f'<div style="text-align:center; color:#999; margin-top:10px; font-size:12px;">当前会话: {chat_manager.current_chat_name}</div>'
                final_html = clean_html(raw_html)
                
                # 发送欢迎页
                w_msg = cl.Message(content=final_html)
                await w_msg.send()
                cl.user_session.set("welcome_msg_id", w_msg.id)
                
        else:
            await cl.Message(content=f"❌ 删除失败: `{delete_session_target}` (可能文件已被占用或不存在)").send()
            
        need_refresh = True

    # === 2. 删除主题逻辑 ===
    if delete_theme_target != "(不删除)":
        theme_path = os.path.join(BASE_DATA_PATH, delete_theme_target)
        try:
            if os.path.exists(theme_path):
                shutil.rmtree(theme_path)
                await cl.Message(content=f"🗑️ 已删除主题: `{delete_theme_target}`").send()
                
                current_theme = cl.user_session.get("current_theme")
                if delete_theme_target == current_theme:
                    remaining = get_themes()
                    fallback = remaining[0] if remaining else "Default"
                    cl.user_session.set("current_theme", fallback)
                    await cl.Message(content=f"🔄 当前主题已切换为: `{fallback}`").send()
            else:
                await cl.Message(content=f"❌ 主题不存在: {theme_path}").send()
        except Exception as e:
            await cl.Message(content=f"❌ 删除出错: {str(e)}").send()
        need_refresh = True

    # 如果发生了删除操作，刷新面板后直接返回，防止后续逻辑干扰
    if need_refresh:
        # 获取最新的主题和管理器状态
        await update_settings_panel(chat_manager, cl.user_session.get("current_theme"))
        return

    # === 3. 切换会话 ===
    # 只有在没有执行删除时才运行
    if selected_filename == "✨ 新建对话":
        # 只有当前不是新建状态时才执行新建
        # 注意：chat_manager.current_filename 可能是 None
        if chat_manager.current_filename is not None and not chat_manager.current_filename.startswith("New Chat"):
            chat_manager.create_new_chat()
            cl.user_session.set("restored_history", [])
            
            raw_html = WELCOME_HTML + f'<div style="text-align:center; color:#999; margin-top:10px; font-size:12px;">当前会话: {chat_manager.current_chat_name}</div>'
            final_html = clean_html(raw_html)
            
            w_msg = cl.Message(content=final_html)
            await w_msg.send()
            cl.user_session.set("welcome_msg_id", w_msg.id)
            
    elif selected_filename != chat_manager.current_filename:
        # 移除欢迎页
        welcome_id = cl.user_session.get("welcome_msg_id")
        if welcome_id:
            try: await cl.Message(id=welcome_id).remove()
            except: pass
            cl.user_session.set("welcome_msg_id", None)

        messages = chat_manager.load_chat_by_filename(selected_filename)
        if messages is not None: 
            restored_history = [{"role": m["role"], "content": m["content"]} for m in messages]
            cl.user_session.set("restored_history", restored_history)
            
            await cl.Message(content=f"--- 🔄 已加载会话: **{chat_manager.current_chat_name}** ---").send()
            for m in messages:
                author = "User" if m["role"] == "user" else "Assistant"
                await cl.Message(content=m["content"], author=author).send()
            await cl.Message(content="--- ✅ 历史加载完毕 ---").send()

    # === 4. 重命名 ===
    if new_name and new_name != chat_manager.current_chat_name:
        success = chat_manager.rename_chat(new_name)
        if success:
            await cl.Message(content=f"✅ 重命名成功: `{chat_manager.current_filename}`").send()
            await update_settings_panel(chat_manager, current_theme)
            return

    # === 5. 主题切换/新建 ===
    if selected_theme == "🆕 创建新主题...":
        if new_theme_name_input and new_theme_name_input.strip():
            current_theme = new_theme_name_input.strip()
            new_theme_path = os.path.join(BASE_DATA_PATH, current_theme)
            os.makedirs(new_theme_path, exist_ok=True)
            await cl.Message(content=f"📂 已创建新主题: **{current_theme}**").send()
        else:
            current_theme = "Default"
    else:
        current_theme = selected_theme
    
    cl.user_session.set("current_theme", current_theme)
    await update_settings_panel(chat_manager, current_theme)

@cl.on_message
async def main(message: cl.Message):
    # 隐藏欢迎页
    welcome_id = cl.user_session.get("welcome_msg_id")
    if welcome_id:
        try:
            await cl.Message(id=welcome_id).remove()
            cl.user_session.set("welcome_msg_id", None)
        except Exception: pass

    # ... (保持原有的 main 逻辑不变) ...
    agent = cl.user_session.get("agent")
    chat_manager = cl.user_session.get("chat_manager")
    current_theme = cl.user_session.get("current_theme")
    chat_history = cl.user_session.get("restored_history", [])
    
    image_base64 = None
    image_analysis_content = ""
    docs_uploaded = False

    if message.elements:
        doc_files = [el for el in message.elements if "image" not in el.mime]
        if doc_files:
            theme_path = os.path.join(BASE_DATA_PATH, current_theme)
            os.makedirs(theme_path, exist_ok=True)
            processing_msg = cl.Message(content=f"📥 归档到 `{current_theme}`...")
            await processing_msg.send()

            for doc in doc_files:
                dest_path = os.path.join(theme_path, doc.name)
                with open(doc.path, "rb") as f_src:
                    with open(dest_path, "wb") as f_dst:
                        f_dst.write(f_src.read())
            
            try:
                cmd = ["python", PROCESS_SCRIPT_PATH, "--theme", current_theme, "--incremental"]
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    await processing_msg.update(content=f"✅ 主题 `{current_theme}` 更新完成！")
                else:
                    await processing_msg.update(content=f"❌ 失败:\n{result.stderr}")
            except Exception as e:
                await processing_msg.update(content=f"❌ 错误: {str(e)}")
            docs_uploaded = True

        for element in message.elements:
            if "image" in element.mime:
                try:
                    with open(element.path, "rb") as image_file:
                        image_base64 = base64.b64encode(image_file.read()).decode('utf-8')
                    break 
                except: pass

    if docs_uploaded and not message.content:
        return

    chat_manager.append_message("user", message.content)
    chat_history.append({"role": "user", "content": message.content})

    if image_base64:
        async with cl.Step(name="👁️ 视觉语义分析", type="tool") as step:
            step.input = "分析中..."
            analysis_result = await cl.make_async(agent.understand_image)(image_base64)
            step.output = analysis_result
            image_analysis_content = analysis_result

    final_query = message.content
    if image_analysis_content:
        final_query += f"\n详细背景：{image_analysis_content}"

    async with cl.Step(name="SCARAG 思考中...", type="tool") as step:
        step.input = final_query
        context_str, results = await cl.make_async(agent.retrieve_context)(final_query)
        step.output = f"检索到 {len(results)} 条资料"
        
        detail_text = ""
        for i, res in enumerate(results):
            detail_text += f"### 来源 {i+1}: {res['metadata']['filename']}\n"
            if res['metadata'].get('page_number'):
                detail_text += f"*(P{res['metadata']['page_number']})*\n"
            detail_text += f"```text\n{res['content'][:200]}...\n```\n\n"
        step.elements = [cl.Text(name="检索详情", content=detail_text, display="inline")]

    source_elements = []
    for idx, doc in enumerate(results):
        meta = doc['metadata']
        source_name = f"参考来源 {idx+1}"
        content_preview = f"文件: {meta.get('filename')}\n页码: {meta.get('page_number', 'N/A')}\n\n{doc['content']}"
        element = cl.Text(name=source_name, content=content_preview, display="side")
        source_elements.append(element)

    final_answer_msg = cl.Message(content="")
    await final_answer_msg.send()

    full_answer = await cl.make_async(agent.generate_response)(
        query=message.content,
        context=context_str,
        chat_history=chat_history,
        image_base64=image_base64
    )

    for char in full_answer:
        await final_answer_msg.stream_token(char)
        await asyncio.sleep(0.002)
    
    final_answer_msg.elements = source_elements
    await final_answer_msg.update()

    chat_manager.append_message("assistant", full_answer)
    chat_history.append({"role": "assistant", "content": full_answer})
    cl.user_session.set("restored_history", chat_history)