"""OpenAPI JSON-object tools and credential-free, replayable HTTP requests."""

from __future__ import annotations

import copy
import json
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

import requests
from jsonschema import Draft202012Validator

from detect.contracts import Request

_SECRET_HEADERS = {"authorization", "cookie", "set-cookie", "x-api-key", "proxy-authorization"}


def _resolve(spec: dict, value: Any, seen: tuple[str, ...] = ()) -> Any:
    if isinstance(value, list):
        return [_resolve(spec, item, seen) for item in value]
    if not isinstance(value, dict):
        return value
    if "$ref" in value:
        ref = value["$ref"]
        if not ref.startswith("#/") or ref in seen:
            raise ValueError(f"unsupported external or recursive OpenAPI reference: {ref}")
        node = spec
        for part in ref[2:].split("/"):
            node = node[part.replace("~1", "/").replace("~0", "~")]
        return _resolve(
            spec, {**node, **{k: v for k, v in value.items() if k != "$ref"}}, (*seen, ref)
        )
    return {key: _resolve(spec, item, seen) for key, item in value.items()}


class OpenAPIAdapter:
    """Supports scalar path/query/header parameters and object JSON bodies.

    Unsupported parameter serialization and ambiguous flattened names fail at
    load time instead of silently producing a different request during replay.
    """

    def __init__(self, spec_or_path: str | Path | dict, base_url: str):
        origin = urlsplit(base_url)
        if (
            origin.scheme not in {"http", "https"}
            or not origin.netloc
            or origin.username
            or origin.password
            or origin.query
            or origin.fragment
            or origin.path not in {"", "/"}
        ):
            raise ValueError("base_url must be an HTTP(S) origin without embedded credentials")
        self.base_url = base_url.rstrip("/")
        if isinstance(spec_or_path, (str, Path)):
            self.spec = json.loads(Path(spec_or_path).read_text(encoding="utf-8"))
        else:
            self.spec = copy.deepcopy(spec_or_path)
        self.operations: dict[str, dict] = {}
        self._parse_spec()

    def _parse_spec(self) -> None:
        for path, raw_item in self.spec.get("paths", {}).items():
            item = _resolve(self.spec, raw_item)
            for method in ("get", "post", "put", "delete", "patch", "head", "options"):
                if method not in item:
                    continue
                op = item[method]
                clean_path = re.sub(r"[{}]", "", path).strip("/").replace("/", "_")
                name = op.get("operationId") or f"{method}_{clean_path}".rstrip("_")
                if name in self.operations:
                    raise ValueError(f"duplicate operationId: {name}")
                properties, required, parameters = {}, [], {}
                # Operation-level parameters override path-level parameters.
                merged = {
                    (p["in"], p["name"]): p
                    for p in [*item.get("parameters", []), *op.get("parameters", [])]
                }
                for (location, key), param in merged.items():
                    if location == "header" and key.lower() in _SECRET_HEADERS | {"auth"}:
                        continue
                    if location not in {"path", "query", "header"}:
                        raise ValueError(f"unsupported parameter location: {location}")
                    schema = param.get("schema", {"type": "string"})
                    if schema.get("type") in {"object", "array"}:
                        raise ValueError(f"unsupported parameter serialization: {name}.{key}")
                    if key in properties:
                        raise ValueError(f"ambiguous flattened parameter: {name}.{key}")
                    properties[key] = schema
                    parameters[key] = location
                    if param.get("required") or location == "path":
                        required.append(key)
                body = op.get("requestBody")
                body_keys = []
                body_schema = None
                if body:
                    schema = body.get("content", {}).get("application/json", {}).get("schema")
                    if not schema or schema.get("type", "object") != "object":
                        raise ValueError(f"only object JSON request bodies supported: {name}")
                    if any(key in schema for key in ("allOf", "anyOf", "oneOf")):
                        raise ValueError(f"composed root request bodies are unsupported: {name}")
                    body_schema = schema
                    body_keys = list(schema.get("properties", {}))
                    if set(properties) & set(body_keys):
                        raise ValueError(f"body and parameter names overlap: {name}")
                    properties.update(schema.get("properties", {}))
                    required.extend(schema.get("required", []))
                tool_schema = {
                    "type": "object",
                    "properties": properties,
                    "required": list(dict.fromkeys(required)),
                    "additionalProperties": False,
                }
                Draft202012Validator.check_schema(tool_schema)
                self.operations[name] = {
                    "method": method.upper(),
                    "path": path,
                    "parameters": parameters,
                    "body_keys": body_keys,
                    "body_schema": body_schema,
                    "has_body": bool(body),
                    "schema": tool_schema,
                    "tool_definition": {
                        "type": "function",
                        "function": {
                            "name": name,
                            "description": op.get("summary") or op.get("description") or name,
                            "parameters": tool_schema,
                        },
                    },
                }

    def get_tool_names(self) -> set[str]:
        return set(self.operations)

    def get_tool_definitions(self, tool_names: list[str] | None = None) -> list[dict]:
        names = list(self.operations) if tool_names is None else tool_names
        unknown = set(names) - set(self.operations)
        if unknown:
            raise ValueError(f"unknown tools: {sorted(unknown)}")
        return [copy.deepcopy(self.operations[name]["tool_definition"]) for name in names]

    def prepare_request(self, tool_name: str, arguments: dict[str, Any]) -> Request:
        if tool_name not in self.operations:
            raise ValueError(f"unknown tool: {tool_name}")
        op = self.operations[tool_name]
        Draft202012Validator(op["schema"]).validate(arguments)
        path, query, headers = op["path"], {}, {}
        for key, location in op["parameters"].items():
            if key not in arguments or arguments[key] is None:
                continue
            value = arguments[key]
            if location == "path":
                path = path.replace("{" + key + "}", quote(str(value), safe=""))
            elif location == "query":
                query[key] = str(value).lower() if isinstance(value, bool) else value
            else:
                headers[key] = str(value)
        body = {k: arguments[k] for k in op["body_keys"] if k in arguments}
        if op["body_schema"] is not None:
            Draft202012Validator(op["body_schema"]).validate(body)
        return Request(
            method=op["method"],
            path=path,
            query=query,
            headers=headers,
            json_body=body if op["has_body"] else None,
        )

    def execute_request(
        self, request: Request, auth_token: str = "", timeout: float = 10.0
    ) -> tuple[int | None, str, float]:
        headers = dict(request.headers)
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
        started = time.perf_counter()
        try:
            response = requests.request(
                request.method,
                f"{self.base_url}{request.path}",
                params=request.query,
                json=request.json_body,
                headers=headers,
                timeout=timeout,
                allow_redirects=False,
            )
            return response.status_code, response.text, (time.perf_counter() - started) * 1000
        except requests.RequestException as exc:
            # No invented HTTP 503, and no credential-bearing request in the error.
            return (
                None,
                json.dumps({"error": type(exc).__name__}),
                (time.perf_counter() - started) * 1000,
            )

    def execute_tool(
        self, tool_name: str, arguments: dict[str, Any], auth_token: str = "", timeout: float = 10.0
    ) -> tuple[int | None, str, float]:
        request = self.prepare_request(tool_name, arguments)
        return self.execute_request(request, auth_token, timeout)
