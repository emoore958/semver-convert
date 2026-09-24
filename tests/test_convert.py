import gzip
import io
import os
import tempfile
import unittest

from semver_convert.convert import _open_input, _open_output, convert_lines, run


class ConvertLinesTests(unittest.TestCase):
    def test_to_win(self):
        results = list(convert_lines(["1.4.2", "2.0.0-rc.1+7"], "to-win"))
        self.assertEqual(
            results,
            [(1, "1.4.2.0", None, ""), (2, "2.0.0.7", None, "rc.1")],
        )

    def test_to_semver(self):
        results = list(convert_lines(["1.4.2.0", "1.4.2.42"], "to-semver"))
        self.assertEqual(
            results,
            [(1, "1.4.2", None, None), (2, "1.4.2+42", None, None)],
        )

    def test_blank_lines_are_skipped_and_do_not_consume_a_line_number(self):
        results = list(convert_lines(["1.4.2", "", "  \n", "1.4.3"], "to-win"))
        self.assertEqual(
            results,
            [(1, "1.4.2.0", None, ""), (4, "1.4.3.0", None, "")],
        )

    def test_bad_line_reports_error_and_keeps_its_line_number(self):
        results = list(convert_lines(["1.4.2", "not-a-version", "1.4.3"], "to-win"))
        self.assertEqual(results[0], (1, "1.4.2.0", None, ""))
        self.assertEqual(results[2], (3, "1.4.3.0", None, ""))
        line_number, output, error, tag = results[1]
        self.assertEqual(line_number, 2)
        self.assertIsNone(output)
        self.assertIn("not-a-version", error)
        self.assertIsNone(tag)

    def test_to_semver_folds_in_supplied_prereleases_in_order(self):
        results = list(
            convert_lines(["1.4.2.0", "1.4.2.42"], "to-semver", prereleases=["rc.1", "beta"])
        )
        self.assertEqual(
            results,
            [(1, "1.4.2-rc.1", None, None), (2, "1.4.2-beta+42", None, None)],
        )

    def test_to_semver_prerelease_skips_failed_lines(self):
        results = list(
            convert_lines(["1.4.2.0", "bad", "1.4.2.42"], "to-semver", prereleases=["rc.1", "beta"])
        )
        self.assertEqual(results[0], (1, "1.4.2-rc.1", None, None))
        self.assertEqual(results[2], (3, "1.4.2-beta+42", None, None))


