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

    def update_story(self, story_id: str, updates: Dict[str, Any]) -> bool:
        for story in self.stories:
            if story.get("id") == story_id:
                story.update(updates)
                self.updated_at = datetime.utcnow().isoformat()
                return True
        return False

    def add_dependency(self, story_id: str, depends_on: str) -> bool:
        for story in self.stories:
            if story.get("id") == story_id:
                deps = story.get("dependencies", [])
                if isinstance(deps, str):
                    deps = [d.strip() for d in deps.split(',') if d.strip()]
                if depends_on not in deps:
                    deps.append(depends_on)
                    story["dependencies"] = deps
                    self.updated_at = datetime.utcnow().isoformat()
                return True
        return False

    def remove_story(self, story_id: str) -> bool:
        for i, story in enumerate(self.stories):
            if story.get("id") == story_id:
                self.stories.pop(i)
                self.updated_at = datetime.utcnow().isoformat()
                self.clean_dependencies([story_id])
                return True
        return False

    def clean_dependencies(self, removed_story_ids: List[str]):
        """Remove references to deleted stories from other stories' dependencies"""
        for story in self.stories:
            deps = story.get("dependencies", [])
            if isinstance(deps, str):
                deps = [d.strip() for d in deps.split(',') if d.strip()]
            if isinstance(deps, list):
                story["dependencies"] = [d for d in deps if d not in removed_story_ids]

    def remove_stories_by_epic(self, epic_id: str) -> List[str]:
        removed_ids = self.get_story_ids_by_epic(epic_id)
        self.stories = [
            story for story in self.stories
            if story.get("epic_id") != epic_id
        ]
        if removed_ids:
            self.clean_dependencies(removed_ids)
        self.updated_at = datetime.utcnow().isoformat()
        return removed_ids

    def get_story_ids_by_epic(self, epic_id: str) -> List[str]:
        return [story.get("id") for story in self.stories if story.get("epic_id") == epic_id]

    def get_next_story_number(self) -> int:
        max_num = 0
        for story in self.stories:
            story_id = story.get("id", "")
            if story_id.startswith("STORY-"):
                try:
                    num = int(story_id.split("-")[1])
                    max_num = max(max_num, num)
                except ValueError:
                    pass
        return max_num + 1

    def update_story_status(self, story_id: str, status: StoryStatus, feedback: Optional[str] = None) -> bool:
        for story in self.stories:
            if story.get("id") == story_id:
                story["status"] = status.value
                if feedback:
                    story["feedback"] = feedback
                self.updated_at = datetime.utcnow().isoformat()
                return True
        return False

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

    def update_story_status(self, session_id: str, story_id: str, status: StoryStatus, feedback: Optional[str] = None) -> bool:
        state = self.load_state(session_id)
        if not state:
            return False
        success = state.update_story_status(story_id, status, feedback)
        if success:
            self.save_state(session_id)
        return success

    def remove_stories_by_epic(self, session_id: str, epic_id: str) -> List[str]:
        state = self.load_state(session_id)
        if not state:
            return []
        removed_ids = state.get_story_ids_by_epic(epic_id)
        state.remove_stories_by_epic(epic_id)
        self.save_state(session_id)
        return removed_ids