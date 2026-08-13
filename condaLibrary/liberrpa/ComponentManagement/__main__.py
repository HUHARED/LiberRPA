# FileName: __main__.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from liberrpa.ComponentManagement.Common._DiagnosticLog import DiagnosticLog
from liberrpa.ComponentManagement.Adapter.Protocol._Protocol import handle_request
from liberrpa.ComponentManagement.Types._Protocol import DictProtocolResponse_Error

import json
from time import perf_counter
import sys
import traceback


def _build_unexpected_error_response() -> DictProtocolResponse_Error:
    dictDetails: dict[str, object] = {}
    pathDiagnosticLog = DiagnosticLog.logFilePath
    if pathDiagnosticLog is not None:
        dictDetails["diagnosticLogPath"] = str(pathDiagnosticLog)

    return {
        "schemaVersion": 1,
        "ok": False,
        "error": {
            "code": "unexpected_error",
            "message": "Unexpected Component Management backend error.",
            "details": dictDetails,
        },
    }


def _write_protocol_response(responseDict: object) -> None:
    strResponse = json.dumps(
        responseDict,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    sys.stdout.write(strResponse + "\n")
    sys.stdout.flush()


def main() -> int:
    floatStartedAt = perf_counter()

    try:
        pathDiagnosticLog = DiagnosticLog.initialize()
        DiagnosticLog.info("Component Management process started.")
        DiagnosticLog.debug(f"Diagnostic log path: {pathDiagnosticLog}")

        strRequest = sys.stdin.read()
        DiagnosticLog.debug(
            f"Received Protocol request ({len(strRequest.encode('utf-8'))} UTF-8 bytes)."
        )

        dictResponse = handle_request(strRequest)
        _write_protocol_response(dictResponse)
        DiagnosticLog.debug("Protocol response written to stdout.")
        return 0

    except Exception as e:
        DiagnosticLog.exception(
            "Unexpected Component Management backend error.",
            e,
        )

        traceback.print_exc(file=sys.stderr)

        try:
            _write_protocol_response(_build_unexpected_error_response())
            return 0
        except Exception as responseError:
            DiagnosticLog.exception(
                "Failed to write the unexpected-error Protocol response.",
                responseError,
            )
            return 1

    finally:
        if DiagnosticLog.initialized:
            DiagnosticLog.info(
                "Component Management process finished in "
                f"{perf_counter() - floatStartedAt:.3f} seconds."
            )
            DiagnosticLog.close()


if __name__ == "__main__":
    raise SystemExit(main())
