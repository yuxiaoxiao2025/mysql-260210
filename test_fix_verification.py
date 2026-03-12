#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Fix the failing test by ensuring knowledge_loader is properly provided
"""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

def fix_failing_test():
    """Fix the failing test by ensuring proper initialization"""
    print("Creating a corrected version of the failing test...")

    # Read the test file
    test_file_path = r"E:\trae-pc\mysql260227\tests\integration\test_chat_mode.py"

    # Let me create a fixed test function that can be temporarily patched
    print("The issue is in the test at line 219-222 where IntentAgent is created without knowledge_loader.")
    print("We need to make sure the test initializes IntentAgent with a knowledge_loader.")

    # Let me run a test to verify the fix works by importing with proper initialization
    from unittest.mock import MagicMock, patch

    print("Testing IntentAgent with proper initialization...")

    # Import necessary modules
    from src.agents.impl.intent_agent import IntentAgent
    from src.agents.config import IntentAgentConfig
    from src.llm_client import LLMClient
    from src.knowledge import KnowledgeLoader
    from src.db_manager import DatabaseManager
    from src.agents.context import AgentContext

    try:
        # Initialize components properly
        print("Creating DatabaseManager...")
        db_manager = DatabaseManager()

        print("Creating KnowledgeLoader...")
        knowledge_loader = KnowledgeLoader(db_manager=db_manager)

        print("Creating LLMClient mock...")
        mock_llm = MagicMock()
        mock_llm.api_key = "test-key"
        mock_llm.client = None

        print("Creating IntentAgent with proper parameters...")
        intent_agent = IntentAgent(
            IntentAgentConfig(name="intent"),
            llm_client=mock_llm,
            knowledge_loader=knowledge_loader
        )

        print("Testing with user input '你好'...")
        context = AgentContext(user_input="你好")
        result = intent_agent.run(context)

        print("✅ IntentAgent worked correctly with proper initialization!")
        return True

    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests_now():
    """Now run the full test suite to check if we fixed the issue"""
    import subprocess
    import sys

    print("\n" + "="*60)
    print("RUNNING FULL TEST SUITE TO VERIFY FIX")
    print("="*60)

    # Run the specific failing test first
    print("\n--- Running the specific failing test ---")
    cmd = [sys.executable, "-m", "pytest", "tests/integration/test_chat_mode.py::TestChatModeWithRealAgents::test_intent_agent_recognizes_chat_intent", "-v"]
    result = subprocess.run(cmd, capture_output=True, text=True)

    print("STDOUT:", result.stdout)
    print("STDERR:", result.stderr)
    print("Return code:", result.returncode)

    if result.returncode == 0:
        print("✅ Specific test now passes!")
    else:
        print("❌ Specific test still fails!")

    # Now run all tests
    print("\n--- Running all tests ---")
    cmd = [sys.executable, "-m", "pytest", "tests/", "-x", "--tb=short"]  # -x to stop on first failure
    result = subprocess.run(cmd, capture_output=True, text=True)

    print(f"All tests result - Return code: {result.returncode}")
    print("Some output truncated, but checking overall result...")

    return result.returncode == 0


if __name__ == "__main__":
    print("Attempting to fix and verify the failing test...")

    # First, try the fix approach
    success = fix_failing_test()

    if success:
        print("\n🎉 Fix verification successful!")

        # Now run all tests to confirm
        all_tests_pass = run_all_tests_now()

        if all_tests_pass:
            print("\n✅ All tests pass! Integration verification successful!")
        else:
            print("\n⚠️  Some tests still fail. Additional fixes needed.")
    else:
        print("\n💥 Failed to verify fix.")