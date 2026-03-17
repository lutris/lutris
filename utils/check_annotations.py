#!/usr/bin/env python3
"""Check that annotations referencing conditional imports are quoted.

Without `from __future__ import annotations`, Python 3.10 evaluates annotations
eagerly at class/function definition time.  Any import that lives under an `if`
or `try` block is conditional — the name may not exist or may be None at runtime.
Using such a name unquoted in a type annotation will crash at import time.

See https://github.com/lutris/lutris/issues/6552 for an example.
"""

import ast
import sys
from pathlib import Path


def has_future_annotations(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            if any(alias.name == "annotations" for alias in node.names):
                return True
    return False


def get_conditional_imports(tree):
    """Return (modules, names) imported inside any `if` or `try` block.

    Any import under a conditional block is suspect — the name may not be
    defined at runtime, so it must be quoted (or deferred) in annotations.

    modules: names brought in via `import X` (so `X.Attr` is a reference)
    names:   names brought in via `from X import Y` (so bare `Y` is a reference)
    """
    modules = set()
    names = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.If, ast.Try)):
            continue
        for child in ast.walk(node):
            match child:
                case ast.Import(names=aliases):
                    for alias in aliases:
                        modules.add(alias.asname or alias.name.split(".")[0])
                case ast.ImportFrom(names=aliases):
                    for alias in aliases:
                        names.add(alias.asname or alias.name)
    return modules, names


def find_unquoted_refs(annotation, names, modules):
    """Return list of unquoted references to conditional imports in an annotation.

    annotation: an ast node representing a type annotation, or None.
    names:      bare names imported via `from x import Y` under a conditional block.
    modules:    module names imported via `import x` under a conditional block.
    """
    match annotation:
        case None | ast.Constant(value=str()):
            return []
        case ast.Name(id=id) if id in names:
            return [id]
        case ast.Attribute(value=ast.Name(id=module), attr=attr) if module in modules or module in names:
            return [f"{module}.{attr}"]
        case ast.Subscript(value=value, slice=ast.Tuple(elts=elts)):
            return find_unquoted_refs(value, names, modules) + [
                ref for elt in elts for ref in find_unquoted_refs(elt, names, modules)
            ]
        case ast.Subscript(value=value, slice=slc):
            return find_unquoted_refs(value, names, modules) + find_unquoted_refs(slc, names, modules)
        case ast.BinOp(left=left, right=right):  # X | Y unions
            return find_unquoted_refs(left, names, modules) + find_unquoted_refs(right, names, modules)
        case _:
            return []


def iter_annotation_errors(node, names, modules):
    """Yield (lineno, ref) for each unquoted conditional import ref in annotations."""
    match node:
        case ast.FunctionDef(args=args, returns=returns) | ast.AsyncFunctionDef(args=args, returns=returns):
            all_args = (
                args.posonlyargs
                + args.args
                + args.kwonlyargs
                + ((args.vararg and [args.vararg]) or [])
                + ((args.kwarg and [args.kwarg]) or [])
            )
            for arg in all_args:
                for ref in find_unquoted_refs(arg.annotation, names, modules):
                    yield arg.annotation.lineno, ref
            for ref in find_unquoted_refs(returns, names, modules):
                yield returns.lineno, ref
        case ast.AnnAssign(annotation=annotation):
            for ref in find_unquoted_refs(annotation, names, modules):
                yield annotation.lineno, ref


def check_file(path):
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (OSError, SyntaxError):
        return []

    if has_future_annotations(tree):
        return []

    modules, names = get_conditional_imports(tree)
    if not modules and not names:
        return []

    errors = set()
    for node in ast.walk(tree):
        for lineno, ref in iter_annotation_errors(node, names, modules):
            errors.add((lineno, ref))
    return sorted(errors)


def main():
    args = sys.argv[1:]
    if args:
        paths = [Path(p) for p in args if p.endswith(".py")]
    else:
        paths = sorted(Path("lutris").rglob("*.py")) + sorted(Path("tests").rglob("*.py"))

    found_errors = False
    for path in paths:
        for lineno, ref in check_file(path):
            print(f"{path}:{lineno}: unquoted annotation '{ref}' references a conditional import")
            found_errors = True

    return 1 if found_errors else 0


if __name__ == "__main__":
    sys.exit(main())