class RunTests(unittest.TestCase):
    def test_writes_converted_lines_and_returns_zero_on_success(self):
        infile = io.StringIO("1.4.2\n2.0.0-rc.1+7\n")
        outfile = io.StringIO()
        errfile = io.StringIO()

        status = run(infile, outfile, errfile, "to-win")

        self.assertEqual(status, 0)
        self.assertEqual(outfile.getvalue(), "1.4.2.0\n2.0.0.7\n")
        self.assertEqual(errfile.getvalue(), "")

    def test_skips_bad_lines_by_default_and_returns_nonzero(self):
        infile = io.StringIO("1.4.2\nbad\n1.4.3\n")
        outfile = io.StringIO()
        errfile = io.StringIO()

        status = run(infile, outfile, errfile, "to-win")

        self.assertEqual(status, 1)
        self.assertEqual(outfile.getvalue(), "1.4.2.0\n1.4.3.0\n")
        self.assertIn("line 2:", errfile.getvalue())

    def test_strict_stops_at_first_bad_line(self):
        infile = io.StringIO("1.4.2\nbad\n1.4.3\n")
        outfile = io.StringIO()
        errfile = io.StringIO()

        status = run(infile, outfile, errfile, "to-win", strict=True)

        self.assertEqual(status, 1)
        self.assertEqual(outfile.getvalue(), "1.4.2.0\n")
        self.assertIn("line 2:", errfile.getvalue())

    def test_strict_has_no_effect_when_input_is_valid(self):
        infile = io.StringIO("1.4.2\n1.4.3\n")
        outfile = io.StringIO()
        errfile = io.StringIO()

        status = run(infile, outfile, errfile, "to-win", strict=True)

        self.assertEqual(status, 0)
        self.assertEqual(outfile.getvalue(), "1.4.2.0\n1.4.3.0\n")

    def test_to_win_with_sidecar_writes_one_prerelease_per_line(self):
        infile = io.StringIO("1.4.2\n2.0.0-rc.1+7\n")
        outfile = io.StringIO()
        errfile = io.StringIO()
        sidecar = io.StringIO()

        status = run(infile, outfile, errfile, "to-win", sidecar=sidecar)

        self.assertEqual(status, 0)
        self.assertEqual(outfile.getvalue(), "1.4.2.0\n2.0.0.7\n")
        self.assertEqual(sidecar.getvalue(), "\nrc.1\n")

    def test_to_semver_with_sidecar_restores_prerelease(self):
        infile = io.StringIO("1.4.2.0\n2.0.0.7\n")
        outfile = io.StringIO()
        errfile = io.StringIO()
        sidecar = io.StringIO("\nrc.1\n")

        status = run(infile, outfile, errfile, "to-semver", sidecar=sidecar)

        self.assertEqual(status, 0)
        self.assertEqual(outfile.getvalue(), "1.4.2\n2.0.0-rc.1+7\n")

    def test_sidecar_round_trip_is_lossless_for_prerelease(self):
        original = ["1.4.2", "2.0.0-rc.1", "3.1.0-beta.2+9"]
        sidecar_out = io.StringIO()
        forward = run(
            io.StringIO("\n".join(original) + "\n"),
            (win_out := io.StringIO()),
            io.StringIO(),
            "to-win",
            sidecar=sidecar_out,
        )
        self.assertEqual(forward, 0)

        sidecar_in = io.StringIO(sidecar_out.getvalue())
        back = run(
            io.StringIO(win_out.getvalue()),
            (semver_out := io.StringIO()),
            io.StringIO(),
            "to-semver",
            sidecar=sidecar_in,
        )
        self.assertEqual(back, 0)
        self.assertEqual(semver_out.getvalue().splitlines(), original)


class GzipIOTests(unittest.TestCase):
    def test_gz_output_path_is_written_as_gzip(self):
        fd, path = tempfile.mkstemp(suffix=".gz")
        os.close(fd)
        try:
            outfile = _open_output(path)
            try:
                outfile.write("1.4.2.0\n2.0.0.7\n")
            finally:
                outfile.close()
            with gzip.open(path, "rt", encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "1.4.2.0\n2.0.0.7\n")
        finally:
            os.remove(path)

    def test_gz_input_path_is_read_as_gzip(self):
        fd, path = tempfile.mkstemp(suffix=".gz")
        os.close(fd)
        try:
            with gzip.open(path, "wt", encoding="utf-8") as fh:
                fh.write("1.4.2\n2.0.0-rc.1+7\n")
            infile = _open_input(path)
            try:
                self.assertEqual(list(infile), ["1.4.2\n", "2.0.0-rc.1+7\n"])
            finally:
                infile.close()
        finally:
            os.remove(path)

    def test_run_roundtrips_through_gzip_files(self):
        in_fd, in_path = tempfile.mkstemp(suffix=".gz")
        os.close(in_fd)
        out_fd, out_path = tempfile.mkstemp(suffix=".gz")
        os.close(out_fd)
        try:
            with gzip.open(in_path, "wt", encoding="utf-8") as fh:
                fh.write("1.4.2\n2.0.0-rc.1+7\n")

            infile = _open_input(in_path)
            outfile = _open_output(out_path)
            errfile = io.StringIO()
            try:
                status = run(infile, outfile, errfile, "to-win")
            finally:
                infile.close()
                outfile.close()

            self.assertEqual(status, 0)
            with gzip.open(out_path, "rt", encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "1.4.2.0\n2.0.0.7\n")
        finally:
            os.remove(in_path)
            os.remove(out_path)

    def test_non_gz_paths_are_opened_as_plain_text(self):
        fd, path = tempfile.mkstemp(suffix=".txt")
        os.close(fd)
        try:
            outfile = _open_output(path)
            try:
                outfile.write("1.4.2.0\n")
            finally:
                outfile.close()
            with open(path, "r", encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "1.4.2.0\n")
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
