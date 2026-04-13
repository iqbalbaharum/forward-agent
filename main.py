#!/usr/bin/env python3
"""
Forward Agent CLI
Agile AI Multi-Agent System - Transform requirements into stories and tests
"""
import click
import json
import sys
from pathlib import Path
from typing import Optional

from core.orchestrator import Orchestrator
from core.state import StoryStatus
from agents.requirement import RequirementAgent
from agents.epic import EpicAgent
from agents.story import StoryAgent
from agents.test_generator import TestGeneratorAgent
from config.settings import (
    STORIES_DIR, TESTS_DIR, ARTIFACTS_DIR, 
    QWEN_API_KEY, QWEN_MODEL
)


def get_orchestrator() -> Orchestrator:
    orch = Orchestrator(ARTIFACTS_DIR)
    orch.register_agent("requirement", RequirementAgent())
    orch.register_agent("epic", EpicAgent())
    orch.register_agent("story", StoryAgent())
    orch.register_agent("test_generator", TestGeneratorAgent())
    return orch


@click.group()
def cli():
    """Forward Agent - Agile AI Multi-Agent System"""
    pass


@cli.command()
@click.argument("requirement")
def new(requirement: str):
    """Submit a new requirement to generate stories"""
    if not QWEN_API_KEY:
        click.echo("Error: QWEN_API_KEY not set in environment or .env file")
        sys.exit(1)
    
    click.echo(f"Processing requirement: {requirement[:50]}...")
    
    orch = get_orchestrator()
    
    try:
        result = orch.run_requirement_to_stories(requirement)
        
        click.echo(f"\n✅ Session created: {result['session_id']}")
        click.echo(f"📋 Stories generated: {len(result['stories'].get('stories', []))}")
        
        click.echo("\n--- Stories Summary ---")
        for story in result['stories'].get('stories', []):
            click.echo(f"  [{story.get('id')}] {story.get('title')} ({story.get('priority', 'N/A')})")
        
        click.echo("\nNext step: Run 'forward-agent tests <story_id>' to generate test scripts")
        
    except Exception as e:
        click.echo(f"Error: {e}")
        sys.exit(1)


@cli.command()
def list():
    """List all sessions and their stories"""
    orch = get_orchestrator()
    sessions = orch.list_sessions()
    
    if not sessions:
        click.echo("No sessions found. Submit a new requirement first.")
        return
    
    for session in sessions:
        click.echo(f"\nSession: {session['session_id']}")
        click.echo(f"  Requirement: {session['requirement']}")
        click.echo(f"  Status: {session['status']}")
        click.echo(f"  Stories: {session['story_count']}")
        
        state = orch.get_state(session['session_id'])
        if state and state.stories:
            click.echo("  Story Status:")
            for story in state.stories:
                status_icon = {
                    "generated": "⏳",
                    "tests_generated": "📝",
                    "approved": "✅",
                    "rejected": "❌",
                    "pending": "⏸️"
                }.get(story.get("status", "pending"), "❓")
                click.echo(f"    {status_icon} {story.get('id')}: {story.get('title', 'N/A')[:40]}")


@cli.command()
@click.argument("story_id")
def view(story_id: str):
    """View story details and test script"""
    state = None
    session_id = None
    
    for session in get_orchestrator().list_sessions():
        state = get_orchestrator().get_state(session['session_id'])
        if state:
            for story in state.stories:
                if story.get('id') == story_id:
                    session_id = session['session_id']
                    break
        if session_id:
            break
    
    if not state:
        click.echo(f"Story {story_id} not found")
        return
    
    story = None
    for s in state.stories:
        if s.get('id') == story_id:
            story = s
            break
    
    if not story:
        click.echo(f"Story {story_id} not found in any session")
        return
    
    click.echo(f"\n{'='*60}")
    click.echo(f"STORY: {story_id}")
    click.echo(f"{'='*60}")
    
    click.echo(f"\nTitle: {story.get('title', 'N/A')}")
    click.echo(f"Epic: {story.get('epic_id', 'N/A')}")
    click.echo(f"Priority: {story.get('priority', 'N/A')}")
    click.echo(f"Story Points: {story.get('story_points', 'N/A')}")
    click.echo(f"Status: {story.get('status', 'N/A')}")
    
    click.echo(f"\nDescription:")
    click.echo(f"  {story.get('description', 'N/A')}")
    
    click.echo(f"\nAcceptance Criteria:")
    for ac in story.get('acceptance_criteria', []):
        click.echo(f"  • {ac}")
    
    if story.get('technical_notes'):
        click.echo(f"\nTechnical Notes:")
        click.echo(f"  {story.get('technical_notes')}")
    
    test_file = TESTS_DIR / f"test_{story_id}.py"
    if test_file.exists():
        click.echo(f"\n--- Test Script ---")
        click.echo(test_file.read_text())
    else:
        click.echo(f"\n⚠️  No test script yet. Run 'forward-agent tests {story_id}' to generate.")


