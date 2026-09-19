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
            [(1, "1.4.2.0", None), (2, "2.0.0.7", None)],
        )

    def test_to_semver(self):
        results = list(convert_lines(["1.4.2.0", "1.4.2.42"], "to-semver"))
        self.assertEqual(
            results,
            [(1, "1.4.2", None), (2, "1.4.2+42", None)],
        )

    def test_blank_lines_are_skipped_and_do_not_consume_a_line_number(self):
        results = list(convert_lines(["1.4.2", "", "  \n", "1.4.3"], "to-win"))
        self.assertEqual(
            results,
            [(1, "1.4.2.0", None), (4, "1.4.3.0", None)],
        )

    def test_bad_line_reports_error_and_keeps_its_line_number(self):
        results = list(convert_lines(["1.4.2", "not-a-version", "1.4.3"], "to-win"))
        self.assertEqual(results[0], (1, "1.4.2.0", None))
        self.assertEqual(results[2], (3, "1.4.3.0", None))
        line_number, output, error = results[1]
        self.assertEqual(line_number, 2)
        self.assertIsNone(output)
        self.assertIn("not-a-version", error)


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
