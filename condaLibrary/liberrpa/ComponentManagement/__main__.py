# FileName: __main__.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from liberrpa.ComponentManagement._Protocol import handle_request

import json
import sys
import traceback


def main() -> int:
    try:
        strRequest = sys.stdin.read()
        dictResponse = handle_request(strRequest)
        strResponse = json.dumps(dictResponse, ensure_ascii=False, separators=(",", ":"))
        sys.stdout.write(strResponse + "\n")
        sys.stdout.flush()
        return 0
    except Exception:
        traceback.print_exc(file=sys.stderr)

        try:
            sys.stdout.write(
                '{"schemaVersion":1,"ok":false,"error":{"code":"unexpected_error",'
                '"message":"Unexpected Component Management backend error.","details":{}}}\n'
            )
            sys.stdout.flush()
            return 0
        except Exception:
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