@cli.command()
@click.argument("story_id", required=False)
@click.option("--all", "generate_all", is_flag=True, help="Generate tests for all pending stories")
def tests(story_id: str, generate_all: bool):
    """Generate test scripts for stories"""
    orch = get_orchestrator()
    
    if generate_all:
        sessions = orch.list_sessions()
        for session in sessions:
            state = orch.get_state(session['session_id'])
            if state:
                for story in state.stories:
                    if story.get('status') in [StoryStatus.GENERATED.value, StoryStatus.PENDING.value]:
                        _generate_test(orch, story, session['session_id'])
        click.echo("✅ Tests generated for all pending stories")
        return
    
    if not story_id:
        click.echo("Error: Provide story_id or use --all flag")
        return
    
    for session in orch.list_sessions():
        state = orch.get_state(session['session_id'])
        if state:
            for story in state.stories:
                if story.get('id') == story_id:
                    result = _generate_test(orch, story, session['session_id'])
                    click.echo(f"✅ Test generated for {story_id}")
                    return
    
    click.echo(f"Story {story_id} not found")


def _generate_test(orch, story, session_id):
    result = orch.generate_tests_for_story(session_id, story)
    
    test_dir = TESTS_DIR
    test_dir.mkdir(parents=True, exist_ok=True)
    
    story_id = story.get("id", "unknown")
    with open(test_dir / f"test_{story_id}.py", "w") as f:
        f.write(result.get("test_code", ""))
    
    state = orch.get_state(session_id)
    if state:
        for s in state.stories:
            if s.get('id') == story_id:
                s['status'] = StoryStatus.TESTS_GENERATED.value
        orch.state_manager.save_state(session_id)
    
    return result


@cli.command()
@click.argument("story_id")
def approve(story_id: str):
    """Approve a story"""
    orch = get_orchestrator()
    
    for session in orch.list_sessions():
        state = orch.get_state(session['session_id'])
        if state:
            for story in state.stories:
                if story.get('id') == story_id:
                    if orch.approve_story(session['session_id'], story_id):
                        click.echo(f"✅ Story {story_id} approved")
                        click.echo("   Ready for coding phase (not yet implemented)")
                        return
    
    click.echo(f"Story {story_id} not found")


@cli.command()
@click.argument("story_id")
@click.argument("feedback")
def reject(story_id: str, feedback: str):
    """Reject a story with feedback"""
    orch = get_orchestrator()
    
    for session in orch.list_sessions():
        state = orch.get_state(session['session_id'])
        if state:
            for story in state.stories:
                if story.get('id') == story_id:
                    if orch.reject_story(session['session_id'], story_id, feedback):
                        click.echo(f"❌ Story {story_id} rejected")
                        click.echo(f"   Feedback: {feedback}")
                        return
    
    click.echo(f"Story {story_id} not found")


@cli.command()
def status():
    """Show overall pipeline status"""
    orch = get_orchestrator()
    sessions = orch.list_sessions()
    
    total_stories = 0
    approved = 0
    rejected = 0
    pending = 0
    
    for session in sessions:
        state = orch.get_state(session['session_id'])
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
    
    click.echo(f"\n{'='*40}")
    click.echo("FORWARD AGENT - PIPELINE STATUS")
    click.echo(f"{'='*40}")
    click.echo(f"Total Sessions: {len(sessions)}")
    click.echo(f"Total Stories: {total_stories}")
    click.echo(f"  ✅ Approved: {approved}")
    click.echo(f"  ❌ Rejected: {rejected}")
    click.echo(f"  ⏳ Pending Review: {pending}")
    click.echo(f"{'='*40}")


if __name__ == "__main__":
    cli()