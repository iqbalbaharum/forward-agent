from typing import Dict, Any, List, Optional
from datetime import datetime
import json
from pathlib import Path


class SessionMemory:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.messages: List[Dict[str, Any]] = []
        self.context: Dict[str, Any] = {}
        self.created_at = datetime.utcnow().isoformat()

    def add_message(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }
        self.messages.append(message)

    def get_messages(self) -> List[Dict[str, str]]:
        return [{"role": m["role"], "content": m["content"]} for m in self.messages]

    def set_context(self, key: str, value: Any):
        self.context[key] = value

    def get_context(self, key: str) -> Any:
        return self.context.get(key)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "messages": self.messages,
            "context": self.context,
            "created_at": self.created_at
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionMemory":
        session = cls(data["session_id"])
        session.messages = data.get("messages", [])
        session.context = data.get("context", {})
        session.created_at = data.get("created_at", datetime.utcnow().isoformat())
        return session


class MemoryManager:
    def __init__(self, storage_path: Path):
        self.storage_path = storage_path
        self.sessions: Dict[str, SessionMemory] = {}
        storage_path.mkdir(parents=True, exist_ok=True)

    def create_session(self, session_id: str) -> SessionMemory:
        session = SessionMemory(session_id)
        self.sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[SessionMemory]:
        return self.sessions.get(session_id)

    def save_session(self, session_id: str):
        session = self.sessions.get(session_id)
        if session:
            file_path = self.storage_path / f"{session_id}.json"
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(session.to_dict(), f, indent=2)

    def load_session(self, session_id: str) -> Optional[SessionMemory]:
        file_path = self.storage_path / f"{session_id}.json"
        if file_path.exists():
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)
                session = SessionMemory.from_dict(data)
                self.sessions[session_id] = session
                return session
        return None