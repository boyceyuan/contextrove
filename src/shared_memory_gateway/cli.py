"""One JSON request per invocation; also useful for independent-process tests."""

import argparse
import json
import sys

from .core import Memory, MemoryError

METHODS = ("read", "search", "bootstrap", "propose_update", "apply_update", "forget")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("method", choices=METHODS)
    args = parser.parse_args()
    try:
        parameters = json.load(sys.stdin)
        result = getattr(Memory(args.config), args.method)(**parameters)
        print(json.dumps(result, ensure_ascii=False))
    except MemoryError as exc:
        print(json.dumps({"error": {"code": exc.code, "message": str(exc)}}))
        raise SystemExit(1)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"error": {"code": "INVALID_REQUEST_OR_CONFIG", "type": type(exc).__name__}}))
        raise SystemExit(2)


if __name__ == "__main__":
    main()
