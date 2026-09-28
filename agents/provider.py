"""Gemini provider adapter (W03-L) on the official `google-genai` SDK.

- SDK hidden retries are disabled (HttpRetryOptions attempts=1) and automatic
  function calling is off, so every HTTP send goes through the budget gate.
- One explicit retry at most for 429/5xx/timeout, honouring Retry-After plus
  jitter, and it shares the job's 8-send cap.
- A single configured model id; there is no fallback model and no paid tier
  switch. If the configured model has no verified quota, nothing is sent.
- Every send records model id, returned model version, prompt version,
  prompt hash and usageMetadata in the job events and the usage ledger.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import time
from typing import Any, Callable

from .budget import BudgetExceeded, BudgetGate
from .store import JobStore
from .tools import TOOL_DECLARATIONS, ROLE_TOOLS, args_hash, dispatch

RETRYABLE_CODES = {408, 429, 500, 502, 503, 504}


def make_client(api_key: str | None = None):  # pragma: no cover - needs a real key
    """Official SDK client with SDK-level retries disabled."""

    from google import genai
    from google.genai import types

    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY 未設定；只能執行 mock 測試。")
    return genai.Client(
        api_key=key,
        http_options=types.HttpOptions(timeout=60_000, retry_options=types.HttpRetryOptions(attempts=1)),
    )


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _usage_dict(resp: Any) -> dict[str, Any]:
    usage = getattr(resp, "usage_metadata", None)
    if usage is None:
        return {}
    fields = ("prompt_token_count", "candidates_token_count", "thoughts_token_count",
              "tool_use_prompt_token_count", "cached_content_token_count", "total_token_count")
    return {f: getattr(usage, f, None) for f in fields}


def _retry_after_seconds(exc: Exception) -> float | None:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None) or {}
    value = headers.get("retry-after") if hasattr(headers, "get") else None
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


class GeminiAdapter:
    def __init__(self, client: Any, model_id: str, gate: BudgetGate, *, prompt_version: str,
                 thinking_budget: int = 0, sleep: Callable[[float], None] = time.sleep,
                 monotonic: Callable[[], float] = time.monotonic):
        if not model_id:
            raise ValueError("GEMINI_MODEL 未設定；model id 由組長於 handoff/model-config.md 鎖定。")
        if gate.quota.model_id and gate.quota.model_id != model_id:
            raise ValueError(f"quota 核實的是 {gate.quota.model_id}，不能改用 {model_id}（不做 fallback）。")
        self.client, self.model_id, self.gate = client, model_id, gate
        self.prompt_version, self.thinking_budget = prompt_version, thinking_budget
        self.sleep, self.monotonic = sleep, monotonic

    @property
    def store(self) -> JobStore:
        return self.gate.store

    @property
    def job_id(self) -> str:
        return self.gate.job["job_id"]

    def build_config(self, role: str, system_instruction: str):
        from google.genai import types

        allowed = set(ROLE_TOOLS[role])
        declarations = [
            types.FunctionDeclaration(name=t["name"], description=t["description"],
                                      parameters_json_schema=t["parameters"])
            for t in TOOL_DECLARATIONS if t["name"] in allowed
        ]
        return types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=[types.Tool(function_declarations=declarations)],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            max_output_tokens=self.gate.limits.max_output_tokens,
            temperature=0,
            thinking_config=types.ThinkingConfig(thinking_budget=self.thinking_budget),
        )

    def send(self, role: str, contents: list[Any], system_instruction: str) -> Any:
        """One logical request = up to 1 + max_retries HTTP sends, all counted."""

        from google.genai import errors

        config = self.build_config(role, system_instruction)
        prompt_text = system_instruction + "\n" + json.dumps(
            [c.model_dump(mode="json", exclude_none=True) if hasattr(c, "model_dump") else c for c in contents],
            ensure_ascii=False,
        )
        prompt_hash = _hash(prompt_text)
        for attempt in range(self.gate.limits.max_retries + 1):
            res = self.gate.reserve_call(role, prompt_text, prompt_hash)
            started = self.monotonic()
            try:
                resp = self.client.models.generate_content(model=self.model_id, contents=contents, config=config)
            except errors.APIError as exc:
                self.gate.settle(res, f"error_{exc.code}", None)
                self.store.append_event(self.job_id, role, "model_error", detail={
                    "call_number": res.call_number, "code": exc.code, "model_id": self.model_id,
                    "prompt_version": self.prompt_version, "prompt_hash": prompt_hash,
                })
                self.gate.add_active_time(self.monotonic() - started)
                if exc.code in RETRYABLE_CODES and attempt < self.gate.limits.max_retries:
                    wait = _retry_after_seconds(exc) or 2.0
                    self.sleep(wait + random.uniform(0, 1))
                    continue
                if exc.code == 429:
                    raise BudgetExceeded("provider_429", "供應商回 429，重試後仍失敗；保存 paused_quota") from exc
                raise
            self.gate.add_active_time(self.monotonic() - started)
            usage = _usage_dict(resp)
            self.gate.settle(res, "ok", usage.get("total_token_count"))
            candidate = (getattr(resp, "candidates", None) or [None])[0]
            self.store.append_event(self.job_id, role, "model_call", detail={
                "call_number": res.call_number,
                "model_id": self.model_id,
                "model_version": getattr(resp, "model_version", None),
                "prompt_version": self.prompt_version,
                "prompt_hash": prompt_hash,
                "usage": usage,
                "finish_reason": str(getattr(candidate, "finish_reason", None)),
                "function_calls": [fc.name for fc in (resp.function_calls or [])],
            })
            return resp
        raise AssertionError("unreachable")

    def run_tool_roundtrip(self, role: str, user_prompt: str, system_instruction: str) -> dict[str, Any]:
        """Model → tool call(s) → function response → model, until text or a budget stop."""

        from google.genai import types

        contents: list[Any] = [types.Content(role="user", parts=[types.Part.from_text(text=user_prompt)])]
        while True:
            resp = self.send(role, contents, system_instruction)
            calls = resp.function_calls or []
            if not calls:
                return {"text": resp.text, "contents": contents, "response": resp}
            contents.append(resp.candidates[0].content)
            parts = []
            for call in calls:
                args = dict(call.args or {})
                h = args_hash(args)
                self.gate.register_tool_call(call.name, h)
                result = dispatch(role, call.name, args)
                self.store.append_event(self.job_id, role, "tool_call", call.name, {
                    "args_hash": h,
                    "output_hash": _hash(json.dumps(result, sort_keys=True, ensure_ascii=False))[:16],
                    "status": result.get("status"),
                    "reason": result.get("reason"),
                })
                parts.append(types.Part.from_function_response(name=call.name, response=result))
            contents.append(types.Content(role="user", parts=parts))
