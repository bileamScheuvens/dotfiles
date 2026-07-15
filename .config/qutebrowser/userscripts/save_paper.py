#!/usr/bin/env nix-shell
#!nix-shell -i python3 save_paper.nix

# -*- coding: utf-8 -*-

# Copyright: 2026 bileam <benedictbileam@gmx.de>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Userscript to download papers to specific folder."""

from random import randint

from os import environ
import os
from pathlib import Path
from time import sleep

import subprocess
import shlex
import sys
from pdf2bib import pdf2bib
import requests
import json
from urllib.parse import parse_qs, urlparse

ROOT = Path.home() / "papers"
CFG_FILE = Path(__file__).parent / ".save_paper_cfg.json"


def read_cfg():
    with open(CFG_FILE) as f:
        return json.loads(f.read())


def write_cfg(cfg):
    with open(CFG_FILE, "w") as f:
        return f.write(json.dumps(cfg))


def get_folder():
    folders = [p.name for p in os.scandir(ROOT) if not p.is_file()]
    selection = (
        subprocess.run(
            shlex.split("fuzzel --dmenu -i"),
            input="\n".join(folders).encode(),
            stdout=subprocess.PIPE,
        )
        .stdout.decode()
        .strip()
    )
    if not selection:
        selection = "unsorted"
    return selection


def set_download_dir():
    cfg = read_cfg()
    folder = get_folder()
    cfg["PAPER_DOWNLOAD_DIR"] = folder
    write_cfg(cfg)


fifo = open(environ["QUTE_FIFO"], "w")

# Qute stuff


def notify(message):
    print('message-info "{}"'.format(message), file=fifo)


def notify_error(message):
    print('message-error "{}"'.format(message), file=fifo)


def main():
    if environ["QUTE_MODE"] == "hints":
        url = environ["QUTE_URL"]
    else:
        # extract pdf source from pdfjs url
        url = parse_qs(urlparse(environ["QUTE_URL"]).query)["source"][0]

    response = requests.get(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
        },
    )
    response.raise_for_status()

    if "set_dir" in sys.argv:
        set_download_dir()
    cfg = read_cfg()
    DOWNLOAD_DIR = ROOT / cfg["PAPER_DOWNLOAD_DIR"]

    tmppath = DOWNLOAD_DIR / "tmp.pdf"
    with open(tmppath, "wb") as f:
        f.write(response.content)
    # short timeout to ensure file is closed
    sleep(0.1)

    pdf_info = pdf2bib(tmppath)
    bibtex = pdf_info["bibtex"]
    # extract id from string:
    # @article{authorYEARtitle, ...}
    # ^^^^^^^^^^^^^^^
    if bibtex is None:
        notify("Skipping, doi extraction failed")
        os.rename(tmppath, ROOT / f"unknown_{randint(1000, 9999)}.pdf")
        return
    bibtex_id = bibtex.split("{")[1].split(",")[0]
    outpath = DOWNLOAD_DIR / f"{bibtex_id}.pdf"
    if outpath.is_file():
        notify(f"Skipping, {bibtex_id} entry already exists")
        os.remove(tmppath)
        return

    os.rename(tmppath, outpath)
    # add to all bib
    with (DOWNLOAD_DIR / "citation.bib").open("a") as f:
        f.write("\n")
        f.write(bibtex)
        f.write("\n")
    notify(f"Added entry {bibtex_id} to {DOWNLOAD_DIR}")


if __name__ == "__main__":
    main()
