"""Optional-dependency shims.

This module re-exports Pydantic, Typer, Rich and PyYAML when they are
installed, and otherwise provides tiny stdlib-only replacements that are just
large enough to run the bio-manim-lab pipeline on the golden-cache path.

The production path — when the user runs `pip install -e .` — picks up the
real libraries automatically and the shims are never touched.

This file exists so the repo can `python -m biomanim run` successfully even
in a fresh environment where dependencies have not yet been installed.
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, get_args, get_origin, get_type_hints


# ============================================================================
# PYDANTIC SHIM
# ============================================================================

try:
    from pydantic import BaseModel, Field, ConfigDict, field_validator  # type: ignore
    from pydantic import ValidationError  # type: ignore
    PYDANTIC_AVAILABLE = True

    def _model_dump(model, mode: str = "python"):  # pragma: no cover
        return model.model_dump(mode=mode)

except ImportError:  # stdlib fallback
    PYDANTIC_AVAILABLE = False

    class ValidationError(ValueError):
        """Drop-in replacement for pydantic.ValidationError."""

    def ConfigDict(**kwargs):  # noqa: N802 (match pydantic API)
        return dict(kwargs)

    def Field(default=..., *, default_factory=None, description: str | None = None, **_):  # noqa: N802
        return _FieldInfo(default=default, default_factory=default_factory, description=description)

    @dataclass
    class _FieldInfo:
        default: Any = ...
        default_factory: Callable[[], Any] | None = None
        description: str | None = None

    def field_validator(*fields, **_):
        def deco(fn):
            fn.__validator_fields__ = fields  # type: ignore[attr-defined]
            return fn
        return deco

    class _ModelMeta(type):
        def __new__(mcls, name, bases, ns):
            cls = super().__new__(mcls, name, bases, ns)
            # Collect field info from the class body.
            hints: dict[str, Any] = {}
            for base in reversed(bases):
                hints.update(getattr(base, "__biomanim_hints__", {}))
            try:
                hints.update(get_type_hints(cls))
            except Exception:
                pass  # forward refs handled by the dict merge above
            cls.__biomanim_hints__ = hints
            # Collect validators.
            validators: dict[str, list[Callable]] = {}
            for base in reversed(bases):
                for k, v in getattr(base, "__biomanim_validators__", {}).items():
                    validators.setdefault(k, []).extend(v)
            for attr in ns.values():
                raw = attr.__func__ if isinstance(attr, classmethod) else attr
                fields_ = getattr(raw, "__validator_fields__", None)
                if fields_:
                    for f in fields_:
                        validators.setdefault(f, []).append(raw)
            cls.__biomanim_validators__ = validators
            return cls

    class BaseModel(metaclass=_ModelMeta):
        """Minimal Pydantic-compatible base class."""

        model_config: dict = {}

        def __init__(self, **data: Any) -> None:
            hints = type(self).__biomanim_hints__
            cfg = getattr(type(self), "model_config", {}) or {}
            if cfg.get("extra") == "forbid":
                extra = set(data) - set(hints)
                if extra:
                    raise ValidationError(f"{type(self).__name__}: unknown fields {sorted(extra)}")
            for name, tp in hints.items():
                if name in data:
                    value = _coerce(data[name], tp)
                else:
                    default = getattr(type(self), name, _MISSING)
                    if isinstance(default, _FieldInfo):
                        if default.default_factory is not None:
                            value = default.default_factory()
                        elif default.default is not ...:
                            value = default.default
                        else:
                            raise ValidationError(f"{type(self).__name__}: missing field {name!r}")
                    elif default is _MISSING:
                        raise ValidationError(f"{type(self).__name__}: missing field {name!r}")
                    else:
                        value = default
                # Run validators.
                for fn in type(self).__biomanim_validators__.get(name, []):
                    try:
                        value = fn(type(self), value)
                    except Exception as e:  # noqa: BLE001
                        raise ValidationError(f"{type(self).__name__}.{name}: {e}") from e
                object.__setattr__(self, name, value)

        @classmethod
        def model_validate(cls, data: Any):
            if isinstance(data, cls):
                return data
            if not isinstance(data, dict):
                raise ValidationError(f"{cls.__name__}: expected dict, got {type(data).__name__}")
            return cls(**data)

        @classmethod
        def model_validate_json(cls, text: str | bytes):
            return cls.model_validate(json.loads(text))

        def model_dump(self, mode: str = "python") -> dict:  # noqa: ARG002
            out: dict[str, Any] = {}
            for name in type(self).__biomanim_hints__:
                out[name] = _dump_value(getattr(self, name))
            return out

        def model_dump_json(self, **kwargs) -> str:
            return json.dumps(self.model_dump(mode="json"), default=str, **kwargs)

        @classmethod
        def model_json_schema(cls) -> dict:
            return {"title": cls.__name__, "type": "object",
                    "properties": {k: {"type": "any"} for k in cls.__biomanim_hints__}}

    _MISSING = object()

    def _dump_value(v: Any) -> Any:
        if isinstance(v, BaseModel):
            return v.model_dump(mode="json")
        if isinstance(v, dict):
            return {k: _dump_value(x) for k, x in v.items()}
        if isinstance(v, (list, tuple)):
            return [_dump_value(x) for x in v]
        return v

    def _coerce(value: Any, tp: Any) -> Any:
        origin = get_origin(tp)
        args = get_args(tp)
        if tp is Any:
            return value
        if origin is None:
            if isinstance(tp, type) and issubclass(tp, BaseModel):
                if isinstance(value, tp):
                    return value
                if isinstance(value, dict):
                    return tp(**value)
                raise ValidationError(f"expected {tp.__name__}, got {type(value).__name__}")
            if tp is float and isinstance(value, int):
                return float(value)
            if tp in (str, int, float, bool):
                if not isinstance(value, tp):
                    # Allow None if field is declared Optional upstream (origin handled there).
                    raise ValidationError(f"expected {tp.__name__}, got {type(value).__name__}")
                return value
            return value
        # Literal[...]
        try:
            from typing import Literal  # noqa: WPS433
            if origin is Literal:
                if value not in args:
                    raise ValidationError(f"value {value!r} not in {args}")
                return value
        except ImportError:
            pass
        # Optional / Union
        if origin is type(None) or (str(origin) in ("typing.Union", "types.UnionType")):
            if value is None and type(None) in args:
                return None
            for sub in args:
                if sub is type(None):
                    continue
                try:
                    return _coerce(value, sub)
                except Exception:
                    continue
            raise ValidationError(f"value {value!r} does not match {tp}")
        if origin in (list, tuple):
            if not isinstance(value, (list, tuple)):
                raise ValidationError(f"expected list, got {type(value).__name__}")
            sub = args[0] if args else Any
            return [_coerce(x, sub) for x in value]
        if origin is dict:
            if not isinstance(value, dict):
                raise ValidationError(f"expected dict, got {type(value).__name__}")
            return dict(value)
        return value


# ============================================================================
# TYPER SHIM — a minimal Typer-compatible surface on top of argparse.
# ============================================================================

try:
    import typer  # type: ignore
    TYPER_AVAILABLE = True
except ImportError:
    TYPER_AVAILABLE = False

    class BadParameter(Exception):
        pass

    class _TyperOption:
        def __init__(self, default, *flags, help: str = "", **_):  # noqa: A002
            self.default = default
            self.flags = [f for f in flags if f]
            self.help = help

    def Option(default=None, *flags, help: str = "", **kwargs):  # noqa: N802
        return _TyperOption(default, *flags, help=help, **kwargs)

    class Typer:
        def __init__(self, **kwargs) -> None:
            self.help = kwargs.get("help", "")
            self.commands: dict[str, Callable] = {}

        def command(self, name: str | None = None, **_):
            def deco(fn):
                self.commands[name or fn.__name__.replace("_", "-")] = fn
                return fn
            return deco

        def __call__(self, argv: list[str] | None = None) -> int:  # noqa: D401
            import argparse
            parser = argparse.ArgumentParser(prog="biomanim", description=self.help)
            sub = parser.add_subparsers(dest="cmd")
            for name, fn in self.commands.items():
                p = sub.add_parser(name, help=(fn.__doc__ or "").strip())
                _attach_args(p, fn)
            args = parser.parse_args(argv)
            if not args.cmd:
                parser.print_help()
                return 0
            fn = self.commands[args.cmd]
            kwargs = _extract_kwargs(fn, args)
            try:
                fn(**kwargs)
            except BadParameter as e:
                print(f"error: {e}", file=sys.stderr)
                return 2
            return 0

    def _attach_args(parser, fn):
        import inspect
        sig = inspect.signature(fn)
        for name, param in sig.parameters.items():
            default = param.default
            if isinstance(default, _TyperOption):
                flags = default.flags or [f"--{name.replace('_', '-')}"]
                kwargs = {"default": default.default, "help": default.help}
                if isinstance(default.default, bool):
                    kwargs["action"] = "store_true"
                    kwargs.pop("default")
                parser.add_argument(*flags, dest=name, **kwargs)
            else:
                parser.add_argument(f"--{name.replace('_', '-')}", dest=name,
                                    default=default if default is not inspect.Parameter.empty else None)

    def _extract_kwargs(fn, args):
        import inspect
        sig = inspect.signature(fn)
        return {name: getattr(args, name, None) for name in sig.parameters}

    # Typer, Option, BadParameter are exposed as module-level attrs below.


# ============================================================================
# RICH SHIM
# ============================================================================

try:
    from rich.console import Console as RichConsole  # type: ignore
    from rich.tree import Tree as RichTree  # type: ignore
    RICH_AVAILABLE = True
    Console = RichConsole
    Tree = RichTree

except ImportError:
    RICH_AVAILABLE = False
    _ANSI = re.compile(r"\[(/?[a-zA-Z0-9#_ ]+)\]")

    class Console:
        is_terminal = sys.stdout.isatty()

        def print(self, *args, **_) -> None:
            text = " ".join(str(a) for a in args)
            print(_ANSI.sub("", text))

        def rule(self, *_, **__) -> None:
            print("-" * 60)

        def print_json(self, data: str) -> None:
            try:
                print(json.dumps(json.loads(data), indent=2))
            except Exception:
                print(data)

        def print_exception(self, **_) -> None:  # pragma: no cover
            import traceback
            traceback.print_exc()

    class Tree:
        def __init__(self, label: str) -> None:
            self.label = _ANSI.sub("", label)
            self.children: list[Tree] = []

        def add(self, label: str) -> "Tree":
            t = Tree(label)
            self.children.append(t)
            return t

        def __str__(self) -> str:
            lines: list[str] = [self.label]
            self._render(lines, "")
            return "\n".join(lines)

        def _render(self, lines: list[str], prefix: str) -> None:
            for i, child in enumerate(self.children):
                last = i == len(self.children) - 1
                lines.append(prefix + ("└── " if last else "├── ") + child.label)
                child._render(lines, prefix + ("    " if last else "│   "))


# ============================================================================
# YAML SHIM — minimal parser for our config files (simple key: value, lists)
# ============================================================================

try:
    import yaml  # type: ignore
    YAML_AVAILABLE = True

    def safe_load_yaml(text: str) -> dict:
        return yaml.safe_load(text) or {}

except ImportError:
    YAML_AVAILABLE = False

    def safe_load_yaml(text: str) -> dict:  # noqa: C901
        """Tiny YAML subset parser.

        Handles our config files: nested mappings, lists of strings/numbers,
        scalar strings, quoted strings, integers, floats, booleans, `~`/`null`.
        Comments (#) and blank lines are ignored. Mapping and list indentation
        must be consistent (2 or 4 spaces).
        """
        lines = [ln.rstrip() for ln in text.splitlines()]
        lines = [ln for ln in lines if ln.strip() and not ln.lstrip().startswith("#")]
        # Strip inline comments outside quotes.
        def _strip_inline(ln: str) -> str:
            in_str = False
            quote = ""
            out = []
            for ch in ln:
                if in_str:
                    out.append(ch)
                    if ch == quote:
                        in_str = False
                elif ch in ("'", '"'):
                    in_str = True
                    quote = ch
                    out.append(ch)
                elif ch == "#":
                    break
                else:
                    out.append(ch)
            return "".join(out).rstrip()
        lines = [_strip_inline(ln) for ln in lines]

        root: Any = {}
        stack: list[tuple[int, Any]] = [(-1, root)]

        def _cast(v: str) -> Any:
            s = v.strip()
            if not s:
                return None
            if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
                return s[1:-1]
            low = s.lower()
            if low in ("null", "~", ""):
                return None
            if low in ("true", "yes", "on"):
                return True
            if low in ("false", "no", "off"):
                return False
            try:
                if "." in s:
                    return float(s)
                return int(s)
            except ValueError:
                return s

        for ln in lines:
            indent = len(ln) - len(ln.lstrip(" "))
            content = ln.strip()
            while stack and stack[-1][0] >= indent:
                stack.pop()
            parent = stack[-1][1]

            if content.startswith("- "):
                item = content[2:]
                if not isinstance(parent, list):
                    # Convert last key of grand-parent from None to list
                    # This branch is only reached if the parent mapping expected a list.
                    raise ValueError(f"list item without list parent: {ln!r}")
                if ":" in item and not (item.startswith('"') or item.startswith("'")):
                    key, _, rest = item.partition(":")
                    obj: dict = {}
                    obj[key.strip()] = _cast(rest) if rest.strip() else {}
                    parent.append(obj)
                    if not rest.strip():
                        stack.append((indent + 2, obj[key.strip()]))
                else:
                    parent.append(_cast(item))
                continue

            if ":" in content:
                key, _, rest = content.partition(":")
                key = key.strip()
                rest = rest.strip()
                if not isinstance(parent, dict):
                    raise ValueError(f"mapping entry without dict parent: {ln!r}")
                if rest == "":
                    # Could be dict or list; defer decision.
                    new: dict | list = {}
                    parent[key] = new
                    stack.append((indent, new))
                else:
                    parent[key] = _cast(rest)
                continue
            raise ValueError(f"unparseable line: {ln!r}")

        return root if isinstance(root, dict) else {}


# ============================================================================
# SLUGIFY SHIM
# ============================================================================

try:
    from slugify import slugify as _slugify  # type: ignore
    SLUGIFY_AVAILABLE = True
except ImportError:
    SLUGIFY_AVAILABLE = False

    def _slugify(text: str, max_length: int | None = None) -> str:
        s = text.lower().strip()
        s = re.sub(r"[^a-z0-9]+", "-", s)
        s = s.strip("-")
        if max_length is not None:
            s = s[:max_length].rstrip("-")
        return s or "x"


def slugify(text: str, max_length: int | None = None) -> str:
    return _slugify(text, max_length=max_length) if SLUGIFY_AVAILABLE else _slugify(text, max_length)


if TYPER_AVAILABLE:
    # Re-export the real typer symbols under the names the shim path uses.
    Typer = typer.Typer  # type: ignore[attr-defined]
    Option = typer.Option  # type: ignore[attr-defined]
    BadParameter = typer.BadParameter  # type: ignore[attr-defined]


__all__ = [
    "BaseModel",
    "Field",
    "ConfigDict",
    "field_validator",
    "ValidationError",
    "Typer",
    "Option",
    "BadParameter",
    "Console",
    "Tree",
    "safe_load_yaml",
    "slugify",
    "PYDANTIC_AVAILABLE",
    "TYPER_AVAILABLE",
    "RICH_AVAILABLE",
    "YAML_AVAILABLE",
    "SLUGIFY_AVAILABLE",
]
