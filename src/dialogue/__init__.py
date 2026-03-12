# src/dialogue/__init__.py
"""
Intelligent dialogue system.

Provides natural language driven interaction with concept learning.

Note: DialogueEngine has been DEPRECATED.
Use Orchestrator from src.agents.orchestrator instead.
See docs/migration/dialogue-engine-to-orchestrator.md for migration guide.
"""

from src.dialogue.concept_recognizer import ConceptRecognizer, RecognizedConcept
from src.dialogue.question_generator import QuestionGenerator, ClarificationQuestion
from src.dialogue.startup_wizard import StartupWizard

# DialogueEngine已废弃，请使用Orchestrator
# 如需向后兼容，可从 dialogue_engine 导入，但会收到 DeprecationWarning
from src.dialogue.dialogue_engine import (
    DialogueEngine,
    DialogueState,
    DialogueResponse,
)

__all__ = [
    "ConceptRecognizer",
    "RecognizedConcept",
    "QuestionGenerator",
    "ClarificationQuestion",
    "StartupWizard",
    # Deprecated - kept for backward compatibility
    "DialogueEngine",
    "DialogueState",
    "DialogueResponse",
]
