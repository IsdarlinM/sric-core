from __future__ import annotations

import importlib
import os
import re
import sys

from .errors import debug_exceptions_enabled, safe_exception_message


_MODULE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")


def _render_failure(exc: BaseException) -> int:
    if debug_exceptions_enabled():
        raise exc
    print(
        f"Command runner error: {type(exc).__name__}: {safe_exception_message(exc)}",
        file=sys.stderr,
    )
    return 1


def main() -> int:
    module_name = os.environ.get("SENTINEL_CLI_MODULE", "")
    if not module_name or not _MODULE_RE.fullmatch(module_name):
        print("Invalid or missing SENTINEL_CLI_MODULE", file=sys.stderr)
        return 2
    try:
        module = importlib.import_module(module_name)
        run = getattr(module, "run", None)
        if not callable(run):
            print(f"{module_name} does not expose a callable run()", file=sys.stderr)
            return 2
        sys.argv = [module_name.split(".", 1)[0], *sys.argv[1:]]
        result = run()
    except SystemExit as exc:
        code = exc.code
        if isinstance(code, int):
            return code
        return 0 if code in (None, "") else 1
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        return _render_failure(exc)
    return int(result) if isinstance(result, int) else 0


if __name__ == "__main__":
    raise SystemExit(main())
