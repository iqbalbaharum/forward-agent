import os
import json
from pathlib import Path
from flask import Flask, render_template, jsonify, request
from config.settings import ARTIFACTS_DIR, STORIES_DIR, TESTS_DIR, EPICS_DIR, OPENROUTER_API_KEY
from core.state import StateManager, StoryStatus
from core.orchestrator import Orchestrator
from agents.test_generator import TestGeneratorAgent
from agents.speculate import SpeculateAgent
from agents.requirement import RequirementAgent
from agents.epic import EpicAgent
from agents.story import StoryAgent
from core.llm import LLMClient
import json

app = Flask(__name__, template_folder='templates', static_folder='static')

state_manager = StateManager(ARTIFACTS_DIR / "state")
orchestrator = Orchestrator(ARTIFACTS_DIR)

from agents.requirement import RequirementAgent
from agents.epic import EpicAgent
from agents.story import StoryAgent
from agents.test_generator import TestGeneratorAgent

orchestrator.register_agent("requirement", RequirementAgent())
orchestrator.register_agent("epic", EpicAgent())
orchestrator.register_agent("story", StoryAgent())
orchestrator.register_agent("test_generator", TestGeneratorAgent())


def load_session(session_id: str):
    return state_manager.load_state(session_id)


def load_story_from_all_sessions(story_id: str):
    for session_file in (ARTIFACTS_DIR / "state").glob("*.json"):
        state = state_manager.load_state(session_file.stem)
        if state:
            for story in state.stories:
                if story.get('id') == story_id:
                    return story, state.session_id
    return None, None


@app.route('/')
def index():
    return '<h1>Forward Agent API</h1><p>Go to <a href="/dashboard">/dashboard</a> for the UI</p>'


@app.route('/api/sessions', methods=['POST'])
def create_session():
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
            'session_id': result['session_id'],
            'message': f'Session created with {len(result["stories"].get("stories", []))} stories'
        })
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500


@app.route('/dashboard')
def dashboard():
    sessions_data = []
    sessions = state_manager.list_states()
    for session in sessions:
        state = load_session(session['session_id'])
        if state:
            sessions_data.append({
                'session_id': session['session_id'],
                'requirement': session['requirement'],
                'status': session['status'],
                'story_count': session['story_count'],
                'created_at': session['created_at'],
                'stories': state.stories
            })
    return render_template('dashboard.html', sessions=sessions_data)


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


@app.route('/dashboard/story/<story_id>')
def story_detail(story_id: str):
    story, session_id = load_story_from_all_sessions(story_id)
    if not story:
        return "Story not found", 404
    
    test_file = TESTS_DIR / f"test_{story_id}.py"
    test_code = test_file.read_text() if test_file.exists() else None
    
    return render_template('story.html', story=story, test_code=test_code, session_id=session_id)


@app.route('/api/sessions', methods=['GET'])
def list_sessions():
    sessions = state_manager.list_states()
    return jsonify(sessions)


@app.route('/api/sessions/<session_id>', methods=['GET'])
def get_session(session_id: str):
    state = load_session(session_id)
    if not state:
        return jsonify({'error': 'Session not found'}), 404
    
    session_data = state.to_dict()
    return jsonify(session_data)


@app.route('/api/stories/<story_id>', methods=['GET'])
def get_story(story_id: str):
    story, session_id = load_story_from_all_sessions(story_id)
    if not story:
        return jsonify({'error': 'Story not found'}), 404
    
    story['session_id'] = session_id
    
    test_file = TESTS_DIR / f"test_{story_id}.py"
    if test_file.exists():
        story['test_code'] = test_file.read_text()
    
    return jsonify(story)


@app.route('/api/stories/<story_id>/tests', methods=['POST'])
def generate_tests(story_id: str):
    story, session_id = load_story_from_all_sessions(story_id)
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
        
        state = load_session(session_id)
        if state:
            for s in state.stories:
                if s.get('id') == story_id:
                    s['status'] = StoryStatus.TESTS_GENERATED.value
            state_manager.save_state(session_id)
        
        return jsonify({'success': True, 'test_code': result.get('test_code', '')})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/stories/<story_id>/approve', methods=['POST'])
def approve_story(story_id: str):
    story, session_id = load_story_from_all_sessions(story_id)
    if not story:
        return jsonify({'error': 'Story not found'}), 404
    
    success = state_manager.update_story_status(session_id, story_id, StoryStatus.APPROVED)
    if success:
        return jsonify({'success': True, 'message': 'Story approved'})
    return jsonify({'error': 'Failed to approve story'}), 500


@app.route('/api/stories/<story_id>/reject', methods=['POST'])
def reject_story(story_id: str):
    story, session_id = load_story_from_all_sessions(story_id)
    if not story:
        return jsonify({'error': 'Story not found'}), 404
    
    data = request.get_json() or {}
    feedback = data.get('feedback', '')
    
    success = state_manager.update_story_status(session_id, story_id, StoryStatus.REJECTED, feedback)
    if success:
        return jsonify({'success': True, 'message': 'Story rejected'})
    return jsonify({'error': 'Failed to reject story'}), 500


