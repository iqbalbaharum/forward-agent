from core.orchestrator import Agent
from core.llm import LLMClient
from typing import Dict, Any, Optional


COLLABORATE_AGENT_PROMPT = """You are a Technical Requirements Collaborator.

Your job is to update the technical_notes for a user story based on user feedback.

## Context
The user is collaborating on a user story to refine its technical requirements.
You need to intelligently process their feedback and update the technical notes.

## CURRENT TECHNICAL NOTES:
{current_notes}

## USER FEEDBACK:
{prompt}

## INSTRUCTIONS:
1. Analyze the user's feedback carefully
2. Decide whether to:
   - APPEND: Add new requirements (e.g., "add tips button")
   - MODIFY: Change existing requirements (e.g., "change login to Google login")
   - REMOVE: Delete outdated requirements (e.g., "remove password field")
   - RESTRUCTURE: Reorganize for clarity
3. Preserve any valid existing requirements that weren't changed
4. Output as a clear, structured technical_notes format
5. Provide a brief summary of what changed

## Output Format:
Return a JSON object with:
- "technical_notes": The updated technical notes (string)
- "change_type": "append" | "modify" | "remove" | "restructure"
- "summary": Brief description of what was changed"""


class CollaborateAgent(Agent):
    AGENT_NAME = "collaborate"
    
    def __init__(self):
        super().__init__(
            name="CollaborateAgent",
            role="Technical Requirements Collaborator",
            description="Intelligently updates story technical notes based on user feedback",
            system_prompt=COLLABORATE_AGENT_PROMPT
        )
        self.llm = LLMClient(agent_name=self.AGENT_NAME)

    def execute(self, current_notes: str, prompt: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        full_prompt = f"""CURRENT TECHNICAL NOTES:
{current_notes or 'No technical notes provided yet.'}

USER FEEDBACK:
{prompt}"""

        messages = self._build_messages(full_prompt, context)
        result = self.llm.chat_with_json(messages)
        
        return result