# FileName: analyzeManagedImportNames.py

"""Find known Python names that are referenced without being bound in the file."""

import ast
import json
import sys


def _get_import_binding(alias: ast.alias, boolFromImport: bool) -> str:
    if alias.asname is not None:
        return alias.asname
    if boolFromImport:
        return alias.name
    return alias.name.split(".", 1)[0]


def _collect_bound_names(tree: ast.AST) -> set[str]:
    setBoundName: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            setBoundName.add(node.id)
            continue

        if isinstance(node, ast.arg):
            setBoundName.add(node.arg)
            continue

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            setBoundName.add(node.name)
            continue

        if isinstance(node, ast.Import):
            setBoundName.update(
                _get_import_binding(alias, False) for alias in node.names
            )
            continue

        if isinstance(node, ast.ImportFrom):
            setBoundName.update(
                _get_import_binding(alias, True) for alias in node.names
            )
            continue

        if isinstance(node, ast.ExceptHandler) and node.name is not None:
            setBoundName.add(node.name)
            continue

        if isinstance(node, ast.MatchAs) and node.name is not None:
            setBoundName.add(node.name)
            continue

        if isinstance(node, ast.MatchStar) and node.name is not None:
            setBoundName.add(node.name)
            continue

        if isinstance(node, ast.MatchMapping) and node.rest is not None:
            setBoundName.add(node.rest)

    return setBoundName


def get_referenced_known_names(source: str, knownNames: list[str]) -> list[str] | None:
    """Return None when the complete Python file is not parseable."""
    try:
        tree = ast.parse(source.lstrip("\ufeff"))
    except (SyntaxError, ValueError, RecursionError):
        return None

    setKnownName = set(knownNames)
    setLoadedName = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name)
        and isinstance(node.ctx, ast.Load)
        and node.id in setKnownName
    }
    setBoundName = _collect_bound_names(tree)
    return sorted(setLoadedName - setBoundName)


def main() -> None:
    request = json.load(sys.stdin)
    result = get_referenced_known_names(request["source"], request["knownNames"])
    json.dump({"referencedNames": result}, sys.stdout, ensure_ascii=True)


if __name__ == "__main__":
    main()
