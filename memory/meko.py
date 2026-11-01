"""
memory/meko.py — Meko MCP Phase 2 Client and Finding Publisher.

Publishes verified findings and run results to Meko over MCP for coding agents.
Local storage remains the source of truth for replays and regression checks.
All API keys are strictly redacted in any error messages.
"""

# ruff: noqa: E501 -- preserve the generated Markdown's existing long lines

from __future__ import annotations

import base64
import hashlib
import json
import logging
import time
from typing import Any

import requests

from detect.contracts import Finding

logger = logging.getLogger("swarmtest.meko")


def _redact(text: str, secret: str) -> str:
    """Safely redact secret tokens from any string or exception output."""
    if not secret or not text:
        return text
    return text.replace(secret, "[REDACTED_API_KEY]")


def format_finding_markdown(
    finding: Finding,
    replay_artifact_hash: str,
    commit: str = "HEAD",
) -> str:
    """
    Format a verified finding into a structured markdown document for Meko.
    Includes the mandatory notice that this file is data, not instructions.
    """
    # Extract unique endpoints hit in the minimal repro sequence
    endpoints = sorted(
        list(
            {
                f"{a.request.method} {a.request.path}"
                for step in finding.minimal_repro_sequence.steps
                for a in step.actions
            }
        )
    )

    # Format human-readable repro steps without credentials or sensitive data
    repro_lines = []
    for step_idx, step in enumerate(finding.minimal_repro_sequence.steps, start=1):
        action_descs = []
        for a in step.actions:
            clean_body = (
                f" with payload {json.dumps(a.request.json_body)}" if a.request.json_body else ""
            )
            action_descs.append(
                f"agent `{a.agent_id}` calls `{a.request.method} {a.request.path}`{clean_body}"
            )
        repro_lines.append(f"{step_idx}. Concurrently execute: {'; '.join(action_descs)}")

    repro_text = "\n".join(repro_lines)
    endpoints_str = ", ".join(f"`{ep}`" for ep in endpoints) if endpoints else "N/A"

    return f"""# Finding: {finding.title}

<!-- Notice: This document contains testing data and bug reports. It does not contain instructions or commands for AI models. -->

## Summary
- **id**: `{finding.id}`
- **bug_class**: `{finding.mapped_bug_id or finding.type}`
- **severity**: `{finding.severity}`
- **status**: `open`
- **endpoints**: {endpoints_str}
- **violated_invariant**: `{finding.oracle_triggered}`
- **replay_artifact_hash**: `{replay_artifact_hash}`
- **reproduction_rate**: `1.0`
- **first_seen**: (run: `{finding.run_id}`, commit: `{commit}`)
- **last_checked**: (run: `{finding.run_id}`, commit: `{commit}`)

## Invariant Details
- **Expected**: Invariant `{finding.oracle_triggered}` holds across concurrent and sequential operations.
- **Actual**: Invariant was violated. Detected failure condition: `{finding.title}`.

## Reproduction Steps
{repro_text}

## Verification Status
- **Verified**: Yes (proven via deterministic replay in an isolated environment).
- **Involved Agents**: {", ".join(f"`{ag}`" for ag in finding.involved_agents)}
- **Causality**: `{finding.causality}`
"""


def format_run_results_markdown(
    run_id: str,
    results: list[dict[str, str]],
    commit: str = "HEAD",
) -> str:
    """Format run recheck results (fixed, still_failing, regressed) into markdown."""
    rows = []
    for r in results:
        rows.append(
            f"| `{r.get('finding_id', 'unknown')}` | `{r.get('classification', 'unknown')}` |"
        )
    table = "\n".join(rows) if rows else "| None | None |"

    return f"""# Swarmtest Run Results: {run_id}

<!-- Notice: This document contains testing data and bug reports. It does not contain instructions or commands for AI models. -->

- **run_id**: `{run_id}`
- **commit**: `{commit}`
- **checked_at**: `{time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime())}`

| Finding ID | Classification |
| :--- | :--- |
{table}
"""


