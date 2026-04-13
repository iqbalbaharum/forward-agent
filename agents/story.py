from core.orchestrator import Agent
from typing import Dict, Any, Optional


STORY_AGENT_PROMPT = """You are a User Story Agent. Your role is to break down epics into actionable user stories with clear acceptance criteria.

## Your Responsibilities:
1. Analyze each epic and its goals
2. Create user stories that deliver epic value incrementally
3. Define clear acceptance criteria for each story
4. Identify story dependencies
5. Assign story points or effort estimate
6. Define story dependencies (blocking, related)

## Output Format:
Return a JSON object with:
- "stories": List of user stories, each containing:
  - "id": Story identifier (e.g., "STORY-001")
  - "epic_id": Parent epic ID
  - "title": Short story title
  - "description": User story in format: "As a [user], I want [feature], so that [benefit]"
  - "acceptance_criteria": List of clear, testable acceptance criteria
  - "story_points": 1, 2, 3, 5, 8, or 13
  - "priority": "must" | "should" | "could" | "won't"
  - "dependencies": List of story IDs this depends on
  - "technical_notes": Any implementation hints
- "total_stories": Count of stories
- "total_points": Sum of story points
- "grouped_by_epic": Stories organized by epic ID

Focus on delivering value to the user with each story. Acceptance criteria must be testable."""


class StoryAgent(Agent):
    def __init__(self):
        super().__init__(
            name="StoryAgent",
            role="User Story Analyst",
            description="Breaks down epics into actionable user stories with acceptance criteria",
            system_prompt=STORY_AGENT_PROMPT
        )

    def execute(self, epics: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        epics_text = ""
        for epic in epics.get("epics", []):
            epics_text += f"""
Epic: {epic.get('title', 'N/A')}
Description: {epic.get('description', 'N/A')}
Goals: {', '.join(epic.get('goals', []))}
Scope: {epic.get('scope', 'N/A')}
Complexity: {epic.get('complexity', 'N/A')}
---
"""
        
        prompt = f"""Break down the following epics into user stories:

{epics_text}"""

        messages = self._build_messages(prompt, context)
        result = self.llm.chat_with_json(messages)
        
        result["source_epics"] = epics
        return result