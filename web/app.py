import os
import json
from pathlib import Path
from flask import Flask, render_template, jsonify, request, redirect
from config.settings import ARTIFACTS_DIR, STORIES_DIR, TESTS_DIR, EPICS_DIR, OPENROUTER_API_KEY
from core.state import StateManager, StoryStatus
from core.orchestrator import Orchestrator
from agents.test_generator import TestGeneratorAgent
from agents.speculate import SpeculateAgent
from agents.reject import RejectAgent
from agents.requirement import RequirementAgent
from agents.epic import EpicAgent
from agents.story import StoryAgent
from core.llm import LLMClient

app = Flask(__name__, template_folder='templates', static_folder='static')

state_manager = StateManager(ARTIFACTS_DIR / "state")
orchestrator = Orchestrator(ARTIFACTS_DIR)

orchestrator.register_agent("requirement", RequirementAgent())
orchestrator.register_agent("epic", EpicAgent())
orchestrator.register_agent("story", StoryAgent())
orchestrator.register_agent("test_generator", TestGeneratorAgent())


def load_workspace(workspace_id: str):
    return state_manager.load_state(workspace_id)


def get_workspace_story(workspace_id: str, story_id: str):
    state = load_workspace(workspace_id)
    if not state:
        return None, None
    for story in state.stories:
        if story.get('id') == story_id:
            return story, state
    return None, None


@app.route('/')
def index():
    return '<h1>Forward Agent API</h1><p>Go to <a href="/dashboard">/dashboard</a> for the UI</p>'


@app.route('/api/workspaces', methods=['POST'])
def create_workspace():
    data = request.get_json() or {}
    requirement = data.get('requirement', '').strip()
    
    if not requirement:
        return jsonify({'error': 'Requirement is required'}), 400
    
    if not OPENROUTER_API_KEY:
        return jsonify({'error': 'OPENROUTER_API_KEY not configured'}), 500
    
    try:
        result = orchestrator.run_requirement_to_stories(requirement)
        return jsonify({
            'success': True,
            'workspace_id': result['session_id'],
            'message': f'Workspace created with {len(result["stories"].get("stories", []))} stories'
        })
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500


@app.route('/api/workspaces', methods=['GET'])
def list_workspaces():
    workspaces = state_manager.list_states()
    return jsonify(workspaces)


@app.route('/api/workspaces/<workspace_id>', methods=['GET'])
def get_workspace(workspace_id: str):
    state = load_workspace(workspace_id)
    if not state:
        return jsonify({'error': 'Workspace not found'}), 404
    
    workspace_data = state.to_dict()
    return jsonify(workspace_data)


@app.route('/api/workspaces/<workspace_id>/stories', methods=['GET'])
def get_workspace_stories(workspace_id: str):
    state = load_workspace(workspace_id)
    if not state:
        return jsonify({'error': 'Workspace not found'}), 404
    
    return jsonify({
        'workspace_id': workspace_id,
        'stories': state.stories
    })


@app.route('/api/workspaces/<workspace_id>/stories/<story_id>', methods=['GET'])
def get_story(workspace_id: str, story_id: str):
    story, state = get_workspace_story(workspace_id, story_id)
    if not story:
        return jsonify({'error': 'Story not found'}), 404
    
    story_data = dict(story)
    story_data['workspace_id'] = workspace_id
    
    test_file = TESTS_DIR / f"test_{story_id}.py"
    if test_file.exists():
        story_data['test_code'] = test_file.read_text()
    
    return jsonify(story_data)


@app.route('/api/workspaces/<workspace_id>/stories/<story_id>/tests', methods=['POST'])
def generate_tests(workspace_id: str, story_id: str):
    story, state = get_workspace_story(workspace_id, story_id)
    if not story:
        return jsonify({'error': 'Story not found'}), 404
    
    if not OPENROUTER_API_KEY:
        return jsonify({'error': 'OPENROUTER_API_KEY not configured'}), 500
    
    try:
        test_agent = TestGeneratorAgent()
        result = test_agent.execute(story)
        
        test_file = TESTS_DIR / f"test_{story_id}.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        with open(test_file, 'w') as f:
            f.write(result.get('test_code', ''))
        
        if state:
            for s in state.stories:
                if s.get('id') == story_id:
                    s['status'] = StoryStatus.TESTS_GENERATED.value
            state_manager.save_state(workspace_id)
        
        return jsonify({'success': True, 'test_code': result.get('test_code', '')})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/workspaces/<workspace_id>/stories/<story_id>/approve', methods=['POST'])