@app.route('/api/stories/<story_id>/speculate', methods=['POST'])
def speculate_story(story_id: str):
    story, session_id = load_story_from_all_sessions(story_id)
    if not story:
        return jsonify({'error': 'Story not found'}), 404
    
    if not OPENROUTER_API_KEY:
        return jsonify({'error': 'OPENROUTER_API_KEY not configured'}), 500
    
    data = request.get_json() or {}
    feedback = data.get('feedback', '').strip()
    
    if len(feedback) < 10:
        return jsonify({'error': 'Feedback must be at least 10 characters'}), 400
    
    try:
        speculate_agent = SpeculateAgent()
        result = speculate_agent.execute(feedback=feedback, story=story)
        
        change_type = result.get('change_type', 'simple')
        
        state = load_session(session_id)
        if not state:
            return jsonify({'error': 'Session not found'}), 404
        
        if change_type == 'simple':
            new_notes = result.get('technical_notes', story.get('technical_notes', ''))
            
            for s in state.stories:
                if s.get('id') == story_id:
                    s['technical_notes'] = new_notes
            state_manager.save_state(session_id)
            
            return jsonify({
                'success': True,
                'change_type': 'simple',
                'technical_notes': new_notes,
                'reasoning': result.get('reasoning', ''),
                'message': 'Technical notes updated'
            })
        
        else:
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
                
                saved_epic_ids = []
                for epic in new_epics:
                    epic_id = epic.get('id', f'EPIC-{len(state.stories) + 1}')
                    saved_epic_ids.append(epic_id)
                    epic['id'] = epic_id
                
                epic_stories_map = {}
                for epic in new_epics:
                    epic_stories_map[epic['id']] = []
                
                saved_story_ids = []
                for story_data in new_stories:
                    story_id_new = story_data.get('id', f'STORY-{state.get_next_story_number()}')
                    story_data['id'] = story_id_new
                    story_data['dependencies'] = []
                    saved_story_ids.append(story_id_new)
                    
                    epic_id = story_data.get('epic_id')
                    if epic_id and epic_id in epic_stories_map:
                        epic_stories_map[epic_id].append(story_id_new)
                    
                    state.add_story(story_data)
                
                epic_file = EPICS_DIR / f"{session_id}.json"
                epic_file.parent.mkdir(parents=True, exist_ok=True)
                
                existing_epics = []
                if epic_file.exists():
                    with open(epic_file, 'r') as f:
                        existing_data = json.load(f)
                        existing_epics = existing_data.get('epics', [])
                
                for epic in new_epics:
                    epic_id = epic['id']
                    epic['stories'] = epic_stories_map.get(epic_id, [])
                    existing_epics.append(epic)
                
                with open(epic_file, 'w') as f:
                    json.dump({'epics': existing_epics}, f, indent=2)
                
                primary_new_story_id = saved_story_ids[0] if saved_story_ids else None
                if primary_new_story_id:
                    state.add_dependency(story_id, primary_new_story_id)
                
                state_manager.save_state(session_id)
                
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


@app.route('/api/stories/<story_id>', methods=['DELETE'])
def delete_story(story_id: str):
    story, session_id = load_story_from_all_sessions(story_id)
    if not story:
        return jsonify({'error': 'Story not found'}), 404
    
    state = load_session(session_id)
    if not state:
        return jsonify({'error': 'Session not found'}), 404
    
    success = state.remove_story(story_id)
    if success:
        state_manager.save_state(session_id)
        
        epic_file = EPICS_DIR / f"{session_id}.json"
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


@app.route('/api/sessions/<session_id>/epics/<epic_id>', methods=['DELETE'])
def delete_epic(session_id: str, epic_id: str):
    state = load_session(session_id)
    if not state:
        return jsonify({'error': 'Session not found'}), 404
    
    epic_file = EPICS_DIR / f"{session_id}.json"
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
    
    story_ids = epic_to_delete.get('stories', [])
    
    epics = [e for e in epics if e.get('id') != epic_id]
    with open(epic_file, 'w') as f:
        json.dump({'epics': epics}, f, indent=2)
    
    removed_story_ids = state_manager.remove_stories_by_epic(session_id, epic_id)
    
    return jsonify({
        'success': True,
        'message': f'Epic {epic_id} and {len(removed_story_ids)} associated stories deleted',
        'deleted_epic': epic_id,
        'deleted_stories': removed_story_ids
    })


@app.route('/api/sessions/<session_id>/epics', methods=['GET'])
def get_session_epics(session_id: str):
    state = load_session(session_id)
    if not state:
        return jsonify({'error': 'Session not found'}), 404
    
    epics_file = EPICS_DIR / f"{session_id}.json"
    if not epics_file.exists():
        return jsonify({'error': 'Epics not found for this session'}), 404
    
    with open(epics_file, 'r') as f:
        epics_data = json.load(f)
    
    epics = epics_data.get('epics', [])
    
    for epic in epics:
        epic['stories'] = [s for s in state.stories if s.get('epic_id') == epic.get('id')]
    
    return jsonify({
        'session_id': session_id,
        'epics': epics
    })


@app.route('/api/sessions/<session_id>/stories', methods=['GET'])
def get_session_stories(session_id: str):
    state = load_session(session_id)
    if not state:
        return jsonify({'error': 'Session not found'}), 404
    
    return jsonify({
        'session_id': session_id,
        'stories': state.stories
    })
def get_stats():
    sessions = state_manager.list_states()
    
    total_stories = 0
    approved = 0
    rejected = 0
    pending = 0
    
    for session in sessions:
        state = load_session(session['session_id'])
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
        'total_sessions': len(sessions),
        'total_stories': total_stories,
        'approved': approved,
        'rejected': rejected,
        'pending': pending
    })


if __name__ == '__main__':
    print("=" * 50)
    print("Forward Agent Dashboard")
    print("=" * 50)
    print("Dashboard: http://localhost:8080/dashboard")
    print("API: http://localhost:8080/api/")
    print("=" * 50)
    app.run(host='0.0.0.0', port=8080, debug=True)