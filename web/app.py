import os
import json
from pathlib import Path
from flask import Flask, render_template, jsonify, request
from config.settings import ARTIFACTS_DIR, STORIES_DIR, TESTS_DIR, EPICS_DIR, OPENROUTER_API_KEY
from core.state import StateManager, StoryStatus
from core.orchestrator import Orchestrator
from agents.test_generator import TestGeneratorAgent
from agents.collaborate import CollaborateAgent
from core.llm import LLMClient

app = Flask(__name__, template_folder='templates', static_folder='static')

state_manager = StateManager(ARTIFACTS_DIR / "state")


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


@app.route('/api/stories/<story_id>/collaborate', methods=['POST'])
def collaborate_story(story_id: str):
    story, session_id = load_story_from_all_sessions(story_id)
    if not story:
        return jsonify({'error': 'Story not found'}), 404
    
    if not OPENROUTER_API_KEY:
        return jsonify({'error': 'OPENROUTER_API_KEY not configured'}), 500
    
    data = request.get_json() or {}
    user_prompt = data.get('prompt', '').strip()
    
    if not user_prompt:
        return jsonify({'error': 'Prompt is required'}), 400
    
    try:
        current_notes = story.get('technical_notes', '')
        
        collaborate_agent = CollaborateAgent()
        result = collaborate_agent.execute(current_notes, user_prompt)
        
        new_notes = result.get('technical_notes', current_notes)
        
        state = load_session(session_id)
        if state:
            for s in state.stories:
                if s.get('id') == story_id:
                    s['technical_notes'] = new_notes
            state_manager.save_state(session_id)
        
        return jsonify({
            'success': True,
            'updated_notes': new_notes,
            'change_type': result.get('change_type', 'modify'),
            'summary': result.get('summary', 'Updated technical notes')
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


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