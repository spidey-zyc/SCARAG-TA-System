# chat_manager.py
import os
import json
import uuid
from datetime import datetime
from typing import List, Dict, Optional

# 你的对话存储目录
CHAT_DIR = "/Users/fangjie/Documents/code/RAG-programs/chat"

class ChatManager:
    def __init__(self):
        os.makedirs(CHAT_DIR, exist_ok=True)
        self.current_chat_id = None
        self.current_chat_name = None
        self.current_filename = None

    def create_new_chat(self, name: str = None) -> str:
        """创建一个新的会话"""
        self.current_chat_id = str(uuid.uuid4())
        
        if not name:
            name = f"New Chat {datetime.now().strftime('%m-%d %H:%M')}"
        self.current_chat_name = name
        
        safe_name = self._get_safe_filename(name)
        self.current_filename = safe_name
        
        data = {
            "id": self.current_chat_id,
            "name": name,
            "created_at": datetime.now().isoformat(),
            "messages": []
        }
        self._save_file(data, filename=safe_name)
        return self.current_chat_id

    def list_chats(self) -> List[Dict]:
        """列出所有已有会话"""
        chats = []
        if not os.path.exists(CHAT_DIR):
            return []
            
        for filename in os.listdir(CHAT_DIR):
            if filename.endswith(".json"):
                try:
                    with open(os.path.join(CHAT_DIR, filename), 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        chats.append({
                            "id": data.get("id"),
                            "name": data.get("name", "Untitled"),
                            "filename": filename,
                            "updated_at": data.get("updated_at", data.get("created_at", ""))
                        })
                except:
                    continue
        chats.sort(key=lambda x: x["updated_at"], reverse=True)
        return chats

    def load_chat_by_filename(self, filename: str) -> List[Dict]:
        """通过文件名加载会话"""
        filepath = os.path.join(CHAT_DIR, filename)
        if not os.path.exists(filepath):
            return []
            
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            self.current_chat_id = data.get("id")
            self.current_chat_name = data.get("name")
            self.current_filename = filename
            return data.get("messages", [])

    def rename_chat(self, new_name: str):
        """重命名"""
        if not self.current_filename:
            return False
        
        data = self._load_current_file_data()
        if not data:
            return False

        data["name"] = new_name
        self.current_chat_name = new_name
        
        new_filename = self._get_safe_filename(new_name)
        old_filepath = os.path.join(CHAT_DIR, self.current_filename)
        new_filepath = os.path.join(CHAT_DIR, new_filename)
        
        try:
            os.rename(old_filepath, new_filepath)
            self.current_filename = new_filename
            self._save_file(data, filename=new_filename)
            return True
        except Exception as e:
            print(f"重命名失败: {e}")
            return False

    # 🆕 新增：删除指定会话
    def delete_chat(self, filename: str) -> bool:
        """删除指定的会话文件"""
        filepath = os.path.join(CHAT_DIR, filename)
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                
                # 如果删除的是当前正在进行的会话，重置为新会话
                if filename == self.current_filename:
                    print("删除了当前会话，正在重置...")
                    self.create_new_chat()
                return True
        except Exception as e:
            print(f"删除失败: {e}")
        return False

    def append_message(self, role: str, content: str):
        """追加消息"""
        if not self.current_filename:
            self.create_new_chat()
            
        data = self._load_current_file_data()
        if data:
            msg_entry = {
                "role": role,
                "content": content,
                "timestamp": datetime.now().isoformat()
            }
            data["messages"].append(msg_entry)
            data["updated_at"] = datetime.now().isoformat()
            self._save_file(data, filename=self.current_filename)

    def _load_current_file_data(self) -> Optional[Dict]:
        if not self.current_filename:
            return None
        filepath = os.path.join(CHAT_DIR, self.current_filename)
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None

    def _save_file(self, data: Dict, filename: str):
        filepath = os.path.join(CHAT_DIR, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _get_safe_filename(self, name: str) -> str:
        safe_name = "".join([c for c in name if c.isalnum() or c in (' ', '-', '_', '.')]).strip()
        if not safe_name:
            safe_name = "Untitled"
        filename = f"{safe_name}.json"
        base, ext = os.path.splitext(filename)
        counter = 1
        while os.path.exists(os.path.join(CHAT_DIR, filename)):
            if self.current_filename == filename:
                return filename
            filename = f"{base}_{counter}{ext}"
            counter += 1
        return filename