"""Metric rubrics for the DeltaTerms evaluation framework.

Each metric mirrors the rubric in the evaluation plan. Metrics are written so
they can be applied to any of the three interaction modes (first-contact
summary, delta summary, follow-up Q&A) where applicable. The evaluator emits
an integer 0..5 score that is normalized to 0.0..1.0.
"""

from dataclasses import dataclass
from typing import Iterable


# Interaction modes the chatbot supports. Used to gate which metrics run.
MODE_SUMMARY = "summary"        # first-contact summary
MODE_DELTA = "delta"            # delta summary between two ToS versions
MODE_QA = "qa"                  # follow-up question answering

ALL_MODES = (MODE_SUMMARY, MODE_DELTA, MODE_QA)


@dataclass(frozen=True)
class Metric:
    """A single G-Eval style scoring criterion."""

    name: str
    description: str
    rubric: str
    applies_to: tuple

    def applicable(self, mode: str) -> bool:
        return mode in self.applies_to


ANSWER_RELEVANCY = Metric(
    name="answer_relevancy",
    description=(
        "How directly the chatbot's response addresses what the user asked. "
        "Critical during follow-up Q&A."
    ),
    rubric=(
        "5: Response fully addresses the user's question with no extraneous information.\n"
        "4: Response addresses the question with minor tangential content.\n"
        "3: Response partially addresses the question or includes significant tangential content.\n"
        "2: Response only loosely connects to the question.\n"
        "1: Response barely connects to the question.\n"
        "0: Response does not address the question at all."
    ),
    applies_to=ALL_MODES,
)

TASK_COMPLETION = Metric(
    name="task_completion",
    description=(
        "Whether the bot makes meaningful progress toward helping the user "
        "understand their ToS obligations. The 'task' depends on mode: produce "
        "a usable summary, surface a meaningful delta, or resolve a follow-up "
        "question."
    ),
    rubric=(
        "5: User leaves the interaction with clear, actionable understanding.\n"
        "4: User has good understanding with minor gaps.\n"
        "3: User has partial understanding but key gaps remain.\n"
        "2: User has only fragmentary understanding.\n"
        "1: User picks up almost nothing useful.\n"
        "0: Interaction leaves the user no better informed than before."
    ),
    applies_to=ALL_MODES,
)

PROTOCOL_ADHERENCE = Metric(
    name="protocol_adherence",
    description=(
        "First-contact protocol: (a) confirm the source/service, (b) produce a "
        "plain-language summary, (c) flag potentially harmful clauses BEFORE "
        "accepting follow-up questions or storing as baseline. Returning-user "
        "protocol: (a) retrieve the prior baseline, (b) generate a structured "
        "delta, (c) explicitly flag new harmful clauses introduced."
    ),
    rubric=(
        "5: All required protocol steps performed in correct order.\n"
        "4: All steps performed, ordering minor issue only.\n"
        "3: Steps performed but out of order, or one step skipped.\n"
        "2: Multiple steps skipped or seriously mis-ordered.\n"
        "1: Most steps skipped.\n"
        "0: Protocol largely ignored."
    ),
    applies_to=(MODE_SUMMARY, MODE_DELTA),
)

FAITHFULNESS = Metric(
    name="faithfulness",
    description=(
        "Every factual claim in the response must be directly supported by the "
        "source ToS text. No hallucinated clauses, invented rights, or "
        "misrepresented terms."
    ),
    rubric=(
        "5: Every claim is verifiable in the source ToS.\n"
        "4: All claims grounded; one or two minor wording approximations.\n"
        "3: Most claims grounded, but at least one claim is unsupported or misstated.\n"
        "2: Several claims unsupported or misstated.\n"
        "1: Majority of claims unsupported.\n"
        "0: Response contains fabricated clauses or material misrepresentations."
    ),
    applies_to=ALL_MODES,
)

HARM_FLAGGING_ACCURACY = Metric(
    name="harm_flagging_accuracy",
    description=(
        "Whether the bot correctly identifies and flags genuinely concerning "
        "clauses (broad data sharing, forced arbitration, class-action waivers, "
        "unilateral modification, perpetual licenses, etc.) without flagging "
        "routine boilerplate. Requires comparison against the curated "
        "ground-truth labels."
    ),
    rubric=(
        "5: Flags all genuinely harmful clauses, no false positives.\n"
        "4: Flags all genuinely harmful clauses, minor over-flagging.\n"
        "3: Catches most harmful clauses but misses one, or flags one routine clause as harmful.\n"
        "2: Misses several harmful clauses or flags multiple routine clauses.\n"
        "1: Catches only one harmful clause or floods with false flags.\n"
        "0: Misses critical harmful clauses or floods response with false flags."
    ),
    applies_to=(MODE_SUMMARY, MODE_DELTA),
)

DELTA_PRECISION = Metric(
    name="delta_precision",
    description=(
        "For delta summaries: did the bot capture the material changes between "
        "old and new ToS, exclude cosmetic-only changes, and avoid inventing "
        "phantom changes?"
    ),
    rubric=(
        "5: All material changes captured, no fabricated changes, no cosmetic noise.\n"
        "4: All material changes captured, minimal cosmetic noise or one fabricated minor change.\n"
        "3: Major changes captured but minor changes missed or some noise included.\n"
        "2: Most changes missed or substantial noise included.\n"
        "1: Only one material change captured, or majority fabricated.\n"
        "0: Reports phantom changes or misses the most material change."
    ),
    applies_to=(MODE_DELTA,),
)


ALL_METRICS: tuple = (
    ANSWER_RELEVANCY,
    TASK_COMPLETION,
    PROTOCOL_ADHERENCE,
    FAITHFULNESS,
    HARM_FLAGGING_ACCURACY,
    DELTA_PRECISION,
)


def metrics_for_mode(mode: str) -> Iterable[Metric]:
    return tuple(m for m in ALL_METRICS if m.applicable(mode))