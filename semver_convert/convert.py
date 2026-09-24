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

`--sidecar` makes a to-win/to-semver round trip lossless for prerelease
tags: to-win writes one prerelease per converted line (blank if there
wasn't one) to the sidecar path, and a later to-semver run against the
same sidecar reads them back in order and reattaches them. It only
covers the prerelease tag, since that's the only piece semver_to_winver
throws away outright; numeric build metadata already survives as the
revision field.
"""

from __future__ import annotations

import argparse
import gzip
import sys
from typing import Iterable, TextIO

from .core import VersionError, parse_semver, parse_winver, semver_to_winver, winver_to_semver


def convert_lines(
    lines: Iterable[str],
    direction: str,
    prereleases: Iterable[str] | None = None,
) -> Iterable[tuple[int, str | None, str | None, str | None]]:
    """Yield (line_number, output, error, sidecar) for each non-blank input line.

    Exactly one of output/error is set. Blank lines are skipped entirely
    and do not consume a line number in the output.

    `sidecar` carries the prerelease tag that a to-win conversion has to
    drop: it is the (possibly empty) prerelease string on "to-win" lines
    that converted successfully, and None otherwise.

    `prereleases`, if given, is consumed one item per successful "to-semver"
    line, in order, and folded into that line's output as its prerelease
    tag - this is how a sidecar file written by a prior to-win run restores
    what would otherwise be lost. Lines that fail to parse do not consume
    an item, keeping the two streams aligned the same way the sidecar was
    written (only successful lines produce a sidecar entry).
    """
    prerelease_iter = iter(prereleases) if prereleases is not None else None
    for line_number, raw in enumerate(lines, start=1):
        text = raw.strip()
        if not text:
            continue
        try:
            if direction == "to-win":
                parsed = parse_semver(text)
                output = str(semver_to_winver(parsed))
                yield line_number, output, None, parsed.prerelease or ""
            else:
                parsed = parse_winver(text)
                prerelease = next(prerelease_iter, None) if prerelease_iter is not None else None
                output = str(winver_to_semver(parsed, prerelease=prerelease or None))
                yield line_number, output, None, None
        except VersionError as exc:
            yield line_number, None, str(exc), None


def run(
    infile: TextIO,
    outfile: TextIO,
    errfile: TextIO,
    direction: str,
    strict: bool = False,
    sidecar: TextIO | None = None,
) -> int:
    had_errors = False
    prereleases = None
    if sidecar is not None and direction == "to-semver":
        prereleases = (line.rstrip("\n") for line in sidecar)
    for line_number, output, error, tag in convert_lines(infile, direction, prereleases=prereleases):
        if error is not None:
            had_errors = True
            print(f"line {line_number}: {error}", file=errfile)
            if strict:
                break
            continue
        outfile.write(output)
        outfile.write("\n")
        outfile.flush()
        if sidecar is not None and direction == "to-win":
            sidecar.write(tag)
            sidecar.write("\n")
            sidecar.flush()
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
    parser.add_argument(
        "--sidecar",
        help="path to a plain text file that preserves the prerelease tag a to-win "
             "conversion would otherwise drop: written one entry per converted line "
             "in to-win mode, read back to restore the tag in to-semver mode. Use "
             "the same sidecar path for both halves of a round trip",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    infile = _open_input(args.input)
    outfile = _open_output(args.output)
    sidecar = None
    if args.sidecar:
        mode = "w" if args.direction == "to-win" else "r"
        sidecar = open(args.sidecar, mode, encoding="utf-8")
    try:
        return run(infile, outfile, sys.stderr, args.direction, strict=args.strict, sidecar=sidecar)
    finally:
        if infile is not sys.stdin:
            infile.close()
        if outfile is not sys.stdout:
            outfile.close()
        if sidecar is not None:
            sidecar.close()


if __name__ == "__main__":
    raise SystemExit(main())