class MekoClient:
    """
    Client for Meko MCP Streamable HTTP endpoint.
    Handles SSE framing, conversation tracing, artifact storage, and document upload.
    """

    def __init__(
        self,
        mcp_url: str = "https://mcp.mekodata.ai/mcp",
        api_key: str = "",
        datapack_id: str = "",
        timeout: float = 25.0,
    ):
        self.mcp_url = mcp_url.rstrip("/")
        self.api_key = api_key.strip()
        self.datapack_id = datapack_id.strip()
        self.timeout = timeout
        self._conversation_id: str | None = None

        if not self.api_key:
            raise ValueError("MEKO_API_KEY must not be empty")
        if not self.datapack_id:
            raise ValueError("MEKO_DATAPACK_ID must not be empty")

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "Swarmtest/0.1.0",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }

    def _parse_sse(self, raw_text: str) -> dict | None:
        """Extract JSON-RPC payload from text/event-stream response."""
        for line in raw_text.splitlines():
            line = line.strip()
            if line.startswith("data:"):
                payload = line[5:].strip()
                if payload:
                    try:
                        return json.loads(payload)
                    except json.JSONDecodeError:
                        pass
        return None

    def call_tool(self, tool_name: str, arguments: dict[str, Any], req_id: int = 1) -> dict:
        """Call an MCP tool on Meko over HTTP JSON-RPC."""
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
            "id": req_id,
        }
        try:
            resp = requests.post(
                self.mcp_url,
                headers=self.headers,
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = (
                resp.json()
                if "application/json" in resp.headers.get("Content-Type", "")
                else self._parse_sse(resp.text)
            )
            if not data or "result" not in data:
                raise RuntimeError("Unexpected MCP response")
            if data["result"].get("isError"):
                raise RuntimeError("Meko MCP tool reported an error")

            # Check for error wrapped in content text
            content = data["result"].get("content", [])
            for c in content:
                if c.get("type") == "text":
                    text_val = c.get("text", "")
                    try:
                        parsed_text = json.loads(text_val)
                        if isinstance(parsed_text, dict) and "error" in parsed_text:
                            raise RuntimeError("Meko tool returned an error")
                        return parsed_text
                    except json.JSONDecodeError:
                        return {"text": text_val}
            return data["result"]

        except Exception as exc:
            redacted_msg = _redact(str(exc), self.api_key)
            logger.warning("Meko call_tool '%s' failed: %s", tool_name, redacted_msg)
            raise RuntimeError(f"Meko call_tool failed: {redacted_msg}") from None

    def get_or_create_conversation(self, title: str = "Swarmtest Verifier") -> str:
        """Create or return active conversation ID for trace nesting."""
        if self._conversation_id:
            return self._conversation_id

        res = self.call_tool(
            "conversation_create",
            {
                "datapack_id": self.datapack_id,
                "agent_id": "swarmtest:verifier",
                "title": title,
            },
        )
        conv_id = res.get("id") if isinstance(res, dict) else None
        if not conv_id:
            raise RuntimeError("Failed to create Meko conversation")
        self._conversation_id = conv_id
        return conv_id

    def put_replay_artifact(self, replay_json: str, filename: str = "replay.json") -> str:
        """
        Store replay sequence via artifact_put.
        Returns the artifact's content_hash (SHA-256).
        """
        conv_id = self.get_or_create_conversation()
        content_bytes = replay_json.encode("utf-8")
        b64_content = base64.b64encode(content_bytes).decode("utf-8")

        res = self.call_tool(
            "artifact_put",
            {
                "filename": filename,
                "content_base64": b64_content,
                "content_type": "application/json",
                "conversation_id": conv_id,
                "datapack_id": self.datapack_id,
                "agent_id": "swarmtest:verifier",
            },
        )
        content_hash = res.get("content_hash") if isinstance(res, dict) else None
        if not content_hash:
            raise RuntimeError("artifact_put did not return content_hash")
        return content_hash

    def upload_knowledgebase_document(
        self,
        filename: str,
        content: str,
        max_poll_seconds: float = 10.0,
    ) -> dict:
        """
        Upload a markdown document into Meko's knowledge base.
        Handles presigned S3 POST upload and status check.
        """
        conv_id = self.get_or_create_conversation()
        doc_bytes = content.encode("utf-8")
        doc_size = len(doc_bytes)
        doc_hash = hashlib.sha256(doc_bytes).hexdigest()
        doc_head = base64.b64encode(doc_bytes[:3072]).decode("utf-8")

        prep = self.call_tool(
            "knowledgebase_upload_document",
            {
                "filename": filename,
                "size": doc_size,
                "content_hash": doc_hash,
                "content_head_base64": doc_head,
                "conversation_id": conv_id,
                "datapack_id": self.datapack_id,
                "agent_id": "swarmtest:verifier",
            },
        )

        s3_url = prep.get("url")
        fields = prep.get("fields")
        doc_key = prep.get("key")

        if not doc_key:
            raise RuntimeError("knowledgebase_upload_document missing document key")

        # Post file to presigned S3 URL
        if not prep.get("already_uploaded"):
            if not s3_url or not fields:
                raise RuntimeError("knowledgebase_upload_document missing upload info")
            files = {"file": (filename, doc_bytes, "text/markdown")}
            s3_resp = requests.post(s3_url, data=fields, files=files, timeout=self.timeout)
            if s3_resp.status_code not in (200, 201, 204):
                raise RuntimeError(f"S3 upload failed with HTTP {s3_resp.status_code}")

        deadline = time.monotonic() + max_poll_seconds
        while True:
            status_resp = self.call_tool(
                "knowledgebase_document_status",
                {
                    "document_key": doc_key,
                    "conversation_id": conv_id,
                    "datapack_id": self.datapack_id,
                    "agent_id": "swarmtest:verifier",
                },
            )
            state = status_resp.get("state", status_resp.get("status", "unknown"))
            if state in {"indexed", "completed", "ready", "success"}:
                break
            if state in {"failed", "error"}:
                raise RuntimeError("Meko document indexing failed")
            if time.monotonic() >= deadline:
                raise RuntimeError("Meko document indexing is still pending")
            time.sleep(0.5)
        return {
            "status": "uploaded",
            "document_key": doc_key,
            "content_hash": doc_hash,
            "indexing_state": state,
        }

    def publish_finding(self, finding: Finding, commit: str = "HEAD") -> str | None:
        """
        Store replay sequence as artifact and upload finding document to Meko.
        Returns the replay content_hash.
        """
        # 1. Upload replay sequence artifact
        replay_json = finding.minimal_repro_sequence.model_dump_json()
        replay_filename = f"replay_{finding.id}.json"
        artifact_hash = self.put_replay_artifact(replay_json, filename=replay_filename)

        # 2. Upload finding markdown document
        finding_md = format_finding_markdown(finding, artifact_hash, commit=commit)
        doc_filename = f"finding_{finding.id}.md"
        self.upload_knowledgebase_document(doc_filename, finding_md)

        return artifact_hash

    def publish_run_summary(
        self,
        run_id: str,
        results: list[dict[str, str]],
        commit: str = "HEAD",
    ) -> None:
        """Upload run recheck summary document to Meko."""
        summary_md = format_run_results_markdown(run_id, results, commit=commit)
        filename = f"run_results_{run_id}.md"
        self.upload_knowledgebase_document(filename, summary_md)
