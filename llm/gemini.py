"""Bounded text generation through Google's supported GenAI SDK."""
import os


def generate_text(prompt: str, *, max_output_tokens: int, json_mode: bool = False) -> str:
    from google import genai
    from google.genai import types

    # One attempt, ten seconds, and a closed client per call. Avoid global
    # credentials and SDK retries that silently multiply credit usage.
    with genai.Client(
        api_key=os.environ["GEMINI_API_KEY"],
        vertexai=False,
        http_options=types.HttpOptions(
            timeout=10_000,
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    ) as client:
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
