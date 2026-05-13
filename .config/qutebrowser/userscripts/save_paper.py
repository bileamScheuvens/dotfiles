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

from os import environ
import os
from time import sleep

import subprocess
import shlex
import sys
from pdf2bib import pdf2bib
import requests
from urllib.parse import parse_qs, urlparse

ROOT = os.path.join(os.path.expanduser("~"), "papers")


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


def get_download_dir(set_dir=False):
    if set_dir:
        environ["PAPER_DOWNLOAD_DIR"] = get_folder()
    if "PAPER_DOWNLOAD_DIR" in environ:
        folder = environ["PAPER_DOWNLOAD_DIR"]
    else:
        folder = "unsorted"
    return os.path.join(ROOT, folder)


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
    set_dir = "set_dir" in sys.argv
    DOWNLOAD_DIR = get_download_dir(set_dir)

    tmppath = os.path.join(DOWNLOAD_DIR, "tmp.pdf")
    with open(tmppath, "wb") as f:
        f.write(response.content)
    # short timeout to ensure file is closed
    sleep(0.2)

    pdf_info = pdf2bib(tmppath)
    bibtex = pdf_info["bibtex"]
    # extract id from string:
    # @article{authorYEARtitle, ...}
    # ^^^^^^^^^^^^^^^
    if bibtex is None:
        notify("Skipping, doi extraction failed")
        os.remove(tmppath)
        return
    bibtex_id = bibtex.split("{")[1].split(",")[0]
    outpath = os.path.join(DOWNLOAD_DIR, f"{bibtex_id}.pdf")
    if os.path.exists(outpath):
        notify(f"Skipping, {bibtex_id} entry already exists")
        os.remove(tmppath)
        return

    os.rename(tmppath, outpath)
    # add to all bib
    with open(os.path.join(DOWNLOAD_DIR, "citation.bib"), "a") as f:
        f.write("\n")
        f.write(bibtex)
        f.write("\n")
    notify(f"Added entry {bibtex_id}")

    # if e["QUTE_MODE"] == "hints":
    #     if "QUTE_USER_AGENT" in e:
    #         r = get(url, headers={"User-Agent": e["QUTE_USER_AGENT"]})
    #     else:
    #         r = get(url, headers={})
    #     html = r.text
    #
    # else:  # I guess this must be command mode
    #     fd = open(e["QUTE_HTML"])
    #     html = fd.read()
    #     fd.close()
    #


if __name__ == "__main__":
    main()
