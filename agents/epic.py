from core.orchestrator import Agent
from core.llm import LLMClient
from typing import Dict, Any, Optional


EPIC_AGENT_PROMPT = """You are an Epic Architect Agent. Your role is to transform structured requirements into logical epics and work packages.

## Your Responsibilities:
1. Analyze the structured requirements
2. Group related functionality into cohesive epics
3. Define epic goals and success criteria
4. Identify dependencies between epics
5. Estimate epic complexity (small/medium/large)
6. Determine parallel vs sequential work

## Output Format:
Return a JSON object with:
- "epics": List of epics, each containing:
  - "id": Epic identifier (e.g., "EPIC-001")
  - "title": Short title
  - "description": Detailed description of the epic
  - "goals": List of specific goals
  - "scope": What's included in this epic
  - "dependencies": List of dependencies on other epics
  - "complexity": "small" | "medium" | "large"
  - "estimated_stories": Number of user stories expected
- "total_epics": Total count
- "recommendations": Any implementation recommendations

Each epic should be self-contained and deliver value independently where possible."""


class EpicAgent(Agent):
    AGENT_NAME = "epic"
    
    def __init__(self):
        super().__init__(
            name="EpicAgent",
            role="Epic Architect",
            description="Transforms requirements into logical epics and work packages",
            system_prompt=EPIC_AGENT_PROMPT
        )
        self.llm = LLMClient(agent_name=self.AGENT_NAME)

    def execute(self, requirements: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        req_str = f"""Requirements to transform into epics:

Title: {requirements.get('title', 'N/A')}
Summary: {requirements.get('summary', 'N/A')}
Scope: {requirements.get('scope', 'N/A')}

Functional Requirements:
{chr(10).join(f"- {fr}" for fr in requirements.get('functional_requirements', []))}

Non-Functional Requirements:
{chr(10).join(f"- {nfr}" for nfr in requirements.get('non_functional_requirements', []))}

Assumptions:
{chr(10).join(f"- {a}" for a in requirements.get('assumptions', []))}"""

        messages = self._build_messages(req_str, context)
        result = self.llm.chat_with_json(messages)
        
        result["source_requirements"] = requirements
        return result