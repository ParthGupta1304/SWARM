"""
adapters/openapi.py — OpenAPI 3.x spec parser and dynamic HTTP tool generator.

Translates any OpenAPI spec into:
  1. OpenAI-compatible tool definitions (for LLM function calling).
  2. A dynamic HTTP executor that routes tool calls to the correct endpoint,
     interpolates path parameters, attaches query params, builds JSON bodies,
     and manages auth headers.

Adding an endpoint to openapi.json immediately generates a callable tool
with zero code modifications.
"""

import json
import time
import re
from pathlib import Path
from typing import Any, Optional, Union
import requests


def _resolve_ref(spec: dict, ref: str) -> dict:
    """Resolve a '#/components/schemas/Name' reference in an OpenAPI spec."""
    if not ref.startswith("#/"):
        return {}
    parts = ref.lstrip("#/").split("/")
    curr = spec
    for part in parts:
        if isinstance(curr, dict) and part in curr:
            curr = curr[part]
        else:
            return {}
    return curr if isinstance(curr, dict) else {}


def _clean_schema_property(prop: dict, spec: dict) -> dict:
    """Simplify schema property for OpenAI tool calling compatibility."""
    if "$ref" in prop:
        resolved = _resolve_ref(spec, prop["$ref"])
        return _clean_schema_property(resolved, spec)

    cleaned = {}
    if "type" in prop:
        cleaned["type"] = prop["type"]
    elif "anyOf" in prop:
        # e.g. OpenAPI 3.1 nullable: anyOf: [{"type": "string"}, {"type": "null"}]
        non_null = [t for t in prop["anyOf"] if t.get("type") != "null"]
        if non_null and "type" in non_null[0]:
            cleaned["type"] = non_null[0]["type"]
        else:
            cleaned["type"] = "string"
    else:
        cleaned["type"] = "string"

    if "description" in prop:
        cleaned["description"] = prop["description"]
    elif "title" in prop:
        cleaned["description"] = prop["title"]

    if "enum" in prop:
        cleaned["enum"] = prop["enum"]

    if cleaned.get("type") == "array" and "items" in prop:
        cleaned["items"] = _clean_schema_property(prop["items"], spec)

    return cleaned


