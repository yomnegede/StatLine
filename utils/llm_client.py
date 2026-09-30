import os
import re


def generate_answer(question: str, context: str, model: str = "gpt-4o-mini") -> str:
    """Answer from retrieved stats, with chunk IDs as citations."""
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("Set OPENAI_API_KEY in .env before generating an answer")

    from openai import OpenAI, RateLimitError

    try:
        response = OpenAI(max_retries=0).responses.create(
            model=model,
            instructions=(
                "You are an NBA stats assistant. Answer using only the supplied context. "
                "If the context is insufficient, say so. End each paragraph that states "
                "stats with the exact [Source: chunk_id] shown in the context. "
                "Every paragraph containing a number needs the citation for the source "
                "supporting that number; do not leave comparison or summary paragraphs uncited. "
                "Mention season and date ranges when they matter, especially if sources "
                "cover different periods. Do not invent stats, dates, or source IDs."
            ),
            input=f"Context:\n{context}\n\nQuestion: {question}",
        )
    except RateLimitError as error:
        body = error.body if isinstance(error.body, dict) else {}
        detail = body.get("error", body)
        if detail.get("code") == "credit_balance_exhausted":
            raise RuntimeError(
                "OpenAI API credits are exhausted. Add credits in the OpenAI Platform billing settings."
            ) from None
        raise
    answer = response.output_text
    source_ids = list(dict.fromkeys(re.findall(r"\[Source: ([^\]]+)\]", context)))
    if source_ids and not any(f"[Source: {source_id}]" in answer for source_id in source_ids):
        answer += "\n\nRetrieved sources: " + ", ".join(
            f"[Source: {source_id}]" for source_id in source_ids
        )
    return answer
