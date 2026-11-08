import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from ktasom import DownloadJob, extract_links

SCRIPT = Path(__file__).with_name("ktasom.py")
FAKE_YT_DLP = """#!/bin/sh
echo "$@" >> "$FAKE_LOG"
case "$*" in *broken*) exit 1 ;; esac
"""


class ExtractLinksTest(unittest.TestCase):
    def test_reads_links_from_any_column_with_header(self):
        csv_text = "musica,link\nEvidencias,https://www.youtube.com/watch?v=abc\n"
        self.assertEqual(["https://www.youtube.com/watch?v=abc"], extract_links(csv_text))

    def test_reads_semicolon_separated_files(self):
        csv_text = "https://youtu.be/abc;Evidencias\nTemporal;https://youtu.be/def\n"
        self.assertEqual(["https://youtu.be/abc", "https://youtu.be/def"], extract_links(csv_text))

    def test_reads_quoted_links(self):
        self.assertEqual(["https://youtu.be/abc"], extract_links('"https://youtu.be/abc","x"\n'))

    def test_keeps_query_string(self):
        link = "https://www.youtube.com/watch?v=abc&list=xyz&t=10"
        self.assertEqual([link], extract_links(f"{link}\n"))

    def test_accepts_links_without_scheme(self):
        self.assertEqual(["youtube.com/watch?v=abc"], extract_links("youtube.com/watch?v=abc\n"))

    def test_removes_duplicates_keeping_order(self):
        csv_text = "https://youtu.be/b\nhttps://youtu.be/a\nhttps://youtu.be/b\n"
        self.assertEqual(["https://youtu.be/b", "https://youtu.be/a"], extract_links(csv_text))

    def test_ignores_other_sites(self):
        self.assertEqual([], extract_links("https://vimeo.com/123,https://notyoutube.com/x\n"))


