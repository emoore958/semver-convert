import unittest

from semver_convert.core import (
    SemVer,
    VersionError,
    WinVersion,
    parse_semver,
    parse_winver,
    semver_to_winver,
    winver_to_semver,
)


class ParseSemVerTests(unittest.TestCase):
    def test_plain(self):
        v = parse_semver("1.4.2")
        self.assertEqual(v, SemVer(1, 4, 2))

    def test_prerelease(self):
        v = parse_semver("2.0.0-rc.1")
        self.assertEqual(v, SemVer(2, 0, 0, prerelease="rc.1"))

    def test_build(self):
        v = parse_semver("1.4.2+42")
        self.assertEqual(v, SemVer(1, 4, 2, build="42"))

    def test_prerelease_and_build(self):
        v = parse_semver("2.0.0-rc.1+42")
        self.assertEqual(v, SemVer(2, 0, 0, prerelease="rc.1", build="42"))

    def test_strips_surrounding_whitespace(self):
        v = parse_semver("  1.4.2  \n")
        self.assertEqual(v, SemVer(1, 4, 2))

    def test_rejects_leading_zero(self):
        with self.assertRaises(VersionError):
            parse_semver("01.4.2")

    def test_rejects_missing_patch(self):
        with self.assertRaises(VersionError):
            parse_semver("1.4")

    def test_rejects_non_numeric_core(self):
        with self.assertRaises(VersionError):
            parse_semver("v1.4.2")

    def test_rejects_empty_prerelease(self):
        with self.assertRaises(VersionError):
            parse_semver("1.4.2-")

    def test_str_round_trip(self):
        for text in ("1.4.2", "2.0.0-rc.1", "1.4.2+42", "2.0.0-rc.1+42"):
            self.assertEqual(str(parse_semver(text)), text)


class ParseWinVerTests(unittest.TestCase):
    def test_four_parts(self):
        v = parse_winver("1.4.2.42")
        self.assertEqual(v, WinVersion(1, 4, 2, 42))

    def test_three_parts_defaults_revision_to_zero(self):
        v = parse_winver("1.4.2")
        self.assertEqual(v, WinVersion(1, 4, 2, 0))

    def test_strips_surrounding_whitespace(self):
        v = parse_winver("  1.4.2.42  \n")
        self.assertEqual(v, WinVersion(1, 4, 2, 42))

    def test_rejects_negative(self):
        with self.assertRaises(VersionError):
            parse_winver("1.4.-2.0")

    def test_rejects_non_numeric(self):
        with self.assertRaises(VersionError):
            parse_winver("1.4.2-rc")

    def test_rejects_too_few_parts(self):
        with self.assertRaises(VersionError):
            parse_winver("1.4")

    def test_rejects_too_many_parts(self):
        with self.assertRaises(VersionError):
            parse_winver("1.4.2.42.7")

    def test_field_out_of_uint16_range_rejected(self):
        with self.assertRaises(VersionError):
            parse_winver("1.4.2.65536")

    def test_str_round_trip(self):
        self.assertEqual(str(parse_winver("1.4.2.42")), "1.4.2.42")


class SemVerToWinVerTests(unittest.TestCase):
    def test_plain_version_gets_zero_revision(self):
        self.assertEqual(semver_to_winver(parse_semver("1.4.2")), WinVersion(1, 4, 2, 0))

    def test_numeric_build_becomes_revision(self):
        self.assertEqual(semver_to_winver(parse_semver("1.4.2+42")), WinVersion(1, 4, 2, 42))

    def test_prerelease_is_dropped(self):
        self.assertEqual(semver_to_winver(parse_semver("1.4.2-rc.1")), WinVersion(1, 4, 2, 0))

    def test_prerelease_dropped_but_numeric_build_kept(self):
        self.assertEqual(semver_to_winver(parse_semver("1.4.2-rc.1+42")), WinVersion(1, 4, 2, 42))

    def test_non_numeric_build_is_dropped(self):
        self.assertEqual(semver_to_winver(parse_semver("1.4.2+exp.sha.ab")), WinVersion(1, 4, 2, 0))

    def test_multi_segment_numeric_build_is_dropped(self):
        # "1.42" is digits-and-dots but not a single numeric run.
        self.assertEqual(semver_to_winver(parse_semver("1.4.2+1.42")), WinVersion(1, 4, 2, 0))

    def test_build_over_uint16_max_is_dropped(self):
        self.assertEqual(semver_to_winver(parse_semver("1.4.2+70000")), WinVersion(1, 4, 2, 0))


class WinVerToSemVerTests(unittest.TestCase):
    def test_zero_revision_has_no_build(self):
        self.assertEqual(winver_to_semver(parse_winver("1.4.2.0")), SemVer(1, 4, 2))

    def test_nonzero_revision_becomes_build(self):
        self.assertEqual(winver_to_semver(parse_winver("1.4.2.42")), SemVer(1, 4, 2, build="42"))

    def test_never_produces_prerelease(self):
        self.assertIsNone(winver_to_semver(parse_winver("1.4.2.42")).prerelease)

    def test_prerelease_argument_is_restored_into_the_result(self):
        v = winver_to_semver(parse_winver("1.4.2.42"), prerelease="rc.1")
        self.assertEqual(v, SemVer(1, 4, 2, prerelease="rc.1", build="42"))

    def test_prerelease_argument_defaults_to_none(self):
        v = winver_to_semver(parse_winver("1.4.2.0"))
        self.assertIsNone(v.prerelease)


if __name__ == "__main__":
    unittest.main()
