import chainlit as cl
import textwrap
import base64
import os
import asyncio
import subprocess
import shutil
from rag_agent import RAGAgent
from chat_manager import ChatManager
import urllib.parse
import re



# [新增] 挂载静态目录，让前端能访问 static/images 下的图片
from chainlit.server import app
from fastapi.staticfiles import StaticFiles
# 1. 导入 config 中定义好的跨平台路径
from config import STATIC_DIR 



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
BASE_DATA_PATH = os.path.join(".", "data")
PROCESS_SCRIPT_PATH = os.path.join(".", "process_data.py")

os.makedirs(BASE_DATA_PATH, exist_ok=True)

# 2. 确保目录存在 (使用导入的路径变量)
os.makedirs(STATIC_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")

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

def track_msg_id(msg_id):
    """记录消息ID，以便后续清理"""
    ids = cl.user_session.get("msg_ids", [])
    ids.append(msg_id)
    cl.user_session.set("msg_ids", ids)

async def clear_screen():
    """清除屏幕上所有已记录的消息"""
    ids = cl.user_session.get("msg_ids", [])
    for mid in ids:
        try:
            await cl.Message(content="", id=mid).remove()
        except Exception:
            pass # 忽略已删除的消息
    cl.user_session.set("msg_ids", []) # 清空记录

async def update_settings_panel(chat_manager, current_theme):
    history_chats = chat_manager.list_chats()
    chat_options = [c["filename"] for c in history_chats]
    if chat_manager.current_filename:
        current_selection = chat_manager.current_filename
    else:
        current_selection = "✨ 新建对话"

    if current_selection != "✨ 新建对话" and current_selection not in chat_options:
        chat_options.insert(0, current_selection)
    
    existing_themes = get_themes()
    
    settings = await cl.ChatSettings(
        [
            cl.input_widget.Select(
                id="session_select", 
                label="💬 切换/新建对话", 
                # 这里使用的是修正后的 chat_options
                values=["✨ 新建对话"] + chat_options, 
                initial_value=current_selection
            ),
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
    
    # 1. 初始化列表，用于追踪屏幕上的消息ID
    cl.user_session.set("msg_ids", [])
    
    
    chat_manager = ChatManager()
    
    # 【关键修改】不立即创建新会话，设为 None
    chat_manager.current_filename = None
    chat_manager.current_chat_name = "New Chat"
    
    cl.user_session.set("chat_manager", chat_manager)
    
    existing_themes = get_themes()
    default_theme = existing_themes[0] if existing_themes else "Default"
    cl.user_session.set("current_theme", default_theme)

    agent = RAGAgent(default_theme)
    cl.user_session.set("agent", agent)
    
    # 2. 显示欢迎页
    raw_html = WELCOME_HTML 
    final_html = clean_html(raw_html)
    
    welcome_msg = cl.Message(content=final_html)
    await welcome_msg.send()
    
    # 记录 ID 并在 Session 中保存
    track_msg_id(welcome_msg.id)
    cl.user_session.set("welcome_msg_id", welcome_msg.id)

    # 3. 刷新侧边栏
    await update_settings_panel(chat_manager, default_theme)

@cl.on_settings_update
async def on_settings_update(settings):
    """处理设置变更"""
    agent = cl.user_session.get("agent") 
    chat_manager = cl.user_session.get("chat_manager")
    current_theme = cl.user_session.get("current_theme")
    
    # 获取前端传来的值
    selected_filename = settings["session_select"]
    new_name = settings["rename_session"]
    selected_theme = settings["theme_select"]
    new_theme_name_input = settings["new_theme_name"]
    delete_session_target = settings["delete_session"]
    delete_theme_target = settings["delete_theme"]

    # 标志位：是否已经刷新过面板（避免重复刷新）
    panel_refreshed = False 

    # ==========================================
    # 1. 删除逻辑 (保持不变，但注意 return)
    # ==========================================
    if delete_session_target != "(不删除)":
        is_deleting_current = (delete_session_target == chat_manager.current_filename)
        success = chat_manager.delete_chat(delete_session_target)
        
        if success:
            await cl.Message(content=f"🗑️ 已删除会话: `{delete_session_target}`").send()
            if is_deleting_current:
                cl.user_session.set("restored_history", [])
                # 显示欢迎页
                raw_html = WELCOME_HTML + f'<div style="text-align:center; color:#999; margin-top:10px; font-size:12px;">当前会话: {chat_manager.current_chat_name}</div>'
                final_html = clean_html(raw_html)
                w_msg = cl.Message(content=final_html)
                await w_msg.send()
                cl.user_session.set("welcome_msg_id", w_msg.id)
        else:
            await cl.Message(content=f"❌ 删除失败: `{delete_session_target}`").send()
            
        # 删除操作必须强制刷新
        await update_settings_panel(chat_manager, cl.user_session.get("current_theme"))
        return # 强制结束，防止后续逻辑干扰

    if delete_theme_target != "(不删除)":
        # ... (主题删除逻辑保持不变) ...
        # 为了节省篇幅，这里假设主题删除逻辑和原来一样
        # ... 
        await update_settings_panel(chat_manager, cl.user_session.get("current_theme"))
        return

    # ==========================================
    # 2. 切换/新建会话逻辑 (核心修复)
    # ==========================================
    
    if selected_filename != chat_manager.current_filename:
        
        # A. 【关键步骤】先清空屏幕！
        await clear_screen()
        
        # B. 处理“新建对话”
        if selected_filename == "✨ 新建对话":
            # 设为 None，等待用户发第一句话时再创建文件
            chat_manager.current_filename = None
            chat_manager.current_chat_name = "New Chat"
            cl.user_session.set("restored_history", [])
            
            # 重新显示欢迎页
            raw_html = WELCOME_HTML
            final_html = clean_html(raw_html)
            w_msg = cl.Message(content=final_html)
            await w_msg.send()
            
            # 记录欢迎页ID
            track_msg_id(w_msg.id)
            cl.user_session.set("welcome_msg_id", w_msg.id)
            
        # C. 处理“加载历史会话”
        else:
            chat_manager.current_filename = selected_filename
            messages = chat_manager.load_chat_by_filename(selected_filename)
            
            if messages is not None: 
                restored_history = [{"role": m["role"], "content": m["content"]} for m in messages]
                cl.user_session.set("restored_history", restored_history)
                
                # 发送提示
                info_msg = await cl.Message(content=f"--- 🔄 已加载会话: **{chat_manager.current_chat_name}** ---").send()
                track_msg_id(info_msg.id) # 记录ID
                
                # 回放历史消息
                for m in messages:
                    author = "User" if m["role"] == "user" else "Assistant"
                    # 发送并记录ID
                    msg_obj = await cl.Message(content=m["content"], author=author).send()
                    track_msg_id(msg_obj.id)
                
                end_msg = await cl.Message(content="--- ✅ 历史加载完毕 ---").send()
                track_msg_id(end_msg.id)

        # 刷新面板，锁死选项
        await update_settings_panel(chat_manager, current_theme)

    # ==========================================
    # 3. 重命名逻辑
    # ==========================================
    if new_name and new_name != chat_manager.current_chat_name:
        success = chat_manager.rename_chat(new_name)
        if success:
            await cl.Message(content=f"✅ 重命名成功: `{chat_manager.current_filename}`").send()
            # 重命名肯定要刷新
            await update_settings_panel(chat_manager, cl.user_session.get("current_theme"))
            return

    # ==========================================
    # 4. 主题切换/新建逻辑
    # ==========================================
    # 只有当上面没有发生会话切换导致的刷新时，才去检查主题变更
    # 否则面板已经被刷新过了，不需要重复做
    if not panel_refreshed:
        target_theme = selected_theme
        
        # 处理新建主题
        if selected_theme == "🆕 创建新主题...":
            if new_theme_name_input and new_theme_name_input.strip():
                new_theme_name = new_theme_name_input.strip()
                if not re.match(r'^[a-zA-Z0-9_-]+$', new_theme_name): # 修复变量名 bug
                     await cl.Message(content=f"⚠️ 警告：主题名建议仅使用英文和数字。").send()
                target_theme = new_theme_name 
                os.makedirs(os.path.join(BASE_DATA_PATH, target_theme), exist_ok=True)
                await cl.Message(content=f"📂 已创建新主题: **{target_theme}**").send()
            else:
                target_theme = "Default"

        if target_theme == "🆕 创建新主题...":
            target_theme = "Default"

        # 执行切换
        if target_theme != cl.user_session.get("current_theme"):
            cl.user_session.set("current_theme", target_theme)
            agent.reload_knowledge_base(target_theme)
            await cl.Message(content=f"🔄 知识库已切换为: **{target_theme}**").send()
            # 主题变了，必须刷新
            await update_settings_panel(chat_manager, target_theme)

@cl.on_message
async def main(message: cl.Message):
    # 隐藏欢迎页
    welcome_id = cl.user_session.get("welcome_msg_id")
    if welcome_id:
        try:
            # 关键修改：添加 content="" 参数
            await cl.Message(content="", id=welcome_id).remove()
            cl.user_session.set("welcome_msg_id", None)
        except Exception as e:
            # 打印错误但不阻断流程
            print(f"DEBUG: 移除欢迎页失败: {e}")
            cl.user_session.set("welcome_msg_id", None)

    # ... (保持原有的 main 逻辑不变) ...
    agent = cl.user_session.get("agent")
    chat_manager = cl.user_session.get("chat_manager")
    current_theme = cl.user_session.get("current_theme")
    chat_history = cl.user_session.get("restored_history", [])

    if chat_manager.current_filename is None:
        # 用户发了第一句话，现在才真正创建文件
        chat_manager.create_new_chat()
        
        # 顺便更新一下侧边栏，让下拉框从 "✨ 新建对话" 跳变到新生成的文件名
        # 这样用户就知道会话已经保存了
        await update_settings_panel(chat_manager, current_theme)
    
    image_base64 = None
    image_analysis_content = ""
    docs_uploaded = False

    if message.elements:
        doc_files = [el for el in message.elements if "image" not in el.mime]
        if doc_files:
            theme_path = os.path.join(BASE_DATA_PATH, current_theme)
            os.makedirs(theme_path, exist_ok=True)
            
            # 保存文件
            processing_msg = cl.Message(content=f"📥 文件已保存，正在快速处理文本...")
            await processing_msg.send()

            for doc in doc_files:
                dest_path = os.path.join(theme_path, doc.name)
                with open(doc.path, "rb") as f_src:
                    with open(dest_path, "wb") as f_dst:
                        f_dst.write(f_src.read())
            
            # ==================================================
            # 阶段 1: 快速文本模式 (阻塞等待，用户需等待几秒)
            # ==================================================
            # 注意：加上 --text_only 参数
            cmd_text = ["python", PROCESS_SCRIPT_PATH, "--theme", current_theme, "--incremental", "--text_only"]
            
            # 使用同步方法的包装器
            def run_text_sync():
                return subprocess.run(cmd_text, capture_output=True, text=True)
            
            # 使用 cl.make_async 将其转为非阻塞调用，但这里我们要 await 结果
            result_text = await cl.make_async(run_text_sync)()

            if result_text.returncode == 0:
                # 文本成功！更新UI告诉用户可以开始玩了
                processing_msg.content = f"✅ **文本处理已完成！**\n(图片分析任务已在后台启动，您可以先针对文本内容提问...)"
                await processing_msg.update()
                
                # ==================================================
                # 阶段 2: 图片/OCR 模式 (Fire-and-Forget 后台任务)
                # ==================================================
                async def run_background_images():
                    # 必须加 --incremental (防止清空刚才的文本) 和 --image_only
                    cmd_img = ["python", PROCESS_SCRIPT_PATH, "--theme", current_theme, "--incremental", "--image_only"]
                    
                    print(f"DEBUG: 启动后台图片处理: {current_theme}")
                    
                    def run_img_sync():
                        return subprocess.run(cmd_img, capture_output=True, text=True)
                    
                    # 异步运行，不等待
                    res = await cl.make_async(run_img_sync)()
                    
                    if res.returncode == 0:
                        print(f"DEBUG: 后台图片处理完成: {current_theme}")
                    else:
                        print(f"DEBUG: 后台图片处理失败: {res.stderr}")

                # 关键：创建一个后台任务，不要 await 它！
                asyncio.create_task(run_background_images())
                
            else:
                # 文本处理都失败了，报错
                processing_msg.content = f"❌ 文本处理失败:\n{result_text.stderr}"
                await processing_msg.update()
            
            docs_uploaded = True

        for element in message.elements:
            if "image" in element.mime:
                try:
                    with open(element.path, "rb") as image_file:
                        image_base64 = base64.b64encode(image_file.read()).decode('utf-8')
                    break 
                except: pass

    if docs_uploaded and not message.content:
        await cl.Message(content="✅ 文件已接收，请开始提问。").send()
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

    # async with cl.Step(name="SCARAG 思考中...", type="tool") as step:
    #     step.input = final_query
    #     context_str, results = await cl.make_async(agent.retrieve_context)(final_query)              

        
    #     # === 核心修改：可视化检索结果 ===
    #     elements = []
    #     detail_text = ""
        
    #     for i, res in enumerate(results):
    #         meta = res['metadata']
    #         score = res.get('score', 0)
            
    #         # 构建文本详情
    #         detail_text += f"### 来源 {i+1}: {meta['filename']}\n"
    #         detail_text += f"```text\n{res['content'][:200]}...\n```\n"
            
    #         # 检查是否有图片路径
    #         img_path = meta.get("image_path")
    #         if img_path and img_path.strip():
    #             # img_path 是类似 "./static/images/theme/xxx.png"
    #             # Chainlit Image 组件可以直接读取本地路径
                
    #             # 为了在 Step 中展示，我们使用 cl.Image
    #             # 注意 name 必须唯一
    #             image_name = f"image_source_{i}"
    #             try:
    #                 # 将图片添加到 elements
    #                 elements.append(
    #                     cl.Image(path=img_path, name=image_name, display="inline")
    #                 )
    #                 detail_text += f"**[已加载关联图片: {image_name}]**\n\n"
    #             except Exception as e:
    #                 print(f"加载图片失败: {e}")
    #         else:
    #             detail_text += "\n"


    async with cl.Step(name="SCARAG 思考中...", type="tool") as step:
        step.input = final_query
        context_str, results = await cl.make_async(agent.retrieve_context)(final_query)              

        # === 核心修复：可视化检索结果 ===
        elements = []
        detail_text = ""
        seen_images = set() # 防止重复显示
        
        for i, res in enumerate(results):
            meta = res['metadata']
            
            # 1. 拼接文本详情
            detail_text += f"### 来源 {i+1}: {meta['filename']}\n"
            detail_text += f"```text\n{res['content'][:200]}...\n```\n"
            
            # 2. 简单的图片处理逻辑 (向 v2 学习，直接用 path)
            raw_img_path = meta.get("image_path")
            
            # 判断条件：前5名 + 路径存在 + 没显示过 + 物理文件确实存在
            if (i < 5 
                and raw_img_path 
                and str(raw_img_path).strip() 
                and raw_img_path not in seen_images
                and os.path.exists(raw_img_path)): # 关键：检查文件是否存在
                
                image_name = f"参考图_{len(seen_images)+1}"
                try:
                    # ✅ 核心修复：使用 path 参数，而不是 url
                    # Chainlit 会自动处理读取和传输，不需要关心 URL 编码
                    elements.append(
                        cl.Image(path=raw_img_path, name=image_name, display="inline")
                    )
                    seen_images.add(raw_img_path)
                    detail_text += f"**[🖼️ 已加载关联图片: {image_name}]**\n\n"
                except Exception as e:
                    print(f"❌ 加载图片出错: {e}")
            else:
                detail_text += "\n"

        step.output = f"检索到 {len(results)} 条资料"

        if not detail_text.strip():
            detail_text = "未检索到相关文档内容，将尝试使用通用知识回答。"
        
        # 将详情文本放在开头
        elements.insert(0, cl.Text(name="检索详情", content=detail_text, display="inline"))
        step.elements = elements

    source_elements = []
    for idx, doc in enumerate(results):
        meta = doc['metadata']
        source_name = f"参考来源 {idx+1}"
        content_preview = f"文件: {meta.get('filename')}\n页码: {meta.get('page_number', 'N/A')}\n\n{doc['content']}"
        element = cl.Text(name=source_name, content=content_preview, display="side")
        source_elements.append(element)

# 1. 准备最终回答需要的图片 (从 elements 里挑出图片)
    # 我们不要那个 "检索详情" 的 cl.Text，因为它太长了，留在 Step 里就好
    final_images = [el for el in elements if isinstance(el, cl.Image)]

    # 2. 准备侧边栏的引用源 (source_elements)
    source_elements = []
    for idx, doc in enumerate(results):
        meta = doc['metadata']
        source_name = f"参考来源 {idx+1}"
        content_preview = f"文件: {meta.get('filename')}\n页码: {meta.get('page_number', 'N/A')}\n\n{doc['content']}"
        # display="side" 表示在侧边栏显示
        element = cl.Text(name=source_name, content=content_preview, display="side")
        source_elements.append(element)

    # 3. 初始化消息并发送
    final_answer_msg = cl.Message(content="")
    
    # 【关键修改】初始只带图片
    final_answer_msg.elements = final_images 
    await final_answer_msg.send()

    track_msg_id(final_answer_msg.id)

    # 4. 生成与流式输出
    full_answer = await cl.make_async(agent.generate_response)(
        query=message.content,
        context=context_str,
        chat_history=chat_history,
        image_base64=image_base64
    )

    for char in full_answer:
        await final_answer_msg.stream_token(char)
        await asyncio.sleep(0.002)
    
    # 5. 【关键修改】合并图片和侧边栏引用，避免覆盖
    # 这样图片会保留在消息下方，引用会出现在侧边栏
    final_answer_msg.elements = final_images + source_elements
    
    await final_answer_msg.update()

    chat_manager.append_message("assistant", full_answer)
    chat_history.append({"role": "assistant", "content": full_answer})
    cl.user_session.set("restored_history", chat_history)