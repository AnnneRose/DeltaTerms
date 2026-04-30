from huggingface_hub import InferenceClient
from config import BASE_MODEL, HF_TOKEN

SYSTEM_PROMPT = """
You are a Terms-of-Service change analyst. You will be given two versions of the
same Terms of Service document — the OLD version and the NEW version. Your job
is to summarize the meaningful differences as a concise bullet list a regular
user can understand.

RULES:
1. Output ONLY a bullet list. Each bullet starts with "- ".
2. Each bullet describes a single, concrete change.
3. Focus on changes that affect the user: data collection, data sharing,
   account termination, dispute resolution, payments, liability, content
   ownership, retention periods, opt-out rights.
4. Ignore cosmetic edits: reworded sentences with the same meaning, formatting,
   typo fixes, section renumbering.
5. If a change has a number (e.g. "18 months" -> "24 months"), include both
   values.
6. Do not invent changes that are not present in the texts.
7. If there are no meaningful changes, return exactly the single line:
   - No meaningful changes detected.
8. Do not include preamble, headers, or closing remarks. Bullets only.
""".strip()


class DeltaGenerator:
    def __init__(self):
        self.client = InferenceClient(model=BASE_MODEL, token=HF_TOKEN)

    def get_delta(self, old_tos: str, new_tos: str) -> str | None:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"OLD VERSION:\n{old_tos}\n\n"
                    f"NEW VERSION:\n{new_tos}\n\n"
                    "List the meaningful changes as bullets."
                ),
            },
        ]
        print(f"[delta] calling HF model={BASE_MODEL}, old_len={len(old_tos)}, new_len={len(new_tos)}")
        try:
            output = self.client.chat_completion(messages=messages, max_tokens=1024)
            content = output.choices[0].message.content
            print(f"[delta] HF returned content length={len(content) if content else 0}")
            return content.strip() if content else None
        except Exception as exc:
            print(f"[delta] generation failed: {type(exc).__name__}: {exc}")
            return None
