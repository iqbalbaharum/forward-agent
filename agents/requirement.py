from core.orchestrator import Agent
from core.llm import LLMClient
from typing import Dict, Any, Optional


REQUIREMENT_AGENT_PROMPT = """You are a Requirement Analyst Agent. Your role is to analyze and structure raw requirements from users.

## Your Responsibilities:
1. Parse raw requirement text
2. Identify the core problem or feature request
3. Clarify scope and boundaries
4. Extract functional requirements
5. Identify non-functional requirements (performance, security, etc.)
6. List any assumptions or dependencies

## Output Format:
Return a JSON object with:
- "title": Brief title of the requirement
- "summary": 2-3 sentence summary
- "scope": What's included and excluded
- "functional_requirements": List of functional requirements
- "non_functional_requirements": List of non-functional requirements
- "assumptions": List of assumptions
- "dependencies": List of dependencies

Be concise but thorough. Focus on actionable information that engineers can use."""


class RequirementAgent(Agent):
    AGENT_NAME = "requirement"
    
    def __init__(self):
        super().__init__(
            name="RequirementAgent",
            role="Requirement Analyst",
            description="Analyzes and structures raw requirements into structured format",
            system_prompt=REQUIREMENT_AGENT_PROMPT
        )
        self.llm = LLMClient(agent_name=self.AGENT_NAME)

    def execute(self, requirement: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        messages = self._build_messages(
            f"Analyze and structure the following requirement:\n\n{requirement}",
            context
        )
        
        result = self.llm.chat_with_json(messages)
        
        result["raw_requirement"] = requirement
        return result