from core.orchestrator import Agent
from core.llm import LLMClient
from typing import Dict, Any, Optional


TEST_GENERATOR_PROMPT = """You are a Test Engineer Agent. Your role is to generate comprehensive unit tests for user stories.

## Your Responsibilities:
1. Analyze the user story and its acceptance criteria
2. Generate pytest-compatible unit tests
3. Cover both positive and negative test cases
4. Use proper assertions
5. Include setup and teardown if needed
6. Follow pytest best practices

## Output Format:
Return a JSON object with:
- "story_id": The story ID being tested
- "test_code": Complete pytest test code as a string
- "test_count": Number of test functions
- "coverage_notes": What acceptance criteria are covered

## Test Code Requirements:
- Use pytest framework
- Include docstrings explaining what each test verifies
- Use descriptive test function names (test_<what_is_being_tested>)
- Include proper imports
- Use fixtures where appropriate
- Assert expected behavior clearly

Generate tests that a developer can run directly to verify their implementation."""


class TestGeneratorAgent(Agent):
    AGENT_NAME = "test_generator"
    
    def __init__(self):
        super().__init__(
            name="TestGeneratorAgent",
            role="Test Engineer",
            description="Generates pytest unit tests for user stories",
            system_prompt=TEST_GENERATOR_PROMPT
        )
        self.llm = LLMClient(agent_name=self.AGENT_NAME)

    def execute(self, story: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        story_info = f"""User Story to generate tests for:

ID: {story.get('id', 'N/A')}
Title: {story.get('title', 'N/A')}
Description: {story.get('description', 'N/A')}
Epic ID: {story.get('epic_id', 'N/A')}

Acceptance Criteria:
{chr(10).join(f"- {ac}" for ac in story.get('acceptance_criteria', []))}

Priority: {story.get('priority', 'N/A')}
Story Points: {story.get('story_points', 'N/A')}

Technical Notes: {story.get('technical_notes', 'N/A')}"""

        messages = self._build_messages(story_info, context)
        result = self.llm.chat_with_json(messages)
        
        return result