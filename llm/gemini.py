"""Bounded text generation through Google's supported GenAI SDK."""
import os


def generate_text(prompt: str, *, max_output_tokens: int, json_mode: bool = False) -> str:
    from google import genai
    from google.genai import types

    # Ten seconds, a fresh client per call, no global credentials. google-genai
    # 2.x's Client isn't a context manager (no __enter__/__exit__ or close())
    # and HttpOptions has no retry field - the underlying transport doesn't
    # retry on its own, so a bounded timeout alone already keeps one call
    # from silently multiplying credit usage.
    client = genai.Client(
        api_key=os.environ["GEMINI_API_KEY"],
        vertexai=False,
        http_options=types.HttpOptions(timeout=10_000),
    )
    response = client.models.generate_content(
        model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"),
        contents=prompt,
        config=types.GenerateContentConfig(
            max_output_tokens=max_output_tokens,
            response_mime_type="application/json" if json_mode else "text/plain",
        ),
    )
    if not response.text or not response.text.strip():
        raise ValueError("Gemini returned no text")
    return response.text.strip()
