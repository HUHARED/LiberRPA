# FileName: HandleLogger.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


import inspect
import json
from liberrpa.Logging import Logger

# Retrieve all functions from the object
functions = inspect.getmembers(Logger, predicate=inspect.isfunction)
# print(functions)

snippets = {}

for name, func in functions:
    if name.startswith("_"):
        continue

    params = inspect.signature(func).parameters

    param_parts = []
    intIdx = 1
    for i, (param_name, param) in enumerate(params.items()):
        if param_name == "self":
            continue
        if param.default is inspect.Parameter.empty:
            param_parts.append(f"{param_name}=${intIdx}")
        else:
            default_value = repr(param.default)
            param_parts.append(f"{param_name}=${{{intIdx}:{default_value}}}")
        intIdx += 1

    param_str = ", ".join(param_parts)

    body = f"Log.{name}({param_str})"

    # docstring = json.dumps(inspect.getdoc(func)) or ""
    docstring = inspect.getdoc(func) or ""

    # Define the snippet structure
    snippets[name] = {"prefix": "Log." + name, "body": body, "description": docstring}

print()
print(json.dumps(snippets))
