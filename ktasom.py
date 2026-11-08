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


def extract_links(csv_text):
    return list(dict.fromkeys(YOUTUBE_LINK.findall(csv_text)))


def download(link, output_dir):
    command = [
        "yt-dlp", "--quiet", "--progress", "--no-playlist",
        "--extract-audio", "--audio-format", "mp3", "--audio-quality", "0",
        "--download-archive", str(output_dir / ".baixados.txt"),
        "--paths", str(output_dir),
        "--output", "%(title)s.%(ext)s",
        "--", link,
    ]
    return subprocess.run(command).returncode == 0


def read_links(source):
    if YOUTUBE_LINK.fullmatch(source):
        return [source]
    try:
        return extract_links(Path(source).read_text(encoding="utf-8", errors="replace"))
    except OSError as error:
        sys.exit(f"erro: não foi possível ler {source}: {error.strerror}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="link do YouTube ou arquivo CSV com os links")
    parser.add_argument("-o", "--output", type=Path, default=Path.cwd(), help="pasta de destino (padrão: diretório atual)")
    args = parser.parse_args()

    for tool in REQUIRED_TOOLS:
        if not shutil.which(tool):
            sys.exit(f"erro: {tool} não encontrado no PATH")

    links = read_links(args.source)
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
