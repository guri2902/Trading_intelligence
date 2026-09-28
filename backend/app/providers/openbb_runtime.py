from __future__ import annotations

import json
import subprocess
import sys
from typing import Any


class OpenBBRuntimeError(RuntimeError):
    pass


def _serialize(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "dict") and callable(value.dict):
        try:
            return value.dict()
        except Exception:
            pass
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(k): _serialize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize(v) for v in value]
    return str(value)


_SCRIPT = r'''
import json
import sys

request = json.loads(sys.argv[1])
from openbb import obb

obj = obb
for part in request["target"].split("."):
    obj = getattr(obj, part)

kwargs = request.get("kwargs", {})
result = obj(**kwargs)
rows = getattr(result, "results", result)

if rows is None:
    payload = []
elif isinstance(rows, (list, tuple)):
    payload = []
    for row in rows:
        if hasattr(row, "model_dump"):
            payload.append(row.model_dump(mode="json"))
        elif hasattr(row, "dict") and callable(row.dict):
            payload.append(row.dict())
        elif isinstance(row, dict):
            payload.append(row)
        else:
            payload.append(str(row))
elif hasattr(rows, "model_dump"):
    payload = rows.model_dump(mode="json")
elif isinstance(rows, dict):
    payload = rows
else:
    payload = [str(rows)]

print(json.dumps(payload, default=str))
'''


def run_openbb(target: str, kwargs: dict[str, Any] | None = None, timeout: float = 90.0) -> Any:
    request = {"target": target, "kwargs": kwargs or {}}
    proc = subprocess.run(
        [sys.executable, "-c", _SCRIPT, json.dumps(request)],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "OpenBB subprocess failed").strip()
        raise OpenBBRuntimeError(detail)
    output = proc.stdout.strip()
    if not output:
        return []
    try:
        return json.loads(output)
    except json.JSONDecodeError as exc:
        raise OpenBBRuntimeError(f"OpenBB returned invalid JSON: {output[:500]}") from exc


def check_openbb(timeout: float = 30.0) -> dict[str, Any]:
    script = "from openbb import obb; print('ok', hasattr(obb, 'equity'), hasattr(obb, 'news'), hasattr(obb, 'economy'))"
    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "OpenBB import failed").strip()
        return {"available": False, "message": detail}
    return {"available": True, "message": proc.stdout.strip()}
