# src/dialogue/__init__.py
"""
Intelligent dialogue system.

Provides natural language driven interaction with concept learning.
"""

from src.dialogue.concept_recognizer import ConceptRecognizer
from src.dialogue.dialogue_engine import DialogueEngine, DialogueState, DialogueResponse
from src.dialogue.question_generator import QuestionGenerator
from src.dialogue.startup_wizard import StartupWizard

__all__ = [
    "ConceptRecognizer",
    "DialogueEngine",
    "DialogueResponse",
    "DialogueState",
    "QuestionGenerator",
    "StartupWizard",
]
