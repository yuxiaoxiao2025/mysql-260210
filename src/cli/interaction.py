"""CLI interaction module for user feedback."""

from typing import Optional


class Interaction:
    """Handle user interactions and feedback in CLI."""

    def __init__(self, input_func=input):
        """Initialize Interaction handler.

        Args:
            input_func: Function to use for getting user input.
                       Defaults to built-in input().
        """
        self.input_func = input_func

    def ask_feedback(
        self,
        prompt: Optional[str] = None
    ) -> str:
        """Ask user for feedback on query results.

        Args:
            prompt: Optional custom prompt message.
                   Defaults to asking for y/n/correction.

        Returns:
            User's response as a string.
        """
        if prompt is None:
            prompt = "Is this correct? (y/n/correction): "

        return self.input_func(prompt).strip()

    def confirm_action(
        self,
        action_description: str
    ) -> bool:
        """Ask user to confirm an action.

        Args:
            action_description: Description of the action to confirm.

        Returns:
            True if user confirms, False otherwise.
        """
        prompt = f"Confirm {action_description}? (y/n): "
        response = self.input_func(prompt).strip().lower()
        return response in ('y', 'yes')
