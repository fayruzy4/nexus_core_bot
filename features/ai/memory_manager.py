from __future__ import annotations

from typing import Any, Dict, List

from features.ai.utils_ai import normalize_text, summarize_old_messages


def build_context_messages(
    system_prompt: str,
    summary_text: str,
    messages: List[Dict[str, Any]],
    keep_last: int = 14,
    max_chars: int = 12000,
) -> List[Dict[str, str]]:
    prepared: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]

    summary_text = normalize_text(summary_text)
    if summary_text:
        prepared.append(
            {
                "role": "system",
                "content": "Ringkasan memori percakapan sebelumnya:\n" + summary_text,
            }
        )

    if len(messages) > keep_last:
        old = messages[:-keep_last]
        compact = summarize_old_messages(old, max_turns=min(len(old), 8))
        if compact:
            prepared.append(
                {
                    "role": "system",
                    "content": "Konteks lama yang masih relevan:\n" + compact,
                }
            )

    tail = messages[-keep_last:] if len(messages) > keep_last else messages
    for msg in tail:
        role = msg.get("role", "user")
        content = normalize_text(msg.get("content", ""))
        if not content:
            continue
        if role == "assistant":
            mapped = "assistant"
        elif role == "system":
            mapped = "system"
        else:
            mapped = "user"
        prepared.append({"role": mapped, "content": content})

    total_chars = sum(len(m["content"]) for m in prepared)
    if total_chars > max_chars and len(prepared) > 1:
        keep = [prepared[0]]
        running = len(keep[0]["content"])
        for msg in reversed(prepared[1:]):
            if running + len(msg["content"]) > max_chars:
                break
            keep.insert(1, msg)
            running += len(msg["content"])
        prepared = keep

    return prepared
