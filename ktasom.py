#!/usr/bin/env python3
"""Baixa em MP3 um link do YouTube ou todos os links listados em um CSV."""
import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

REQUIRED_TOOLS = ("yt-dlp", "ffmpeg", "ffprobe")
YOUTUBE_LINK = re.compile(
    r"""(?<![\w./-])(?:https?://)?(?:[\w-]+\.)*(?:youtube\.com|youtu\.be)/[^\s,;"'<>]+""",
    re.IGNORECASE,
)
NO_CONSOLE_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def extract_links(csv_text):
    return list(dict.fromkeys(YOUTUBE_LINK.findall(csv_text)))


def download_command(link, output_dir):
    return [
        "yt-dlp", "--quiet", "--progress", "--no-playlist",
        "--extract-audio", "--audio-format", "mp3", "--audio-quality", "0",
        "--download-archive", str(output_dir / ".baixados.txt"),
        "--paths", str(output_dir),
        "--output", "%(title)s.%(ext)s",
        "--", link,
    ]


def download(link, output_dir):
    return subprocess.run(download_command(link, output_dir)).returncode == 0


def read_links(source):
    if YOUTUBE_LINK.fullmatch(source):
        return [source]
    return extract_links(Path(source).read_text(encoding="utf-8", errors="replace"))


def missing_tools():
    return [tool for tool in REQUIRED_TOOLS if not shutil.which(tool)]


class DownloadJob:
    """Baixa os links publicando o andamento, para quem não pode herdar o terminal."""

    def __init__(self, links, output_dir, publish):
        self.links = links
        self.output_dir = output_dir
        self.publish = publish
        self.process = None
        self.cancelled = False

    def run(self):
        failed = []
        for position, link in enumerate(self.links, 1):
            if self.cancelled:
                return
            self.publish("link", position, len(self.links), link)
            if not self.download(link) and not self.cancelled:
                failed.append(link)
        if not self.cancelled:
            self.publish("done", failed)

    def download(self, link):
        try:
            self.process = subprocess.Popen(
                download_command(link, self.output_dir),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                creationflags=NO_CONSOLE_WINDOW,
            )
        except OSError as error:
            self.publish("line", f"ERROR: {error}")
            return False
        with self.process as process:
            for line in process.stdout:
                if line.strip():
                    self.publish("line", line.strip())
        return process.returncode == 0

    def cancel(self):
        self.cancelled = True
        if self.process:
            self.process.terminate()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="link do YouTube ou arquivo CSV com os links")
    parser.add_argument("-o", "--output", type=Path, default=Path.cwd(), help="pasta de destino (padrão: diretório atual)")
    args = parser.parse_args()

    for tool in missing_tools():
        sys.exit(f"erro: {tool} não encontrado no PATH")

    try:
        links = read_links(args.source)
    except OSError as error:
        sys.exit(f"erro: não foi possível ler {args.source}: {error.strerror}")
    if not links:
        sys.exit(f"erro: nenhum link do YouTube encontrado em {args.source}")

    args.output.mkdir(parents=True, exist_ok=True)
    failed = []
    for position, link in enumerate(links, 1):
        print(f"[{position}/{len(links)}] {link}", flush=True)
        if not download(link, args.output):
            failed.append(link)

    print(f"{len(links) - len(failed)}/{len(links)} links processados, MP3s em {args.output}")
    if failed:
        sys.exit("falharam:\n" + "\n".join(failed))


if __name__ == "__main__":
    main()
