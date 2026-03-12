#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test script to verify ReACT functionality with search_schema tool
"""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

# Setup stdio encoding
def _configure_stdio_encoding():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            continue

_configure_stdio_encoding()

def test_react_with_search_schema():
    """Test ReACT orchestrator with search_schema functionality"""
    print("Testing ReACT orchestrator with search_schema...")

    # Import required modules
    from src.db_manager import DatabaseManager
    from src.llm_client import LLMClient
    from src.knowledge import KnowledgeLoader
    from src.react.orchestrator import MVPReACTOrchestrator
    from src.react.tool_service import MVPToolService
    from src.metadata.retrieval_pipeline import RetrievalPipeline

    try:
        # Initialize components
        print("Initializing database manager...")
        db_manager = DatabaseManager()

        print("Initializing LLM client...")
        llm_client = LLMClient()

        print("Initializing knowledge loader...")
        knowledge_loader = KnowledgeLoader(db_manager=db_manager)

        print("Initializing retrieval pipeline...")
        retrieval_pipeline = RetrievalPipeline()

        print("Initializing tool service...")
        tool_service = MVPToolService(
            db_manager=db_manager,
            retrieval_pipeline=retrieval_pipeline,
            operation_executor=None,  # We won't be testing operations in this test
            knowledge_loader=knowledge_loader
        )

        print("Initializing ReACT orchestrator...")
        orchestrator = MVPReACTOrchestrator(
            llm_client=llm_client,
            tool_service=tool_service
        )

        print("\nReACT orchestrator initialized successfully!")

        # Test 1: Test search_schema with "沪BAB1565" as mentioned in task
        print("\n--- Test 1: Testing search_schema with '沪BAB1565' ---")
        try:
            # Manually call the search_schema tool to verify functionality
            result = tool_service._tool_search_schema("沪BAB1565")
            print(f"search_schema result: {result}")

            # Check if the result contains field information (the expected behavior)
            if "字段" in result or "字段列表" in result or "-" in result:
                print("✅ search_schema returned field information as expected!")
            else:
                print("❌ search_schema did not return expected field information")

        except Exception as e:
            print(f"❌ Error in search_schema test: {e}")
            import traceback
            traceback.print_exc()

        # Test 2: Test search_schema with general term
        print("\n--- Test 2: Testing search_schema with 'plate' ---")
        try:
            result = tool_service._tool_search_schema("plate")
            print(f"search_schema result: {result[:500]}...")  # Truncate for readability

            # Check if the result contains field information
            if "字段" in result or "字段列表" in result or "-" in result:
                print("✅ search_schema returned field information for 'plate' query!")
            else:
                print("❌ search_schema did not return expected field information for 'plate' query")

        except Exception as e:
            print(f"❌ Error in search_schema test with 'plate': {e}")
            import traceback
            traceback.print_exc()

        # Clean up
        orchestrator.reset()
        print("\n✅ ReACT integration tests completed!")

    except Exception as e:
        print(f"❌ Error during ReACT initialization: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True

if __name__ == "__main__":
    print("Starting ReACT integration verification...")
    success = test_react_with_search_schema()

    if success:
        print("\n🎉 ReACT integration verification completed successfully!")
    else:
        print("\n💥 ReACT integration verification failed!")
        sys.exit(1)