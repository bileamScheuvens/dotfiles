#!/usr/bin/env python

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

"""Userscript to clone repo to specified location."""

from random import randint

from os import environ
from pathlib import Path
import os
import subprocess
from time import sleep

import sys
from urllib.parse import parse_qs, urlparse


ROOT = Path.home() / "code"


# Qute stuff
fifo = open(environ["QUTE_FIFO"], "w")


def notify(message):
    print('message-info "{}"'.format(message), file=fifo)


def notify_error(message):
    print('message-error "{}"'.format(message), file=fifo)


def main():
    repo = environ["QUTE_URL"][len("https://github.com/") :].split("/")
    owner, repo = repo[0], repo[1]
    process = subprocess.run(
        ["git", "clone", f"git@github.com:{owner}/{repo}", ROOT / repo],
        capture_output=True,
        text=True,
    )
    if process.returncode:
        msg = f"Failed to clone. stdout: {process.stdout.strip()} stderr: {process.stderr.strip()}"
        notify_error(msg)
        return
    notify(f"Cloned to {ROOT / repo}")


if __name__ == "__main__":
    main()
