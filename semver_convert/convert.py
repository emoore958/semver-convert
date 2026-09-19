"""Command-line front end: converts a stream of version strings, one per
line, from SemVer to WinVersion or back.

Lines are read and written one at a time. Iterating a text file object
(`for line in fh`) pulls a line at a time off the OS read buffer rather
than materializing the whole file, so this comfortably handles a
version list far larger than available memory as long as no single line
is absurd - the same guarantee does not hold for `fh.readlines()` or
`fh.read()`, which is exactly what this avoids.

`-i`/`-o` paths ending in `.gz` are transparently read/written as gzip
(`gzip.open(..., "rt"/"wt")` streams the same way a plain text file
handle does, so the memory guarantee above still holds).
"""

from __future__ import annotations

import argparse
import gzip
import sys
from typing import Iterable, TextIO

from .core import VersionError, parse_semver, parse_winver, semver_to_winver, winver_to_semver


def convert_lines(lines: Iterable[str], direction: str) -> Iterable[tuple[int, str | None, str | None]]:
    """Yield (line_number, output, error) for each non-blank input line.

    Exactly one of output/error is set. Blank lines are skipped entirely
    and do not consume a line number in the output.
    """
    for line_number, raw in enumerate(lines, start=1):
        text = raw.strip()
        if not text:
            continue
        try:
            if direction == "to-win":
                yield line_number, str(semver_to_winver(parse_semver(text))), None
            else:
                yield line_number, str(winver_to_semver(parse_winver(text))), None
        except VersionError as exc:
            yield line_number, None, str(exc)


def run(infile: TextIO, outfile: TextIO, errfile: TextIO, direction: str, strict: bool = False) -> int:
    had_errors = False
    for line_number, output, error in convert_lines(infile, direction):
        if error is not None:
            had_errors = True
            print(f"line {line_number}: {error}", file=errfile)
            if strict:
                break
            continue
        outfile.write(output)
        outfile.write("\n")
        outfile.flush()
    return 1 if had_errors else 0


def _open_input(path: str) -> TextIO:
    if path == "-":
        return sys.stdin
    if path.endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8")
    return open(path, "r", encoding="utf-8")


def _open_output(path: str) -> TextIO:
    if path == "-":
        return sys.stdout
    if path.endswith(".gz"):
        return gzip.open(path, "wt", encoding="utf-8")
    return open(path, "w", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="semver-convert",
        description="Convert versions between SemVer 2.0.0 and 4-part Windows-style numeric versions, one per line.",
    )
    parser.add_argument(
        "direction",
        choices=("to-win", "to-semver"),
        help="to-win: SemVer -> MAJOR.MINOR.PATCH.REVISION; to-semver: the reverse",
    )
    parser.add_argument(
        "-i", "--input",
        default="-",
        help="input file, one version per line (default: stdin); "
             "a .gz path is read as gzip",
    )
    parser.add_argument(
        "-o", "--output",
        default="-",
        help="output file (default: stdout); a .gz path is written as gzip",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="stop at the first invalid line instead of skipping it and continuing",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    infile = _open_input(args.input)
    outfile = _open_output(args.output)
    try:
        return run(infile, outfile, sys.stderr, args.direction, strict=args.strict)
    finally:
        if infile is not sys.stdin:
            infile.close()
        if outfile is not sys.stdout:
            outfile.close()


if __name__ == "__main__":
    raise SystemExit(main())