class OpenAPIAdapter:
    """
    Loads an OpenAPI 3.x spec and exposes dynamic tools and an HTTP executor.
    """

    def __init__(self, spec_or_path: Union[str, Path, dict], base_url: str):
        self.base_url = str(base_url).rstrip("/")
        if isinstance(spec_or_path, (str, Path)):
            spec_path = Path(spec_or_path)
            if not spec_path.exists():
                raise FileNotFoundError(f"OpenAPI spec not found at {spec_path.resolve()}")
            with open(spec_path, "r", encoding="utf-8") as f:
                self.spec = json.load(f)
        else:
            self.spec = spec_or_path

        # Cache of operation metadata: op_id -> metadata
        self.operations: dict[str, dict] = {}
        self._parse_spec()

    def _parse_spec(self):
        """Parse paths and methods from the OpenAPI spec into operation metadata."""
        paths = self.spec.get("paths", {})
        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue
            for method in ("get", "post", "put", "delete", "patch"):
                if method not in path_item:
                    continue
                op = path_item[method]
                if not isinstance(op, dict):
                    continue

                # Generate or take operationId
                op_id = op.get("operationId")
                if not op_id:
                    clean_path = re.sub(r"[{}]", "", path).strip("/").replace("/", "_")
                    op_id = f"{method}_{clean_path}" if clean_path else method

                description = op.get("summary") or op.get("description") or f"{method.upper()} {path}"

                # Parse parameters (path, query, header)
                path_params = []
                query_params = []
                param_properties = {}
                param_required = []

                for param in op.get("parameters", []):
                    if "$ref" in param:
                        param = _resolve_ref(self.spec, param["$ref"])

                    p_name = param.get("name")
                    p_in = param.get("in")
                    if not p_name or not p_in:
                        continue

                    # Don't require LLM to provide Authorization header manually
                    if p_in == "header" and p_name.lower() in ("authorization", "auth"):
                        continue

                    p_schema = param.get("schema", {})
                    clean_prop = _clean_schema_property(p_schema, self.spec)
                    if "description" in param and "description" not in clean_prop:
                        clean_prop["description"] = param["description"]

                    param_properties[p_name] = clean_prop

                    if p_in == "path":
                        path_params.append(p_name)
                        param_required.append(p_name)
                    elif p_in == "query":
                        query_params.append(p_name)
                        if param.get("required"):
                            param_required.append(p_name)

                # Parse requestBody (application/json)
                body_properties = {}
                body_required = []
                req_body = op.get("requestBody")
                if req_body:
                    if "$ref" in req_body:
                        req_body = _resolve_ref(self.spec, req_body["$ref"])
                    content = req_body.get("content", {})
                    json_media = content.get("application/json", {})
                    schema = json_media.get("schema", {})
                    if "$ref" in schema:
                        schema = _resolve_ref(self.spec, schema["$ref"])

                    if schema.get("type") == "object" or "properties" in schema:
                        props = schema.get("properties", {})
                        for k, v in props.items():
                            body_properties[k] = _clean_schema_property(v, self.spec)
                        body_required = schema.get("required", [])

                # Combine all properties for the tool parameter definition
                properties = {**param_properties, **body_properties}
                required = list(dict.fromkeys(param_required + body_required))

                self.operations[op_id] = {
                    "operation_id": op_id,
                    "method": method.upper(),
                    "path": path,
                    "description": description,
                    "path_params": path_params,
                    "query_params": query_params,
                    "body_params": list(body_properties.keys()),
                    "tool_definition": {
                        "type": "function",
                        "function": {
                            "name": op_id,
                            "description": description,
                            "parameters": {
                                "type": "object",
                                "properties": properties,
                                "required": required,
                            },
                        },
                    },
                }

    def get_tool_definitions(self, tool_names: Optional[list[str]] = None) -> list[dict]:
        """
        Return OpenAI-format tool definitions.
        If tool_names is provided, filters to only those operation IDs.
        """
        if tool_names is not None:
            return [
                self.operations[name]["tool_definition"]
                for name in tool_names
                if name in self.operations
            ]
        return [op["tool_definition"] for op in self.operations.values()]

    def get_tool_names(self) -> set[str]:
        """Return all available operation IDs."""
        return set(self.operations.keys())

    def execute_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        auth_token: str = "",
        timeout: float = 10.0,
    ) -> tuple[int, str, float]:
        """
        Execute an operation by its tool_name over HTTP against base_url.

        Returns: (http_status_code, response_body_text, latency_ms)
        """
        t0 = time.perf_counter()
        op = self.operations.get(tool_name)
        if not op:
            latency = (time.perf_counter() - t0) * 1000
            return 400, json.dumps({"error": f"unknown tool: {tool_name}"}), latency

        method = op["method"]
        path_template = op["path"]
        path_params = op["path_params"]
        query_params = op["query_params"]
        body_params = op["body_params"]

        # Build path interpolation
        url_path = path_template
        for param in path_params:
            if param in arguments:
                url_path = url_path.replace(f"{{{param}}}", str(arguments[param]))
            else:
                latency = (time.perf_counter() - t0) * 1000
                return 400, json.dumps({"error": f"missing required path parameter: {param}"}), latency

        # Build query params
        params = {}
        for param in query_params:
            if param in arguments and arguments[param] is not None:
                params[param] = arguments[param]

        # Build JSON body
        # If the endpoint takes a JSON body, collect arguments defined in body_params
        # If body_params is empty but method in POST/PUT/PATCH and arguments exist (not in path/query), include them
        body = None
        if method in ("POST", "PUT", "PATCH"):
            if body_params:
                body = {k: arguments[k] for k in body_params if k in arguments}
            else:
                # Include anything not consumed by path/query
                extra = {k: v for k, v in arguments.items() if k not in path_params and k not in query_params}
                if extra:
                    body = extra
                else:
                    body = {}

        # Headers
        headers: dict[str, str] = {}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        url = f"{self.base_url}{url_path}"

        try:
            r = requests.request(
                method=method,
                url=url,
                params=params if params else None,
                json=body if body is not None else None,
                headers=headers,
                timeout=timeout,
            )
            latency = (time.perf_counter() - t0) * 1000
            return r.status_code, r.text, latency
        except requests.RequestException as exc:
            latency = (time.perf_counter() - t0) * 1000
            return 503, json.dumps({"error": str(exc)}), latency

