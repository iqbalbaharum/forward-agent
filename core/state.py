from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum
import json
from pathlib import Path


class StoryStatus(str, Enum):
    PENDING = "pending"
    GENERATED = "generated"
    TESTS_GENERATED = "tests_generated"
    APPROVED = "approved"
    REJECTED = "rejected"


class WorkflowState:
    def __init__(self, session_id: str, requirement: str):
        self.session_id = session_id
        self.requirement = requirement
        self.status = "initialized"
        self.created_at = datetime.utcnow().isoformat()
        self.updated_at = datetime.utcnow().isoformat()
        self.artifacts: Dict[str, Any] = {}
        self.stories: List[Dict[str, Any]] = []

    def update_status(self, status: str):
        self.status = status
        self.updated_at = datetime.utcnow().isoformat()

    def add_artifact(self, key: str, value: Any):
        self.artifacts[key] = value
        self.updated_at = datetime.utcnow().isoformat()

    def add_story(self, story: Dict[str, Any]):
        story["status"] = StoryStatus.GENERATED.value
        story["created_at"] = datetime.utcnow().isoformat()
        self.stories.append(story)
        self.updated_at = datetime.utcnow().isoformat()

    def update_story_status(self, story_id: str, status: StoryStatus, feedback: Optional[str] = None):
        for story in self.stories:
            if story.get("id") == story_id:
                story["status"] = status.value
                if feedback:
                    story["feedback"] = feedback
                self.updated_at = datetime.utcnow().isoformat()
                break

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "requirement": self.requirement,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "artifacts": self.artifacts,
            "stories": self.stories
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowState":
        state = cls(data["session_id"], data["requirement"])
        state.status = data.get("status", "initialized")
        state.created_at = data.get("created_at", datetime.utcnow().isoformat())
        state.updated_at = data.get("updated_at", datetime.utcnow().isoformat())
        state.artifacts = data.get("artifacts", {})
        state.stories = data.get("stories", [])
        return state


class StateManager:
    def __init__(self, storage_path: Path):
        self.storage_path = storage_path
        self.states: Dict[str, WorkflowState] = {}
        storage_path.mkdir(parents=True, exist_ok=True)

    def create_state(self, session_id: str, requirement: str) -> WorkflowState:
        state = WorkflowState(session_id, requirement)
        self.states[session_id] = state
        return state

    def get_state(self, session_id: str) -> Optional[WorkflowState]:
        return self.states.get(session_id)

    def save_state(self, session_id: str):
        state = self.states.get(session_id)
        if state:
            file_path = self.storage_path / f"{session_id}.json"
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(state.to_dict(), f, indent=2)

    def load_state(self, session_id: str) -> Optional[WorkflowState]:
        file_path = self.storage_path / f"{session_id}.json"
        if file_path.exists():
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)
                state = WorkflowState.from_dict(data)
                self.states[session_id] = state
                return state
        return None

    def list_states(self) -> List[Dict[str, Any]]:
        states = []
        for file_path in self.storage_path.glob("*.json"):
            state = self.load_state(file_path.stem)
            if state:
                states.append({
                    "session_id": state.session_id,
                    "requirement": state.requirement[:50] + "..." if len(state.requirement) > 50 else state.requirement,
                    "status": state.status,
                    "story_count": len(state.stories),
                    "created_at": state.created_at
                })
        return states