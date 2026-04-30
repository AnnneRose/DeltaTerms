"""G-Eval style LLM-as-judge evaluator for the DeltaTerms chatbot.

The evaluator uses the same Hugging Face inference model that powers the
chatbot itself (see ``config.BASE_MODEL``) to keep methodology consistent with
the reference G-Eval paper. For every evaluation:

  1. The judge restates the criterion.
  2. It produces a Chain-of-Thought reasoning trace.
  3. It identifies supporting and contradicting evidence.
  4. It emits an integer 0..5 score with a justification.

To dampen the variance of LLM-as-judge scoring, each (test_case, metric) pair
is judged ``n`` times (default 3) at low temperature (default 0.2), and the
scores are averaged before being normalized to the 0.0..1.0 scale.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from typing import Optional

from huggingface_hub import InferenceClient

from config import BASE_MODEL, HF_TOKEN
from .metrics import Metric


JUDGE_SYSTEM_PROMPT = """
You are an evaluation judge for a Terms of Service assistant. Score the
assistant's RESPONSE for a single CRITERION using the rubric you are given.

You MUST follow this exact procedure (G-Eval / Chain-of-Thought):

1. RESTATE the criterion you have been given in your own words (one sentence).
2. REASON step by step over the user input, the source Terms of Service, the
   ground-truth annotations (if provided), and the assistant's response.
3. Identify SUPPORTING evidence (text that backs up a high score).
4. Identify CONTRADICTING evidence (text that drags the score down).
5. Decide a final integer SCORE in the range 0..5 using the rubric.
6. Provide a one or two sentence JUSTIFICATION for the score.

Output strictly as JSON, no preamble or trailing prose, with the keys:

{
  "criterion_restatement": "...",
  "reasoning": "...",
  "supporting_evidence": "...",
  "contradicting_evidence": "...",
  "score": <integer 0..5>,
  "justification": "..."
}

Do not output markdown fences. Do not output any text outside the JSON object.
""".strip()


@dataclass
class JudgeRun:
    """A single G-Eval style judging trace."""

    metric: str
    score: int
    normalized: float
    criterion_restatement: str = ""
    reasoning: str = ""
    supporting_evidence: str = ""
    contradicting_evidence: str = ""
    justification: str = ""
    raw: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class MetricResult:
    """Aggregated result over ``n`` judge runs for one metric."""

    metric: str
    runs: list = field(default_factory=list)
    mean_score: float = 0.0
    normalized: float = 0.0
    score_spread: int = 0  # max(scores) - min(scores)

    def as_dict(self) -> dict:
        return {
            "metric": self.metric,
            "runs": [r.as_dict() for r in self.runs],
            "mean_score": self.mean_score,
            "normalized": self.normalized,
            "score_spread": self.score_spread,
        }


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_judge_output(raw: str) -> dict: