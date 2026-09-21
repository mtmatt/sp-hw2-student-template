"""Read alarm messages from a FIFO, decrypt as needed, report on stdout/stderr.

Identical to logger/logger.py except for the stderr styling (an alarm
should stand out in a scrolling terminal, a routine log line shouldn't) --
see judge_common/README.md for the shared `<encrypt> <data>` wire protocol
and `Ok: <encrypt> <text>`/`Err:` stdout contract.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from judge_common.decrypt import ServerKeys
from judge_common.pretty import make_console, render_alarm, render_error, render_service_error
from judge_common.protocol import install_fifo_cleanup, process_line, read_lines, setup_fifo

DEFAULT_FIFO = "./alarm.fifo"
DEFAULT_KEYS_DIR = "./keys"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="alarm",
        description="Read alarm messages from a FIFO, decrypt as needed, report on stdout/stderr.",
    )
    parser.add_argument(
        "--fifo",
        default=DEFAULT_FIFO,
        help=f"path to create the alarm FIFO at (default: {DEFAULT_FIFO})",
    )
    parser.add_argument(
        "--keys-dir",
        default=DEFAULT_KEYS_DIR,
        help=(
            "directory containing server_public_key.hex and "
            f"server_secret_key.hex (default: {DEFAULT_KEYS_DIR})"
        ),
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        server_keys = ServerKeys.load(args.keys_dir)
    except (OSError, ValueError) as e:
        render_service_error("alarm", f"failed to load server keys from {args.keys_dir}: {e}")
        return 1

    # Register cleanup before creating the FIFO (not after) so a signal
    # arriving in between can't leak the file.
    install_fifo_cleanup(args.fifo)
    fifo = setup_fifo(args.fifo)
    console = make_console()

    for line in read_lines(fifo):
        if line == "":
            continue
        result = process_line(line, server_keys)
        print(result.stdout_line, flush=True)
        if result.ok:
            render_alarm(console, result.text)
        else:
            render_error(console, result.text, kind="alarm")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
