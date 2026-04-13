from typing import Dict, Any, List, Optional, Callable
from pathlib import Path
from core.llm import LLMClient
from core.memory import MemoryManager
from core.state import StateManager, WorkflowState
from config.settings import STORIES_DIR, TESTS_DIR, ARTIFACTS_DIR
import uuid
import json


class Agent:
    def __init__(self, name: str, role: str, description: str, system_prompt: str):
        self.name = name
        self.role = role
        self.description = description
        self.system_prompt = system_prompt
        self.llm = LLMClient()

    def execute(self, input_data: Any, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        raise NotImplementedError("Each agent must implement execute method")

    def _build_messages(self, user_prompt: str, context: Optional[Dict[str, Any]] = None) -> List[Dict[str, str]]:
        messages = [{"role": "system", "content": self.system_prompt}]
        if context:
            context_str = "\n\n## Context\n"
            for key, value in context.items():
                context_str += f"- {key}: {value}\n"
            user_prompt = context_str + "\n\n## Task\n" + user_prompt
        messages.append({"role": "user", "content": user_prompt})
        return messages


class Orchestrator:
    def __init__(self, storage_path: Path = ARTIFACTS_DIR):
        self.storage_path = storage_path
        self.memory_manager = MemoryManager(storage_path / "memory")
        self.state_manager = StateManager(storage_path / "state")
        self.agents: Dict[str, Agent] = {}

    def register_agent(self, name: str, agent: Agent):
        self.agents[name] = agent

    def run_requirement_to_stories(self, requirement: str) -> Dict[str, Any]:
        session_id = str(uuid.uuid4())[:8]
        
        state = self.state_manager.create_state(session_id, requirement)
        state.update_status("requirement")
        
        requirement_agent = self.agents.get("requirement")
        if not requirement_agent:
            raise ValueError("Requirement agent not registered")
        
        requirement_result = requirement_agent.execute(requirement)
        state.add_artifact("requirements", requirement_result)
        
        state.update_status("epic")
        
        epic_agent = self.agents.get("epic")
        if not epic_agent:
            raise ValueError("Epic agent not registered")
        
        epic_result = epic_agent.execute(requirement_result)
        state.add_artifact("epics", epic_result)
        
        state.update_status("story")
        
        story_agent = self.agents.get("story")
        if not story_agent:
            raise ValueError("Story agent not registered")
        
        story_result = story_agent.execute(epic_result)
        
        for story in story_result.get("stories", []):
            state.add_story(story)
        
        state.update_status("stories_generated")
        self.state_manager.save_state(session_id)
        
        self._save_artifacts(session_id, requirement_result, epic_result, story_result)
        
        return {
            "session_id": session_id,
            "requirements": requirement_result,
            "epics": epic_result,
            "stories": story_result
        }

    def _save_artifacts(self, session_id: str, requirements: Dict, epics: Dict, stories: Dict):
        req_dir = self.storage_path / "requirements"
        req_dir.mkdir(parents=True, exist_ok=True)
        with open(req_dir / f"{session_id}.json", "w") as f:
            json.dump(requirements, f, indent=2)
        
        epic_dir = self.storage_path / "epics"
        epic_dir.mkdir(parents=True, exist_ok=True)
        with open(epic_dir / f"{session_id}.json", "w") as f:
            json.dump(epics, f, indent=2)
        
        story_dir = self.storage_path / "stories"
        story_dir.mkdir(parents=True, exist_ok=True)
        with open(story_dir / f"{session_id}.json", "w") as f:
            json.dump(stories, f, indent=2)

    def generate_tests_for_story(self, session_id: str, story: Dict) -> Dict[str, Any]:
        test_agent = self.agents.get("test_generator")
        if not test_agent:
            raise ValueError("Test generator agent not registered")
        
        test_result = test_agent.execute(story)
        
        test_dir = TESTS_DIR
        test_dir.mkdir(parents=True, exist_ok=True)
        
        story_id = story.get("id", "unknown")
        with open(test_dir / f"test_{story_id}.py", "w") as f:
            f.write(test_result.get("test_code", ""))
        
        return test_result

    def get_state(self, session_id: str) -> Optional[WorkflowState]:
        return self.state_manager.load_state(session_id)

    def list_sessions(self) -> List[Dict[str, Any]]:
        return self.state_manager.list_states()

    def approve_story(self, session_id: str, story_id: str) -> bool:
        state = self.state_manager.load_state(session_id)
        if not state:
            return False
        
        from core.state import StoryStatus
        state.update_story_status(story_id, StoryStatus.APPROVED)
        self.state_manager.save_state(session_id)
        return True

    def reject_story(self, session_id: str, story_id: str, feedback: str) -> bool:
        state = self.state_manager.load_state(session_id)
        if not state:
            return False
        
        from core.state import StoryStatus
        state.update_story_status(story_id, StoryStatus.REJECTED, feedback)
        self.state_manager.save_state(session_id)
        return True