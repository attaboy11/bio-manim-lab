"""Tiny local orchestration helper.

Implements the only useful pattern from `badclaude` (interrupt + retry) without
coupling the product to it. Stages are passed in as small callables; the
supervisor handles timeouts, single-retry, logging, and a clean failure
summary.
"""

from __future__ import annotations

import signal
import time
import traceback
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Callable, TypeVar

from .._compat import Console

T = TypeVar("T")
console = Console()


class StageTimeout(RuntimeError):
    pass


class StageInterrupt(RuntimeError):
    pass


@dataclass
class StageResult:
    name: str
    ok: bool
    duration_s: float
    error: str | None = None


@dataclass
class Supervisor:
    timeout_seconds: int = 300
    max_retries: int = 1
    fail_fast: bool = False
    results: list[StageResult] = field(default_factory=list)

    def run(self, name: str, fn: Callable[[], T]) -> T | None:
        attempts = 0
        last_error: str | None = None
        start = time.time()
        while attempts <= self.max_retries:
            attempts += 1
            console.print(f"[cyan]▶ stage[/] [bold]{name}[/]"
                          + (f" [dim](retry {attempts - 1})[/]" if attempts > 1 else ""))
            try:
                with _timeout(self.timeout_seconds):
                    result = fn()
                duration = time.time() - start
                self.results.append(StageResult(name, True, duration))
                console.print(f"[green]✓ {name}[/] [dim]({duration:.1f}s)[/]")
                return result
            except KeyboardInterrupt:
                last_error = "interrupted by user"
                console.print(f"[yellow]⏸ {name} interrupted[/]")
                if self.fail_fast:
                    break
            except StageTimeout:
                last_error = f"timeout after {self.timeout_seconds}s"
                console.print(f"[red]⏱ {name} timed out[/]")
                if self.fail_fast:
                    break
            except Exception as e:  # noqa: BLE001
                last_error = f"{type(e).__name__}: {e}"
                console.print(f"[red]✗ {name}: {last_error}[/]")
                if console.is_terminal:
                    console.print_exception(show_locals=False)
                else:
                    traceback.print_exc()
                if self.fail_fast:
                    break
        duration = time.time() - start
        self.results.append(StageResult(name, False, duration, last_error))
        return None

    def summary(self) -> str:
        ok = sum(1 for r in self.results if r.ok)
        total = len(self.results)
        lines = [f"Pipeline summary: {ok}/{total} stages succeeded"]
        for r in self.results:
            mark = "✓" if r.ok else "✗"
            extra = "" if r.ok else f"  [{r.error}]"
            lines.append(f"  {mark} {r.name}  ({r.duration_s:.1f}s){extra}")
        return "\n".join(lines)


@contextmanager
def _timeout(seconds: int):
    """Best-effort SIGALRM timeout. Falls back to no-op on platforms without it."""
    if not hasattr(signal, "SIGALRM") or threading.current_thread() is not threading.main_thread():
        yield
        return

    def _handler(signum, frame):  # noqa: ARG001
        raise StageTimeout()

    try:
        old = signal.signal(signal.SIGALRM, _handler)
        signal.alarm(seconds)
        yield
    except ValueError:
        yield
    finally:
        try:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old)
        except Exception:  # noqa: BLE001
            pass
