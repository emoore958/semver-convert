# semver-convert

Converts between [SemVer 2.0.0](https://semver.org) strings like
`1.4.2-rc.1+42` and the 4-part plain-integer version format that Windows
resource files and .NET assemblies expect, `MAJOR.MINOR.BUILD.REVISION`.

I needed this because a build pipeline tags releases with normal semver
(`2.3.0-beta.1`) but the Windows installer step wants a `FILEVERSION` made
of four 16-bit integers, and there's no standard tool for going between
the two.

## The format mismatch

SemVer allows things a Windows version field cannot represent:

- prerelease tags (`-alpha`, `-rc.1`) - arbitrary text, no numeric
  equivalent
- build metadata (`+exp.sha.5114f85`) - arbitrary text, ignored for
  precedence by the spec anyway
- unbounded integers - Windows fields are `0-65535` each

So this tool picks one specific, documented mapping rather than pretending
the conversion is lossless:

- `major.minor.patch` carry across unchanged
- prerelease tags are dropped going to Windows format - there is nowhere
  to put them
- build metadata is kept only when it's a single run of digits
  (`+42` -> revision `42`); anything else is dropped
- going back, a non-zero revision becomes build metadata (`+42`), never a
  prerelease tag, since a revision number is conventionally a build
  counter rather than a prerelease marker

```
1.4.2            -> 1.4.2.0
1.4.2+42         -> 1.4.2.42
1.4.2-rc.1       -> 1.4.2.0      (prerelease dropped)
1.4.2-rc.1+42    -> 1.4.2.42     (prerelease dropped, build kept)
1.4.2+exp.sha.ab -> 1.4.2.0      (non-numeric build dropped)

1.4.2.0  -> 1.4.2
1.4.2.42 -> 1.4.2+42
```

## Usage

As a library:

```python
from semver_convert import parse_semver, semver_to_winver

v = parse_semver("2.3.0-beta.1+42")
print(semver_to_winver(v))  # 2.3.0.42
```

As a command line tool, one version per line, either direction:

```
$ printf '1.4.2\n2.0.0-rc.1+7\nnot-a-version\n' | python -m semver_convert to-win
1.4.2.0
2.0.0.7
line 3: 'not-a-version' is not a valid SemVer 2.0.0 string
```

Malformed lines are reported on stderr with their line number and
skipped; the exit code is non-zero if anything was skipped, but the
rest of the stream is still converted. Use `-i`/`-o` to read or write a
file instead of stdin/stdout.

## Streaming

The CLI reads its input one line at a time and writes each converted
line immediately, so a version list larger than available memory works
fine - nothing does `.read()` or `.readlines()` on the whole input.

## Status

Early skeleton. Parsing and both conversion directions work and are
covered by unit tests in `tests/`; no packaging on PyPI yet.

Run the tests with:

```
python -m unittest discover -s tests
```

## License

MIT, see LICENSE.
