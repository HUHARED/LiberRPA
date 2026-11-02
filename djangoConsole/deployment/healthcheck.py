# FileName: healthcheck.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import sys
from http.client import HTTPConnection, HTTPException


def main() -> int:
    # Check the proxy, running application and database without loading deployment dependencies.
    connection = HTTPConnection("127.0.0.1", 52100, timeout=3)
    try:
        connection.request(
            "GET",
            "/api/health/database/",
            headers={"X-Forwarded-For": "127.0.0.1"},
        )
        response = connection.getresponse()
        if response.status != 200:
            print(
                f"Console health check returned HTTP {response.status}.",
                file=sys.stderr,
            )
            return 1
        return 0
    except (OSError, HTTPException) as e:
        print(
            f"Console health check failed: {type(e).__name__}: {e}",
            file=sys.stderr,
        )
        return 1
    finally:
        connection.close()


if __name__ == "__main__":
    sys.exit(main())
