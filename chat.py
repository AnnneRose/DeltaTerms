from huggingface_hub import InferenceClient
from config import BASE_MODEL, HF_TOKEN

SYSTEM_PROMPT_TEMPLATE = """
You are a Terms of Service assistant for the service "{service_name}". You help
users understand what they are agreeing to and how the latest changes affect
them.

The reference material below is provided to you in three XML-tagged blocks:
<current_tos>, <previous_tos>, and <change_summary>. These tags are scaffolding
for your reference only — DO NOT mention or refer to them in your responses.
The user does not see them and will be confused if you cite them by name.
Do not say things like "according to the SUMMARY OF CHANGES" or "the CURRENT
TERMS OF SERVICE states." Speak naturally, as if quoting the Terms of Service
directly: "the Terms of Service say..." or "this version adds..." or
"previously, the policy was..."

RULES:
1. Answer using ONLY information present in the provided reference text. Do
   not invent clauses, numbers, dates, or contact details.
2. If the user asks about a topic that is not covered, say plainly: "The
   Terms of Service do not address that."
3. When the user asks what changed, compare the two versions and cite specific
   numbers and clause names from the actual text.
4. Use plain language. Briefly define legal terms in parentheses if you use
   them (e.g. "binding arbitration (a private dispute process instead of
   court)").
5. Be concise. Use markdown bullets when listing multiple points.
6. Do not add legal disclaimers unless the user is explicitly asking for legal
   advice. You are explaining what the document says, not giving advice.

<current_tos>
{current_tos}
</current_tos>

<previous_tos>
{previous_tos}
</previous_tos>

<change_summary>
{delta}
</change_summary>
""".strip()


class Chatbot:
    def __init__(self):
        self.client = InferenceClient(model=BASE_MODEL, token=HF_TOKEN)

    def format_prompt(
        self,
        user_input: str,
        history: list,
        service_name: str,
        current_tos: str,
        previous_tos: str | None,
        delta: str | None,
    ) -> list[dict]:
        system_content = SYSTEM_PROMPT_TEMPLATE.format(
            service_name=service_name,
            current_tos=current_tos,
            previous_tos=previous_tos
            or "(Not available — this is the first version uploaded.)",
            delta=delta or "(Not available — no prior version to compare against.)",
        )
        messages = [{"role": "system", "content": system_content}]
        for turn in history or []:
            role = turn.get("role")
            content = turn.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": user_input})
        return messages

    def get_response(
        self,
        user_input: str,
        history: list,
        service_name: str,
        current_tos: str,
        previous_tos: str | None,
        delta: str | None,
    ) -> str:
        messages = self.format_prompt(
            user_input,
            history,
            service_name,
            current_tos,
            previous_tos,
            delta,
        )
        print(
            f"[chat] calling HF model={BASE_MODEL}, "
            f"history_turns={len(history or [])}, "
            f"current_tos_len={len(current_tos)}, "
            f"previous_tos_len={len(previous_tos or '')}"
        )
        output = self.client.chat_completion(messages=messages, max_tokens=1024)
        content = output.choices[0].message.content
        print(f"[chat] HF returned content length={len(content) if content else 0}")
        return (content or "").strip()
