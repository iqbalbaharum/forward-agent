from core.orchestrator import Agent
from core.llm import LLMClient
from typing import Dict, Any, Optional
from pathlib import Path


SPECULATE_AGENT_PROMPT = """You are a Technical Requirements Collaborator.

Your job is to:
1. Classify user feedback as SIMPLE or COMPLEX
2. For SIMPLE changes: Generate updated technical notes that incorporate the feedback
3. For COMPLEX changes: Explain why it requires new epic/stories"""


def load_skill() -> str:
    skill_path = Path(__file__).parent / "skills" / "speculate.md"
    if skill_path.exists():
        return f"\n\n# Classification Skill Guidelines\n\n{skill_path.read_text()}"
    return ""


class SpeculateAgent(Agent):
    AGENT_NAME = "speculate"
    
    def __init__(self):
        system_prompt = SPECULATE_AGENT_PROMPT + load_skill()
        super().__init__(
            name="SpeculateAgent",
            role="Technical Requirements Collaborator",
            description="Classifies feedback and generates updated technical notes",
            system_prompt=system_prompt
        )
        self.llm = LLMClient(agent_name=self.AGENT_NAME)

    def execute(
        self, 
        feedback: str, 
        story: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        existing_ids = ""
        if context:
            epic_ids = context.get("existing_epic_ids", [])
            story_ids = context.get("existing_story_ids", [])
            existing_ids = f"""
## EXISTING WORKSPACE CONTEXT
- Current Epic: {context.get("epic_id", "Unknown")}
- Existing Epic IDs: {', '.join(epic_ids) if epic_ids else "None"}
- Existing Story IDs: {', '.join(story_ids) if story_ids else "None"}

IMPORTANT: When creating new epics/stories, use IDs that do NOT conflict with existing ones."""

        existing_notes = story.get('technical_notes', 'No technical notes provided.')
        existing_acceptance = story.get('acceptance_criteria', [])
        if isinstance(existing_acceptance, list):
            existing_acceptance = '\n'.join([f"- {c}" for c in existing_acceptance])

        full_prompt = f"""## USER FEEDBACK:
{feedback}

## CURRENT STORY CONTEXT
- Story ID: {story.get('id', 'N/A')}
- Story Title: {story.get('title', 'N/A')}
- Story Description: {story.get('description', 'N/A')}
- Epic ID: {story.get('epic_id', 'N/A')}
- Current Technical Notes:
{existing_notes}
- Current Acceptance Criteria:
{existing_acceptance or 'None'}{existing_ids}

## YOUR TASK
1. Classify the feedback as SIMPLE or COMPLEX based on the skill guidelines
2. For SIMPLE: Generate updated technical_notes that REPLACE the existing notes with the feedback incorporated
3. For COMPLEX: Explain why new epic/stories are needed

## CLASSIFICATION RULES (from skill):
- SIMPLE: Validation rules, constraints, logging, security measures, technology choices within same category, clarifications that don't change scope
- COMPLEX: New external integrations, new user-facing features, new platforms, fundamentally new functionality

## OUTPUT FORMAT
Return a JSON object with COMPLETE updated technical notes:
```json
{{
  "change_type": "simple" | "complex",
  "reasoning": "Brief explanation of classification decision",
  "technical_notes": "COMPLETE updated technical notes that REPLACE existing notes."
}}
```

IMPORTANT: For SIMPLE changes, the technical_notes field MUST contain the COMPLETE updated technical notes with feedback incorporated. This will REPLACE the existing technical notes."""

        messages = self._build_messages(full_prompt, context)
        result = self.llm.chat_with_json(messages)
        
        result['original_story_id'] = story.get('id')
        result['feedback'] = feedback
        
        return result
