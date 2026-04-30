"""Thin adapter that drives the production chatbot for evaluation purposes.

The evaluation framework needs to drive the same code paths that real users
hit (``Chatbot.get_response`` and ``DeltaGenerator.get_delta``) without
depending on the Flask request context.
"""

from __future__ import annotations

from typing import Optional

from chat import Chatbot
from delta import DeltaGenerator


# Canonical prompts used to invoke each interaction mode.
SUMMARY_PROMPT = (
    "Please produce a plain-language summary of these Terms of Service. "
    "Confirm the service name, walk through the key provisions, and flag any "
    "clauses that may be harmful to the user."
)


class ChatbotUnderTest:
    """Wraps the production chatbot/delta classes for repeatable evaluation."""

    def __init__(
        self,
        chatbot: Optional[Chatbot] = None,
        delta_generator: Optional[DeltaGenerator] = None,
    ):
        self.chatbot = chatbot or Chatbot()
        self.delta_generator = delta_generator or DeltaGenerator()

    def first_contact_summary(self, service_name: str, current_tos: str) -> str:
        """Drive the first-contact protocol: summary + harm flagging."""
        return self.chatbot.get_response(
            user_input=SUMMARY_PROMPT,
            history=[],
            service_name=service_name,
            current_tos=current_tos,
            previous_tos=None,
            delta=None,
        )

    def delta_summary(
        self,
        service_name: str,
        old_version: str,
        new_version: str,
    ) -> tuple:
        """Drive the returning-user protocol: delta + harm flagging.

        Returns ``(delta_bullets, narrative_response)``.
        """
        delta_bullets = self.delta_generator.get_delta(old_version, new_version) or ""
        narrative = self.chatbot.get_response(
            user_input=(
                "The Terms of Service have been updated. Walk me through what "
                "changed and flag any new clauses that may harm me."
            ),
            history=[],
            service_name=service_name,
            current_tos=new_version,
            previous_tos=old_version,
            delta=delta_bullets,
        )
        return delta_bullets, narrative

    def follow_up(
        self,
        service_name: str,
        current_tos: str,
        previous_tos: Optional[str],
        delta: Optional[str],
        question: str,
        history: Optional[list] = None,
    ) -> str:
        return self.chatbot.get_response(
            user_input=question,
            history=history or [],
            service_name=service_name,
            current_tos=current_tos,
            previous_tos=previous_tos,
            delta=delta,
        )