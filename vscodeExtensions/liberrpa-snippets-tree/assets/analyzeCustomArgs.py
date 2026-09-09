# FileName: analyzeCustomArgs.py

"""Extract source-defined CustomArgs key paths without importing project code."""

import ast
import json
import sys


_CUSTOM_ARGS_NAME = "CustomArgs"


class _ScopeBindings(ast.NodeVisitor):
    """Detect obvious rebinding in one lexical scope, not execution order."""

    def __init__(self) -> None:
        self.hasRebinding = False
        self.hasCanonicalImport = False
        self.hasGlobal = False
        self.hasNonlocal = False

    def visit_Name(self, node: ast.Name) -> None:
        if node.id == _CUSTOM_ARGS_NAME and isinstance(node.ctx, (ast.Store, ast.Del)):
            self.hasRebinding = True

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            if (alias.asname or alias.name) != _CUSTOM_ARGS_NAME:
                continue
            if (
                node.level == 0
                and node.module == "liberrpa.Modules"
                and alias.name == _CUSTOM_ARGS_NAME
            ):
                self.hasCanonicalImport = True
            else:
                self.hasRebinding = True

    def visit_Import(self, node: ast.Import) -> None:
        if any(
            (alias.asname or alias.name.split(".")[0]) == _CUSTOM_ARGS_NAME
            for alias in node.names
        ):
            self.hasRebinding = True

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        if node.name == _CUSTOM_ARGS_NAME:
            self.hasRebinding = True
        # Do not descend into another scope.

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if node.name == _CUSTOM_ARGS_NAME:
            self.hasRebinding = True

    def visit_Lambda(self, node: ast.Lambda) -> None:
        pass

    def visit_ListComp(
        self, node: ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp
    ) -> None:
        # Comprehension targets have their own scope. Named expressions can bind outside that scope; reject a same-name assignment conservatively.
        for child in ast.walk(node):
            if isinstance(child, ast.NamedExpr) and isinstance(child.target, ast.Name):
                if child.target.id == _CUSTOM_ARGS_NAME:
                    self.hasRebinding = True

    visit_SetComp = visit_ListComp
    visit_DictComp = visit_ListComp
    visit_GeneratorExp = visit_ListComp

    def visit_Global(self, node: ast.Global) -> None:
        self.hasGlobal |= _CUSTOM_ARGS_NAME in node.names

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        self.hasNonlocal |= _CUSTOM_ARGS_NAME in node.names

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.name == _CUSTOM_ARGS_NAME:
            self.hasRebinding = True
        self.generic_visit(node)

    def visit_MatchAs(self, node: ast.MatchAs) -> None:
        if node.name == _CUSTOM_ARGS_NAME:
            self.hasRebinding = True
        self.generic_visit(node)

    def visit_MatchStar(self, node: ast.MatchStar) -> None:
        if node.name == _CUSTOM_ARGS_NAME:
            self.hasRebinding = True

    def visit_MatchMapping(self, node: ast.MatchMapping) -> None:
        if node.rest == _CUSTOM_ARGS_NAME:
            self.hasRebinding = True
        self.generic_visit(node)


def _get_key_path(node: ast.expr) -> list[str] | None:
    listKey: list[str] = []
    while isinstance(node, ast.Subscript):
        if not isinstance(node.slice, ast.Constant) or not isinstance(
            node.slice.value, str
        ):
            return None
        listKey.append(node.slice.value)
        node = node.value
    if not isinstance(node, ast.Name) or node.id != _CUSTOM_ARGS_NAME or not listKey:
        return None
    return list(reversed(listKey))


class _KeyPathCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.setKeyPath: set[tuple[str, ...]] = set()
        self.scopeAllowsCustomArgs = True
        self.moduleAllowsCustomArgs = True

    def _visit_scope(
        self, body: list[ast.stmt], args: ast.arguments | None = None
    ) -> None:
        bindings = _ScopeBindings()
        for statement in body:
            bindings.visit(statement)
        if args is not None:
            listArg = [*args.posonlyargs, *args.args, *args.kwonlyargs]
            if args.vararg is not None:
                listArg.append(args.vararg)
            if args.kwarg is not None:
                listArg.append(args.kwarg)
            bindings.hasRebinding |= any(
                arg.arg == _CUSTOM_ARGS_NAME for arg in listArg
            )

        boolPrevious = self.scopeAllowsCustomArgs
        if bindings.hasRebinding or bindings.hasNonlocal:
            self.scopeAllowsCustomArgs = False
        elif bindings.hasCanonicalImport:
            self.scopeAllowsCustomArgs = True
        elif bindings.hasGlobal:
            self.scopeAllowsCustomArgs = self.moduleAllowsCustomArgs
        try:
            for statement in body:
                self.visit(statement)
        finally:
            self.scopeAllowsCustomArgs = boolPrevious

    def visit_Module(self, node: ast.Module) -> None:
        bindings = _ScopeBindings()
        for statement in node.body:
            bindings.visit(statement)
        # The conventional unaliased name is accepted even before its import is inserted. Explicit rebinding or an unrelated import disables it.
        self.moduleAllowsCustomArgs = not bindings.hasRebinding
        self.scopeAllowsCustomArgs = self.moduleAllowsCustomArgs
        self._visit_scope(node.body)

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        # A type parameter named CustomArgs also shadows the project variable.
        if any(parameter.name == _CUSTOM_ARGS_NAME for parameter in node.type_params):
            return
        self._visit_scope(node.body, node.args)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        # Class bodies and method lookup have different scoping rules.
        # They are outside this small source-indexer's supported initialization patterns.
        pass

    def visit_Assign(self, node: ast.Assign) -> None:
        if self.scopeAllowsCustomArgs:
            for target in node.targets:
                self._collect_assignment(target, node.value)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if self.scopeAllowsCustomArgs and node.value is not None:
            self._collect_assignment(node.target, node.value)

    def _collect_assignment(self, target: ast.expr, value: ast.expr) -> None:
        listKey = _get_key_path(target)
        if listKey is None:
            return
        self.setKeyPath.add(tuple(listKey))
        self._collect_dict(value, listKey)

    def _collect_dict(self, node: ast.expr, listParentKey: list[str]) -> None:
        if not isinstance(node, ast.Dict):
            return
        # For repeated literal keys in one dictionary, keep the last value.
        dictValue: dict[str, ast.expr] = {}
        for key, value in zip(node.keys, node.values):
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                dictValue[key.value] = value
        for strKey, value in dictValue.items():
            listKey = [*listParentKey, strKey]
            self.setKeyPath.add(tuple(listKey))
            self._collect_dict(value, listKey)


def extract_key_paths(source: str) -> list[list[str]] | None:
    """Return None for incomplete/invalid Python; never repair or evaluate it."""
    try:
        tree = ast.parse(source.lstrip("\ufeff"))
        collector = _KeyPathCollector()
        collector.visit(tree)
        return [list(keyPath) for keyPath in sorted(collector.setKeyPath)]
    except (SyntaxError, ValueError, RecursionError):
        return None


def main() -> None:
    request = json.load(sys.stdin)
    result = [
        {"filePath": source["filePath"], "keyPaths": extract_key_paths(source["text"])}
        for source in request
    ]
    json.dump(result, sys.stdout, ensure_ascii=True)


if __name__ == "__main__":
    main()
