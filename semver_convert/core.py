"""Parsing and conversion between SemVer 2.0.0 strings and 4-part numeric
"Windows style" versions (the MAJOR.MINOR.BUILD.REVISION shape expected by
things like FILEVERSION resources and .NET AssemblyVersion attributes).

The two formats are not equivalent. SemVer allows arbitrary alphanumeric
prerelease tags ("1.2.3-beta.1") and build metadata ("1.2.3+exp.sha.abc123"),
while the Windows format is four plain 16-bit unsigned integers. The
conversion here is deliberately one specific, documented mapping rather than
an attempt to preserve everything:

- major.minor.patch carry across unchanged.
- prerelease information has no numeric equivalent and is dropped when
  going to WinVersion.
- build metadata is kept only when it is a single run of digits (e.g.
  "+42"), which becomes the revision field. Anything else is dropped.
- going the other way, a non-zero revision is written back as build
  metadata ("+42"), never as a prerelease tag, since revision numbers are
  conventionally build counters rather than prerelease markers.

See README.md for the reasoning and worked examples.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Official grammar from semver.org (2.0.0 spec appendix).
_SEMVER_RE = re.compile(
    r"^(?P<major>0|[1-9]\d*)"
    r"\.(?P<minor>0|[1-9]\d*)"
    r"\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+(?P<build>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)

_WINVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:\.(\d+))?$")

_NUMERIC_BUILD_RE = re.compile(r"^\d+$")

_UINT16_MAX = 65535


class VersionError(ValueError):
    """Raised when a string does not match the expected version grammar."""


@dataclass(frozen=True)
class SemVer:
    major: int
    minor: int
    patch: int
    prerelease: str | None = None
    build: str | None = None

    def __str__(self) -> str:
        s = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            s += f"-{self.prerelease}"
        if self.build:
            s += f"+{self.build}"
        return s


@dataclass(frozen=True)
class WinVersion:
    major: int
    minor: int
    patch: int
    revision: int = 0

    def __post_init__(self) -> None:
        for name in ("major", "minor", "patch", "revision"):
            value = getattr(self, name)
            if not (0 <= value <= _UINT16_MAX):
                raise VersionError(
                    f"{name}={value} is out of range for a Windows version "
                    f"field (0-{_UINT16_MAX})"
                )

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}.{self.revision}"


def parse_semver(text: str) -> SemVer:
    match = _SEMVER_RE.match(text.strip())
    if not match:
        raise VersionError(f"{text!r} is not a valid SemVer 2.0.0 string")
    return SemVer(
        major=int(match["major"]),
        minor=int(match["minor"]),
        patch=int(match["patch"]),
        prerelease=match["prerelease"],
        build=match["build"],
    )


def parse_winver(text: str) -> WinVersion:
    match = _WINVER_RE.match(text.strip())
    if not match:
        raise VersionError(
            f"{text!r} is not a valid Windows version (MAJOR.MINOR.PATCH"
            f"[.REVISION], plain integers only)"
        )
    major, minor, patch, revision = match.groups()
    return WinVersion(
        major=int(major),
        minor=int(minor),
        patch=int(patch),
        revision=int(revision) if revision is not None else 0,
    )


def semver_to_winver(version: SemVer) -> WinVersion:
    revision = 0
    if version.build:
        # Build metadata is a dot-separated list of identifiers; only use
        # it as a revision if the whole field is a single numeric run.
        if _NUMERIC_BUILD_RE.match(version.build) and int(version.build) <= _UINT16_MAX:
            revision = int(version.build)
    return WinVersion(
        major=version.major,
        minor=version.minor,
        patch=version.patch,
        revision=revision,
    )


def winver_to_semver(version: WinVersion, prerelease: str | None = None) -> SemVer:
    """Convert a WinVersion back to SemVer.

    `prerelease` lets a caller restore the tag that `semver_to_winver` had to
    drop (there is no field in WinVersion to carry it), typically read back
    from a sidecar file written during the forward conversion. Left as None,
    the result never has a prerelease, same as before.
    """
    return SemVer(
        major=version.major,
        minor=version.minor,
        patch=version.patch,
        prerelease=prerelease,
        build=str(version.revision) if version.revision else None,
    )
