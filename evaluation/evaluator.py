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
from inference_retry import call_with_hf_retry

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
    """Best-effort extraction of the JSON object from a judge response.

    LLMs often append prose around the JSON. Pull out the first balanced object
    we can find; otherwise fall back to defaults.
    """
    if not raw:
        return {}
    match = _JSON_RE.search(raw)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        # Try to recover by stripping trailing commas, etc.
        cleaned = re.sub(r",\s*}", "}", match.group(0))
        cleaned = re.sub(r",\s*]", "]", cleaned)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {}


def _clamp_score(value) -> int:
    try:
        n = int(round(float(value)))
    except (TypeError, ValueError):
        return 0
    return max(0, min(5, n))

class Evaluator:
    """G-Eval style judge over a single (test_case, response) pair."""

    def __init__(
        self,
        model: str = BASE_MODEL,
        token: Optional[str] = HF_TOKEN,
        n_runs: int = 3,
        temperature: float = 0.2,
        max_tokens: int = 800,
        client: Optional[InferenceClient] = None,
    ):
        self.model = model
        self.n_runs = n_runs
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.client = client or InferenceClient(model=model, token=token)

    # ------------------------------------------------------------------
    # Public API
    def score_metric(
        self,
        metric: Metric,
        mode: str,
        user_input: str,
        response: str,
        source_tos: str = "",
        previous_tos: str = "",
        ground_truth: str = "",
    ) -> MetricResult:
        """Score a single metric ``n_runs`` times and return the aggregate."""
        runs: list = []
        for _ in range(self.n_runs):
            run = self._single_run(
                metric=metric,
                mode=mode,
                user_input=user_input,
                response=response,
                source_tos=source_tos,
                previous_tos=previous_tos,
                ground_truth=ground_truth,
            )
            runs.append(run)

        scores = [r.score for r in runs]
        mean = sum(scores) / max(len(scores), 1)
        result = MetricResult(
            metric=metric.name,
            runs=runs,
            mean_score=mean,
            normalized=round(mean / 5.0, 4),
            score_spread=(max(scores) - min(scores)) if scores else 0,
        )
        return result

    # ------------------------------------------------------------------
    # Internal helpers

    def _build_user_message(
        self,
        metric: Metric,
        mode: str,
        user_input: str,
        response: str,
        source_tos: str,
        previous_tos: str,
        ground_truth: str,
    ) -> str:
        gt_block = (
            f"<ground_truth>\n{ground_truth}\n</ground_truth>\n\n"
            if ground_truth
            else ""
        )
        previous_block = (
            f"<previous_tos>\n{previous_tos}\n</previous_tos>\n\n"
            if previous_tos
            else ""
        )
        return (
            f"INTERACTION_MODE: {mode}\n"
            f"CRITERION_NAME: {metric.name}\n"
            f"CRITERION_DESCRIPTION: {metric.description}\n\n"
            f"RUBRIC (0..5):\n{metric.rubric}\n\n"
            f"<user_input>\n{user_input}\n</user_input>\n\n"
            f"<source_tos>\n{source_tos}\n</source_tos>\n\n"
            f"{previous_block}"
            f"{gt_block}"
            f"<assistant_response>\n{response}\n</assistant_response>\n\n"
            "Apply the procedure and return the JSON object."
        )
    def _single_run(
        self,
        metric: Metric,
        mode: str,
        user_input: str,
        response: str,
        source_tos: str,
        previous_tos: str,
        ground_truth: str,
    ) -> JudgeRun:
        messages = [
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": self._build_user_message(
                    metric=metric,
                    mode=mode,
                    user_input=user_input,
                    response=response,
                    source_tos=source_tos,
                    previous_tos=previous_tos,
                    ground_truth=ground_truth,
                ),
            },
        ]
        try:
            output = call_with_hf_retry(
                lambda: self.client.chat_completion(
                    messages=messages,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                ),
                label="evaluator",
            )
            raw = (output.choices[0].message.content or "").strip()
        except Exception as exc:  # noqa: BLE001
            print(f"[evaluator] judge call failed: {type(exc).__name__}: {exc}")
            return JudgeRun(
                metric=metric.name,
                score=0,
                normalized=0.0,
                justification=f"judge_error: {exc}",
                raw="",
            )

        parsed = _parse_judge_output(raw)
        score = _clamp_score(parsed.get("score"))
        return JudgeRun(
            metric=metric.name,
            score=score,
            normalized=round(score / 5.0, 4),
            criterion_restatement=str(parsed.get("criterion_restatement", "")),
            reasoning=str(parsed.get("reasoning", "")),
            supporting_evidence=str(parsed.get("supporting_evidence", "")),
            contradicting_evidence=str(parsed.get("contradicting_evidence", "")),
            justification=str(parsed.get("justification", "")),
            raw=raw,
        )