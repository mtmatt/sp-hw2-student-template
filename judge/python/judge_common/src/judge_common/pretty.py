"""Terminal-aware stderr rendering for logger/alarm.

Uses a `rich.console.Console` so wrapping and coloring adapt to the real
terminal size (re-read on every print, so a resize mid-run takes effect
immediately) and degrade automatically when stderr isn't a terminal.

Message content comes from the student program and must never be passed to
`Console.print` as a plain (markup-enabled) string -- a log line containing
literal `[...]` text would otherwise be parsed as rich markup, which can
raise `MarkupError` on mismatched brackets and crash the logger over
untrusted input. Wrapping it in `rich.text.Text` first sidesteps markup
parsing entirely, regardless of content.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import sys

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

EVENTS_ENV = "JUDGE_PRESENTATION_EVENTS"
EVENTS_FORMAT = "jsonl-v1"


def make_console() -> Console:
    return Console(file=sys.stderr, highlight=False)


def presentation_events_enabled() -> bool:
    """Return whether the judge requested the version-one JSONL stream."""
    return os.environ.get(EVENTS_ENV) == EVENTS_FORMAT


def emit_presentation_event(event: str, source: str, text: str, *, ok: bool | None = None) -> bool:
    """Emit one safe, machine-readable stderr event when requested.

    The message text is student-controlled. JSON encoding keeps newlines,
    terminal escapes, and quotes inside one framed JSON Lines record instead
    of letting them change the terminal or the transport framing.
    """
    if not presentation_events_enabled():
        return False

    payload: dict[str, object] = {
        "version": 1,
        "event": event,
        "source": source,
        "text": text,
    }
    if ok is not None:
        payload["ok"] = ok
    print(
        json.dumps(payload, ensure_ascii=True, separators=(",", ":")), file=sys.stderr, flush=True
    )
    return True


def _timestamp() -> str:
    return _dt.datetime.now().strftime("%H:%M:%S")


def render_log(console: Console, text: str) -> None:
    if emit_presentation_event("message", "logger", text, ok=True):
        return
    line = Text()
    line.append(_timestamp(), style="dim")
    line.append(" LOG ", style="bold cyan")
    line.append(text)
    console.print(line)


def render_alarm(console: Console, text: str) -> None:
    if emit_presentation_event("message", "alarm", text, ok=True):
        return
    console.print(
        Panel(
            Text(text),
            title=f"ALARM  {_timestamp()}",
            border_style="bold red",
            title_align="left",
        )
    )


def render_error(console: Console, reason: str, kind: str) -> None:
    """Render a failed message's reason to stderr.

    Called by logger/alarm's main loop whenever `protocol.process_line`
    returns a failed `Processed` -- a malformed line, an invalid `<encrypt>`
    flag, undecodable hex, a ciphertext that fails to decrypt, or plaintext
    that isn't valid UTF-8. `kind` is `"log"` or `"alarm"`, just to label
    which program's stderr this came from.
    """
    source = "logger" if kind == "log" else "alarm"
    if emit_presentation_event("message", source, reason, ok=False):
        return
    line = Text()
    line.append(_timestamp(), style="dim")
    line.append(f" {kind.upper()} ERROR ", style="bold yellow")
    line.append(reason, style="yellow")
    console.print(line)


def render_service_error(source: str, reason: str) -> None:
    """Render startup failure without losing it to a judge-owned terminal."""
    if emit_presentation_event("service_error", source, reason):
        return
    print(f"{source}: {reason}", file=sys.stderr)
