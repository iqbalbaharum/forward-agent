from core.orchestrator import Agent
from core.llm import LLMClient
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime


def load_skill() -> str:
    skill_path = Path(__file__).parent / "skills" / "reject.md"
    if skill_path.exists():
        return f"\n\n# Rejection Analysis Skill\n\n{skill_path.read_text()}"
    return ""


class RejectAgent(Agent):
    AGENT_NAME = "reject"
    
    def __init__(self):
        system_prompt = """You are a Project Requirements Analyst.

Your job is to analyze rejection feedback to understand user priorities and update project-level requirements.

IMPORTANT: This is PROJECT-LEVEL analysis, not individual story modification."""
        
        super().__init__(
            name="RejectAgent",
            role="Project Requirements Analyst",
            description="Analyzes rejection patterns and updates project requirements",
            system_prompt=system_prompt + load_skill()
        )
        self.llm = LLMClient(agent_name=self.AGENT_NAME)

    def get_all_rejected_stories(self, state) -> List[Dict[str, Any]]:
        """Get all rejected stories from workspace state"""
        if not state or not state.stories:
            return []
        
        rejected = []
        for story in state.stories:
            if story.get('status') == 'rejected':
                import json
                feedback = story.get('feedback', '')
                if isinstance(feedback, str) and feedback.startswith('{'):
                    try:
                        feedback_data = json.loads(feedback)
                        story_feedback = feedback_data.get('user_feedback', '')
                    except:
                        story_feedback = feedback
                else:
                    story_feedback = feedback
                
                rejected.append({
                    'id': story.get('id'),
                    'title': story.get('title'),
                    'description': story.get('description'),
                    'feedback': story_feedback,
                    'epic_id': story.get('epic_id')
                })
        
        return rejected

    def get_requirements_data(self, workspace_id: str, state) -> Dict[str, Any]:
        """Get existing requirements or create default"""
        req_dir = Path(__file__).parent.parent.parent / "artifacts" / "requirements"
        req_file = req_dir / f"{workspace_id}.json"
        
        if req_file.exists():
            import json
            with open(req_file, 'r') as f:
                return json.load(f)
        
        return {
            'workspace_id': workspace_id,
            'original_requirement': state.requirement if state else '',
            'project_summary': state.requirement if state else '',
            'scope': [],
            'detected_priorities': {},
            'rejection_history': []
        }

    def save_requirements(self, workspace_id: str, data: Dict[str, Any]):
        """Save requirements to file"""
        req_dir = Path(__file__).parent.parent.parent / "artifacts" / "requirements"
        req_dir.mkdir(parents=True, exist_ok=True)
        req_file = req_dir / f"{workspace_id}.json"
        
        import json
        with open(req_file, 'w') as f:
            json.dump(data, f, indent=2)

    def check_dependencies(self, state) -> Dict[str, Any]:
        """Computational dependency analysis - no LLM needed"""
        if not state or not state.stories:
            return {
                'warnings': [],
                'orphan_dependencies': [],
                'cycle_dependencies': []
            }
        
        stories = {s.get('id'): s for s in state.stories}
        results = {
            'warnings': [],
            'orphan_dependencies': [],
            'cycle_dependencies': []
        }
        
        dependents_map = {sid: [] for sid in stories}
        
        for story_id, story in stories.items():
            deps = story.get('dependencies', [])
            if isinstance(deps, str):
                deps = [d.strip() for d in deps.split(',') if d.strip()]
            
            for dep in deps:
                if dep in dependents_map:
                    dependents_map[dep].append(story_id)
        
        for story_id, story in stories.items():
            deps = story.get('dependencies', [])
            if isinstance(deps, str):
                deps = [d.strip() for d in deps.split(',') if d.strip()]
            
            for dep in deps:
                if dep not in stories:
                    results['warnings'].append({
                        'type': 'missing_dependency',
                        'story': story_id,
                        'missing': dep
                    })
                    results['orphan_dependencies'].append({
                        'story': story_id,
                        'depends_on': dep
                    })
        
        visited = set()
        rec_stack = set()
        graph = {sid: [] for sid in stories}
        
        for story_id, story in stories.items():
            deps = story.get('dependencies', [])
            if isinstance(deps, str):
                deps = [d.strip() for d in deps.split(',') if d.strip()]
            graph[story_id] = deps
        
        def dfs(node, path):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor, path):
                        return True
                elif neighbor in rec_stack:
                    cycle_idx = path.index(neighbor)
                    cycle = path[cycle_idx:] + [neighbor]
                    results['cycle_dependencies'].append(cycle)
                    return True
            
            path.pop()
            rec_stack.remove(node)
            return False
        
        for story_id in stories:
            if story_id not in visited:
                dfs(story_id, [])
        
        for cycle in results['cycle_dependencies']:
            results['warnings'].append({
                'type': 'circular_dependency',
                'cycle': cycle
            })
        
        return results

    def execute(self, story: Dict[str, Any], feedback: str, state) -> Dict[str, Any]:
        """Main execution - analyze all rejections and update requirements"""
        workspace_id = state.session_id if hasattr(state, 'session_id') else 'unknown'
        
        all_rejected = self.get_all_rejected_stories(state)
        
        current_rejection = {
            'id': story.get('id'),
            'title': story.get('title'),
            'feedback': feedback,
            'date': datetime.utcnow().isoformat()
        }
        
        all_rejected.append(current_rejection)
        
        requirements = self.get_requirements_data(workspace_id, state)
        
        rejected_list_text = "\n".join([
            f"- {r['id']}: {r.get('title', 'N/A')} | Feedback: {r.get('feedback', 'N/A')}"
            for r in all_rejected
        ])
        
        current_scope = requirements.get('scope', [])
        scope_text = "\n".join([f"- {s}" for s in current_scope]) if current_scope else "No scope defined"
        
        full_prompt = f"""## WORKSPACE: {workspace_id}

## CURRENT PROJECT SUMMARY:
{requirements.get('project_summary', 'Not defined')}

## CURRENT SCOPE:
{scope_text}

## ALL REJECTED STORIES:
{rejected_list_text}

## NEW FEEDBACK:
{feedback}

## YOUR TASK
Analyze the rejection patterns and update project-level requirements.

Based on the skill guidelines:
1. Identify patterns from ALL rejections
2. Detect user's technical priorities
3. Update the project summary to reflect new understanding
4. Suggest scope changes (remove/add/simplify features)

Return a JSON object with your complete analysis."""

        messages = self._build_messages(full_prompt)
        result = self.llm.chat_with_json(messages)
        
        dependency_analysis = self.check_dependencies(state)
        
        rejection_history = requirements.get('rejection_history', [])
        rejection_history.append({
            'story_id': story.get('id'),
            'feedback': feedback,
            'date': datetime.utcnow().isoformat()
        })
        
        updated_requirements = {
            'workspace_id': workspace_id,
            'original_requirement': requirements.get('original_requirement', ''),
            'project_summary': result.get('updated_summary', requirements.get('project_summary', '')),
            'scope': requirements.get('scope', []),
            'detected_priorities': result.get('analysis', {}).get('priorities_detected', {}),
            'rejection_history': rejection_history,
            'last_updated': datetime.utcnow().isoformat()
        }
        
        scope_changes = result.get('scope_changes', {})
        if scope_changes:
            updated_requirements['scope'] = self.apply_scope_changes(
                requirements.get('scope', []),
                scope_changes
            )
        
        self.save_requirements(workspace_id, updated_requirements)
        
        return {
            'success': True,
            'analysis': result.get('analysis', {}),
            'updated_summary': result.get('updated_summary', ''),
            'scope_changes': scope_changes,
            'updated_scope': updated_requirements.get('scope', []),
            'rejected_stories': all_rejected,
            'dependency_warnings': dependency_analysis.get('warnings', []),
            'requirements_file': f"artifacts/requirements/{workspace_id}.json",
            'requires_confirmation': True
        }

    def apply_scope_changes(self, current_scope: List[str], changes: Dict) -> List[str]:
        """Apply scope changes to current scope"""
        scope = list(current_scope)
        
        for removed in changes.get('removed', []):
            scope = [s for s in scope if removed.lower() not in s.lower()]
        
        for added in changes.get('added', []):
            if added not in scope:
                scope.append(added)
        
        return scope