def approve_story(workspace_id: str, story_id: str):
    story, state = get_workspace_story(workspace_id, story_id)
    if not story:
        return jsonify({'error': 'Story not found'}), 404
    
    success = state_manager.update_story_status(workspace_id, story_id, StoryStatus.APPROVED)
    if success:
        return jsonify({'success': True, 'message': 'Story approved'})
    return jsonify({'error': 'Failed to approve story'}), 500


@app.route('/api/workspaces/<workspace_id>/stories/<story_id>/reject', methods=['POST'])
def reject_story(workspace_id: str, story_id: str):
    story, state = get_workspace_story(workspace_id, story_id)
    if not story:
        return jsonify({'error': 'Story not found'}), 404
    
    data = request.get_json() or {}
    feedback = data.get('feedback', '').strip()
    apply_changes = data.get('apply_changes', False)
    
    if not feedback:
        return jsonify({'error': 'Feedback is required'}), 400
    
    try:
        state = load_workspace(workspace_id)
        if not state:
            return jsonify({'error': 'Workspace not found'}), 404
        
        reject_agent = RejectAgent()
        result = reject_agent.execute(story, feedback, state)
        
        if apply_changes:
            rejection_data = {
                'user_feedback': feedback,
                'analysis': result.get('analysis', {}),
                'dependency_warnings': result.get('dependency_warnings', []),
                'scope_changes': result.get('scope_changes', {}),
                'updated': True
            }
            
            success = state_manager.update_story_status(
                workspace_id, 
                story_id, 
                StoryStatus.REJECTED, 
                json.dumps(rejection_data)
            )
            state_manager.save_state(workspace_id)
            
            if success:
                return jsonify({
                    'success': True,
                    'applied': True,
                    'analysis': result.get('analysis', {}),
                    'updated_summary': result.get('updated_summary', ''),
                    'scope_changes': result.get('scope_changes', {}),
                    'updated_scope': result.get('updated_scope', []),
                    'dependency_warnings': result.get('dependency_warnings', []),
                    'message': 'Story rejected with updated project requirements'
                })
        
        return jsonify({
            'success': True,
            'requires_confirmation': True,
            'analysis': result.get('analysis', {}),
            'updated_summary': result.get('updated_summary', ''),
            'scope_changes': result.get('scope_changes', {}),
            'updated_scope': result.get('updated_scope', []),
            'rejected_stories': result.get('rejected_stories', []),
            'dependency_warnings': result.get('dependency_warnings', []),
            'requirements_file': result.get('requirements_file', ''),
            'message': 'Review rejection analysis and apply changes'
        })
        
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500