class FakeToolsTestCase(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.root = Path(temp_dir.name)
        self.log = self.root / "calls.log"
        self.csv = self.root / "links.csv"
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.install_fake("yt-dlp", FAKE_YT_DLP)
        self.install_fake("ffmpeg", "#!/bin/sh\n")
        self.install_fake("ffprobe", "#!/bin/sh\n")

    def install_fake(self, name, body):
        fake = self.bin / name
        fake.write_text(body)
        fake.chmod(0o755)


class DownloadJobTest(FakeToolsTestCase):
    def setUp(self):
        super().setUp()
        self.events = []
        patched_env = mock.patch.dict(os.environ, {"PATH": f"{self.bin}:/usr/bin:/bin", "FAKE_LOG": str(self.log)})
        patched_env.start()
        self.addCleanup(patched_env.stop)

    def run_job(self, *links):
        job = DownloadJob(links, self.root, lambda *event: self.events.append(event))
        job.run()
        return job

    def test_publishes_each_progress_update_as_a_line(self):
        self.install_fake("yt-dlp", "#!/bin/sh\nprintf '[download]  50%%\\r[download] 100%%\\n'\n")

        self.run_job("https://youtu.be/abc")

        self.assertEqual(
            [
                ("link", 1, 1, "https://youtu.be/abc"),
                ("line", "[download]  50%"),
                ("line", "[download] 100%"),
                ("done", []),
            ],
            self.events,
        )

    def test_failed_link_does_not_stop_the_rest_and_is_reported(self):
        self.run_job("https://youtu.be/broken", "https://youtu.be/ok")

        self.assertEqual(2, len(self.log.read_text().splitlines()))
        self.assertEqual(("done", ["https://youtu.be/broken"]), self.events[-1])

    def test_reports_link_as_failed_when_yt_dlp_cannot_start(self):
        (self.bin / "yt-dlp").unlink()

        with mock.patch.dict(os.environ, {"PATH": str(self.bin)}):
            self.run_job("https://youtu.be/abc")

        self.assertEqual(("done", ["https://youtu.be/abc"]), self.events[-1])

    def test_cancel_stops_current_download_and_skips_remaining_links(self):
        self.install_fake("yt-dlp", '#!/bin/sh\necho "$@" >> "$FAKE_LOG"\necho started\nexec sleep 30\n')
        job = DownloadJob(["https://youtu.be/a", "https://youtu.be/b"], self.root, self.cancel_on_first_line)
        self.job = job

        started = time.monotonic()
        job.run()

        self.assertLess(time.monotonic() - started, 10)
        self.assertEqual(1, len(self.log.read_text().splitlines()))
        self.assertNotIn("done", [event[0] for event in self.events])

    def cancel_on_first_line(self, *event):
        self.events.append(event)
        if event[0] == "line":
            self.job.cancel()


class CliTest(FakeToolsTestCase):
    def run_cli(self, *args):
        env = {**os.environ, "PATH": f"{self.bin}:/usr/bin:/bin", "FAKE_LOG": str(self.log)}
        command = [sys.executable, str(SCRIPT), str(self.csv), *args]
        return subprocess.run(command, env=env, capture_output=True, text=True)

    def calls(self):
        return self.log.read_text().splitlines()

    def test_downloads_single_link_passed_instead_of_csv(self):
        env = {**os.environ, "PATH": f"{self.bin}:/usr/bin:/bin", "FAKE_LOG": str(self.log)}
        link = "https://www.youtube.com/watch?v=abc&t=10"
        command = [sys.executable, str(SCRIPT), link, "--output", str(self.root / "musicas")]

        result = subprocess.run(command, env=env, capture_output=True, text=True)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(1, len(self.calls()))
        self.assertTrue(self.calls()[0].endswith(f"-- {link}"))

    def test_requests_mp3_into_output_dir(self):
        self.csv.write_text("https://youtu.be/abc\n")
        output = self.root / "musicas"

        result = self.run_cli("--output", str(output))

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(output.is_dir())
        call = self.calls()[0]
        self.assertIn("--audio-format mp3", call)
        self.assertIn(f"--paths {output}", call)
        self.assertTrue(call.endswith("-- https://youtu.be/abc"))

    def test_downloads_into_current_directory_when_called_through_symlink(self):
        self.csv.write_text("https://youtu.be/abc\n")
        command = self.bin / "ktasom"
        command.symlink_to(SCRIPT)
        work_dir = self.root / "qualquer-pasta"
        work_dir.mkdir()
        env = {**os.environ, "PATH": f"{self.bin}:/usr/bin:/bin", "FAKE_LOG": str(self.log)}

        result = subprocess.run(
            ["ktasom", str(self.csv)], cwd=work_dir, env=env, capture_output=True, text=True,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn(f"--paths {work_dir.resolve()} ", self.calls()[0])
        self.assertIn(str(work_dir.resolve()), result.stdout)

    def test_failed_link_does_not_stop_the_rest_and_is_reported(self):
        self.csv.write_text("https://youtu.be/broken\nhttps://youtu.be/ok\n")

        result = self.run_cli("--output", str(self.root / "musicas"))

        self.assertEqual(2, len(self.calls()))
        self.assertEqual(1, result.returncode)
        self.assertIn("https://youtu.be/broken", result.stderr)
        self.assertNotIn("https://youtu.be/ok", result.stderr)

    def test_fails_when_csv_has_no_links(self):
        self.csv.write_text("musica,artista\n")

        result = self.run_cli()

        self.assertEqual(1, result.returncode)
        self.assertIn("nenhum link", result.stderr)
        self.assertFalse(self.log.exists())

    def test_fails_when_csv_is_missing(self):
        result = self.run_cli()

        self.assertEqual(1, result.returncode)
        self.assertIn(str(self.csv), result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_fails_when_dependency_is_missing(self):
        self.csv.write_text("https://youtu.be/abc\n")
        env = {**os.environ, "PATH": str(self.bin), "FAKE_LOG": str(self.log)}

        for tool in ("yt-dlp", "ffmpeg", "ffprobe"):
            with self.subTest(tool=tool):
                body = (self.bin / tool).read_text()
                (self.bin / tool).unlink()

                result = subprocess.run(
                    [sys.executable, str(SCRIPT), str(self.csv), "--output", str(self.root / "musicas")],
                    env=env, capture_output=True, text=True,
                )

                self.install_fake(tool, body)
                self.assertEqual(1, result.returncode)
                self.assertIn(f"{tool} não encontrado", result.stderr)


if __name__ == "__main__":
    unittest.main()
