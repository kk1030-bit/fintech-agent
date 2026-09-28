"""V1.2 research-agent runtime: job contract, persistent queue, budget gate,
tool contracts and the Gemini provider adapter.

Everything here is new in V1.2 (W02-L/W03-L). The existing Flask site, data
downloaders, DCF and PDF modules are left untouched and are reused later.
"""

from pathlib import Path

from dotenv import load_dotenv

# Server-side settings (RESEARCH_API_TOKEN, GEMINI_MODEL, GEMINI_API_KEY) live in
# the repo-root .env; real environment variables (e.g. on Render) take precedence.
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