@app.route('/api/workspaces/<workspace_id>/stories/<story_id>/speculate', methods=['POST'])
def speculate_story(workspace_id: str, story_id: str):
    story, state = get_workspace_story(workspace_id, story_id)
    if not story:
        return jsonify({'error': 'Story not found'}), 404
    
    if not OPENROUTER_API_KEY:
        return jsonify({'error': 'OPENROUTER_API_KEY not configured'}), 500
    
    data = request.get_json() or {}
    feedback = data.get('feedback', '').strip()
    confirm_complex = data.get('confirm_complex', False)
    
    if len(feedback) < 10:
        return jsonify({'error': 'Feedback must be at least 10 characters'}), 400
    
    try:
        state = load_workspace(workspace_id)
        if not state:
            return jsonify({'error': 'Workspace not found'}), 404
        
        existing_epic_ids = []
        existing_story_ids = []
        if state.stories:
            existing_story_ids = [s.get('id') for s in state.stories]
        
        epic_file = EPICS_DIR / f"{workspace_id}.json"
        if epic_file.exists():
            with open(epic_file, 'r') as f:
                existing_data = json.load(f)
                existing_epic_ids = [e.get('id') for e in existing_data.get('epics', [])]
        
        context = {
            "existing_epic_ids": existing_epic_ids,
            "existing_story_ids": existing_story_ids,
            "epic_id": story.get('epic_id')
        }
        
        speculate_agent = SpeculateAgent()
        result = speculate_agent.execute(feedback=feedback, story=story, context=context)
        
        change_type = result.get('change_type', 'simple')
        
        if change_type == 'simple':
            new_notes = result.get('technical_notes', '')
            
            if not new_notes or len(new_notes.strip()) < 10:
                new_notes = f"Incorporating feedback: {feedback}"
            
            for s in state.stories:
                if s.get('id') == story_id:
                    s['technical_notes'] = new_notes
            state_manager.save_state(workspace_id)
            
            return jsonify({
                'success': True,
                'change_type': 'simple',
                'technical_notes': new_notes,
                'reasoning': result.get('reasoning', ''),
                'message': 'Technical notes updated'
            })
        
        else:
            if not confirm_complex:
                return jsonify({
                    'success': True,
                    'change_type': 'complex',
                    'requires_confirmation': True,
                    'reasoning': result.get('reasoning', ''),
                    'message': 'This feedback requires creating new epic/stories. Confirm to proceed.'
                })
            
            try:
                requirement_agent = RequirementAgent()
                requirement_result = requirement_agent.execute(feedback)
                
                epic_agent = EpicAgent()
                epic_result = epic_agent.execute(requirement_result)
                
                story_agent = StoryAgent()
                story_result = story_agent.execute(epic_result)
                
                new_epics = epic_result.get('epics', [])
                new_stories = story_result.get('stories', [])
                
                if not new_epics or not new_stories:
                    return jsonify({
                        'error': 'Complex change - agents did not generate epics or stories',
                        'requirement_result': requirement_result,
                        'epic_result': epic_result
                    }), 500
                
                next_epic_num = 1
                if existing_epic_ids:
                    for eid in existing_epic_ids:
                        if eid.startswith('EPIC-'):
                            try:
                                num = int(eid.split('-')[1])
                                next_epic_num = max(next_epic_num, num + 1)
                            except ValueError:
                                pass
                
                saved_epic_ids = []
                for epic in new_epics:
                    epic_id = f'EPIC-{next_epic_num}'
                    next_epic_num += 1
                    saved_epic_ids.append(epic_id)
                    epic['id'] = epic_id
                
                epic_stories_map = {epic['id']: [] for epic in new_epics}
                
                next_story_num = state.get_next_story_number()
                saved_story_ids = []
                for story_data in new_stories:
                    story_id_new = f'STORY-{next_story_num}'
                    next_story_num += 1
                    story_data['id'] = story_id_new
                    story_data['dependencies'] = []
                    saved_story_ids.append(story_id_new)
                    
                    original_epic_id = story_data.get('epic_id', '')
                    if original_epic_id in epic_stories_map:
                        epic_stories_map[original_epic_id].append(story_id_new)
                    
                    state.add_story(story_data)
                
                epic_file.parent.mkdir(parents=True, exist_ok=True)
                
                existing_epics = []
                if epic_file.exists():
                    with open(epic_file, 'r') as f:
                        existing_data = json.load(f)
                        existing_epics = existing_data.get('epics', [])
                
                for epic in new_epics:
                    epic['stories'] = epic_stories_map.get(epic['id'], [])
                    existing_epics.append(epic)
                
                with open(epic_file, 'w') as f:
                    json.dump({'epics': existing_epics}, f, indent=2)
                
                primary_new_story_id = saved_story_ids[0] if saved_story_ids else None
                if primary_new_story_id:
                    state.add_dependency(story_id, primary_new_story_id)
                
                state_manager.save_state(workspace_id)
                
                return jsonify({
                    'success': True,
                    'change_type': 'complex',
                    'new_epics': new_epics,
                    'new_stories': new_stories,
                    'dependency_added': primary_new_story_id,
                    'reasoning': result.get('reasoning', ''),
                    'message': f'New story {primary_new_story_id} created as dependency'
                })
            except Exception as e:
                import traceback
                return jsonify({'error': f'Agent pipeline error: {str(e)}', 'trace': traceback.format_exc()}), 500
            
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500


@app.route('/api/workspaces/<workspace_id>/stories/<story_id>', methods=['DELETE'])
def delete_story(workspace_id: str, story_id: str):
    story, state = get_workspace_story(workspace_id, story_id)
    if not story:
        return jsonify({'error': 'Story not found'}), 404
    
    if not state:
        return jsonify({'error': 'Workspace not found'}), 404
    
    success = state.remove_story(story_id)
    if success:
        state_manager.save_state(workspace_id)
        
        epic_file = EPICS_DIR / f"{workspace_id}.json"
        if epic_file.exists():
            with open(epic_file, 'r') as f:
                epics_data = json.load(f)
            
            for epic in epics_data.get('epics', []):
                if 'stories' in epic and story_id in epic['stories']:
                    epic['stories'].remove(story_id)
            
            with open(epic_file, 'w') as f:
                json.dump(epics_data, f, indent=2)
        
        return jsonify({
            'success': True,
            'message': f'Story {story_id} deleted'
        })
    
    return jsonify({'error': 'Failed to delete story'}), 500


