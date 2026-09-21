"""The logger/alarm wire protocol and FIFO plumbing.

Wire protocol, one message per line on the FIFO:

    <encrypt> <data>\n

`<encrypt>` is literally `true` or `false`. `<data>` is the rest of the
line verbatim -- only the trailing `\n` is stripped (no `\r` stripping,
spaces allowed), matching encryptor.c's input-parsing convention. A line
that's blank after the `\n` strip is skipped silently, also matching
encryptor.c.

FIFO setup mirrors access-token-generator's RequestHandler: create the FIFO
ourselves and open it read+write so we never see EOF and never busy-loop
waiting for a writer to attach.
"""

from __future__ import annotations

import atexit
import contextlib
import os
import signal
import sys
import time
from collections.abc import Iterator
from dataclasses import dataclass
from typing import TextIO

from .decrypt import DecryptError, ServerKeys, decrypt_hex


class ProtocolError(Exception):
    """Raised when a line doesn't parse as `<encrypt> <data>`."""


@dataclass(frozen=True)
class Message:
    encrypt: bool
    data: str


@dataclass(frozen=True)
class Processed:
    """The result of handling one non-blank line."""

    stdout_line: str  # "Ok: <encrypt> <text>" or "Err: <reason>"
    ok: bool
    text: str  # decrypted/plain message on success, failure reason otherwise


def parse_message(line: str) -> Message:
    space_idx = line.find(" ")
    if space_idx <= 0:
        raise ProtocolError("malformed message: expected <encrypt> <data>")

    flag, data = line[:space_idx], line[space_idx + 1 :]
    if flag == "true":
        encrypt = True
    elif flag == "false":
        encrypt = False
    else:
        raise ProtocolError(f"invalid encrypt flag {flag!r}, expected true/false")

    return Message(encrypt=encrypt, data=data)


def process_line(line: str, server_keys: ServerKeys) -> Processed:
    try:
        msg = parse_message(line)
    except ProtocolError as e:
        return Processed(stdout_line=f"Err: {e}", ok=False, text=str(e))

    if not msg.encrypt:
        return Processed(stdout_line=f"Ok: false {msg.data}", ok=True, text=msg.data)

    try:
        plaintext = decrypt_hex(server_keys, msg.data)
    except DecryptError as e:
        return Processed(stdout_line=f"Err: {e}", ok=False, text=str(e))

    try:
        text = plaintext.decode("utf-8")
    except UnicodeDecodeError:
        reason = "decrypted payload is not valid UTF-8"
        return Processed(stdout_line=f"Err: {reason}", ok=False, text=reason)

    return Processed(stdout_line=f"Ok: true {text}", ok=True, text=text)


def setup_fifo(path: str) -> TextIO:
    """Create `path` as a FIFO and open it read+write.

    Opening read+write (rather than write-only, or a plain read-only open
    that would see EOF once no writer is attached) means this process
    itself always holds a reader and a writer, so readline() blocks for
    the next message instead of returning EOF the moment a writer
    disconnects -- same rationale as access-token-generator's FIFO setup.
    """
    with contextlib.suppress(FileNotFoundError):
        os.remove(path)
    os.mkfifo(path, mode=0o644)
    fd = os.open(path, os.O_RDWR)
    # newline="\n": only "\n" ends a line, and it's left untranslated (no
    # universal-newlines mode), so a stray "\r" in the data stays put --
    # matching encryptor.c's read_line, which only strips a trailing "\n".
    return os.fdopen(fd, "r", newline="\n")


def cleanup_fifo(path: str) -> None:
    with contextlib.suppress(FileNotFoundError):
        os.remove(path)


def install_fifo_cleanup(path: str) -> None:
    """Remove the FIFO on normal exit or SIGINT/SIGTERM."""
    atexit.register(cleanup_fifo, path)

    def _handler(signum: int, frame: object) -> None:
        sys.exit(0)

    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)


def read_lines(fifo: TextIO) -> Iterator[str]:
    """Yield successive lines from `fifo`, with the trailing "\n" stripped.

    Since the caller holds its own write end open (see setup_fifo), a
    readline() returning "" shouldn't happen -- but if it ever does, avoid
    spinning, same as access-token-generator's read loop.
    """
    while True:
        line = fifo.readline()
        if line == "":
            time.sleep(0.02)
            continue
        if line.endswith("\n"):
            line = line[:-1]
        yield line
