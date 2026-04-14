from core.orchestrator import Agent
from core.llm import LLMClient
from typing import Dict, Any, Optional


SPECULATE_AGENT_PROMPT = """You are a Technical Requirements Collaborator.

Your job is to classify user feedback into one of two categories:

## USER FEEDBACK:
{feedback}

## CURRENT STORY CONTEXT:
- ID: {story_id}
- Title: {title}
- Description: {description}

## CLASSIFICATION

Classify the feedback as one of:

**SIMPLE** - Minor changes that can be handled by updating technical notes:
- Wording or phrasing changes
- Simple UI tweaks (color, size, position)
- Adding simple validations or edge cases
- Clarifications that don't change scope
- Anything that doesn't introduce new functionality

**COMPLEX** - Requires new epic/stories to solve:
- Introduces a completely new feature area
- Requires backend systems not mentioned
- Changes the fundamental user flow
- Adds integration with external systems (payment, auth, APIs)
- Requires new pages/routes that weren't in scope
- Any "known unknown" that was missing from original requirements

## DECISION

If this feedback can be addressed by simply updating the technical notes for the current story → SIMPLE

If this feedback requires NEW capabilities, a new epic, or significantly new stories → COMPLEX

## OUTPUT FORMAT

Return a JSON object:
```json
{{
  "change_type": "simple" | "complex",
  "reasoning": "Brief explanation of why this is simple or complex"
}}
```"""


class SpeculateAgent(Agent):
    AGENT_NAME = "speculate"
    
    def __init__(self):
        super().__init__(
            name="SpeculateAgent",
            role="Technical Requirements Collaborator",
            description="Classifies user feedback as simple or complex",
            system_prompt=SPECULATE_AGENT_PROMPT
        )
        self.llm = LLMClient(agent_name=self.AGENT_NAME)

    def execute(
        self, 
        feedback: str, 
        story: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        full_prompt = f"""USER FEEDBACK:
{feedback}

CURRENT STORY CONTEXT:
- ID: {story.get('id', 'N/A')}
- Title: {story.get('title', 'N/A')}
- Description: {story.get('description', 'N/A')}"""

        messages = self._build_messages(full_prompt, context)
        result = self.llm.chat_with_json(messages)
        
        result['original_story_id'] = story.get('id')
        result['feedback'] = feedback
        
        return result