@app.route('/api/workspaces/<workspace_id>/epics/<epic_id>', methods=['DELETE'])
def delete_epic(workspace_id: str, epic_id: str):
    state = load_workspace(workspace_id)
    if not state:
        return jsonify({'error': 'Workspace not found'}), 404
    
    epic_file = EPICS_DIR / f"{workspace_id}.json"
    if not epic_file.exists():
        return jsonify({'error': 'Epics file not found'}), 404
    
    with open(epic_file, 'r') as f:
        epics_data = json.load(f)
    
    epics = epics_data.get('epics', [])
    epic_to_delete = None
    for epic in epics:
        if epic.get('id') == epic_id:
            epic_to_delete = epic
            break
    
    if not epic_to_delete:
        return jsonify({'error': f'Epic {epic_id} not found'}), 404
    
    epics = [e for e in epics if e.get('id') != epic_id]
    with open(epic_file, 'w') as f:
        json.dump({'epics': epics}, f, indent=2)
    
    removed_story_ids = state_manager.remove_stories_by_epic(workspace_id, epic_id)
    
    return jsonify({
        'success': True,
        'message': f'Epic {epic_id} and {len(removed_story_ids)} associated stories deleted',
        'deleted_epic': epic_id,
        'deleted_stories': removed_story_ids
    })


@app.route('/api/workspaces/<workspace_id>/epics', methods=['GET'])
def get_workspace_epics(workspace_id: str):
    state = load_workspace(workspace_id)
    if not state:
        return jsonify({'error': 'Workspace not found'}), 404
    
    epics_file = EPICS_DIR / f"{workspace_id}.json"
    if not epics_file.exists():
        return jsonify({'error': 'Epics not found for this workspace'}), 404
    
    with open(epics_file, 'r') as f:
        epics_data = json.load(f)
    
    epics = epics_data.get('epics', [])
    
    for epic in epics:
        epic['stories'] = [s for s in state.stories if s.get('epic_id') == epic.get('id')]
    
    return jsonify({
        'workspace_id': workspace_id,
        'epics': epics
    })


@app.route('/api/stats', methods=['GET'])
def get_stats():
    workspaces = state_manager.list_states()
    
    total_stories = 0
    approved = 0
    rejected = 0
    pending = 0
    
    for workspace in workspaces:
        state = load_workspace(workspace['workspace_id'])
        if state and state.stories:
            for story in state.stories:
                total_stories += 1
                status = story.get('status', 'pending')
                if status == StoryStatus.APPROVED.value:
                    approved += 1
                elif status == StoryStatus.REJECTED.value:
                    rejected += 1
                else:
                    pending += 1
    
    return jsonify({
        'total_workspaces': len(workspaces),
        'total_stories': total_stories,
        'approved': approved,
        'rejected': rejected,
        'pending': pending
    })


@app.route('/dashboard')
def dashboard():
    workspaces_data = []
    workspaces = state_manager.list_states()
    for workspace in workspaces:
        state = load_workspace(workspace['workspace_id'])
        if state:
            workspaces_data.append({
                'workspace_id': workspace['workspace_id'],
                'requirement': workspace['requirement'],
                'status': workspace['status'],
                'story_count': workspace['story_count'],
                'created_at': workspace['created_at'],
                'stories': state.stories
            })
    return render_template('dashboard.html', workspaces=workspaces_data)


@app.route('/dashboard/<workspace_id>/story/<story_id>')
def story_detail(workspace_id: str, story_id: str):
    story, state = get_workspace_story(workspace_id, story_id)
    if not story:
        return "Story not found", 404
    
    test_file = TESTS_DIR / f"test_{story_id}.py"
    test_code = test_file.read_text() if test_file.exists() else None
    
    return render_template('story.html', 
                          story=story, 
                          test_code=test_code, 
                          workspace_id=workspace_id)


@app.template_filter('get_status_class')
def get_status_class(status):
    mapping = {
        'approved': 'bg-green-100 text-green-800',
        'rejected': 'bg-red-100 text-red-800',
        'tests_generated': 'bg-blue-100 text-blue-800',
        'generated': 'bg-yellow-100 text-yellow-800',
        'pending': 'bg-gray-100 text-gray-800'
    }
    return mapping.get(status, 'bg-gray-100 text-gray-800')


if __name__ == '__main__':
    print("=" * 50)
    print("Forward Agent Dashboard")
    print("=" * 50)
    print("Dashboard: http://localhost:8080/dashboard")
    print("API: http://localhost:8080/api/")
    print("=" * 50)
    app.run(host='0.0.0.0', port=8080, debug=True)
