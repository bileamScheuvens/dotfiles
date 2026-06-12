#!/usr/bin/env nix-shell
#!nix-shell -i python3 -p python3Packages.tldextract python3Packages.pyperclip python3Packages.pexpect

# SPDX-FileCopyrightText: Chris Braun (cryzed) <cryzed@googlemail.com>
# SPDX-FileContributor: Adapted to rbw by Bileam Scheuvens <benedictbileam@gmx.de>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Insert login information using Bitwarden CLI and a dmenu-compatible application
(e.g. dmenu, rofi -dmenu, ...).
"""

USAGE = """The domain of the site has to be in the name of the Bitwarden entry, for example: "github.com/cryzed" or
"websites/github.com".  The login information is inserted by emulating key events using qutebrowser's fake-key command in this manner:
[USERNAME]<Tab>[PASSWORD], which is compatible with almost all login forms.

If enabled, with the `--totp` flag, it will also move the TOTP code to the
clipboard, much like the Firefox add-on.

You must register using `rbw register` prior to use of this script.

To use in qutebrowser, run: `spawn --userscript bitwarden_rbw.py`
"""

EPILOG = """WARNING: The login details are viewable as plaintext in qutebrowser's debug log
(qute://log) and might be shared if you decide to submit a crash report!"""

import argparse
import enum
import functools
import os
import shlex
import subprocess
import sys
import tldextract
import pexpect

argument_parser = argparse.ArgumentParser(
    description=__doc__,
    usage=USAGE,
    epilog=EPILOG,
)
argument_parser.add_argument("url", nargs="?", default=os.getenv("QUTE_URL"))
argument_parser.add_argument(
    "--dmenu-invocation",
    "-d",
    default="fuzzel --dmenu -i -p > -w 60",
    help="Invocation used to execute a dmenu-provider",
)
argument_parser.add_argument(
    "--password-prompt-invocation",
    "-p",
    default='fuzzel --dmenu -p "Master Password: " --password --lines 0 -w 40',
    help="Invocation used to prompt the user for their Bitwarden password",
)
argument_parser.add_argument(
    "--no-insert-mode",
    "-n",
    dest="insert_mode",
    action="store_false",
    help="Don't automatically enter insert mode",
)
argument_parser.add_argument(
    "--totp", "-t", action="store_true", help="Copy TOTP key to clipboard"
)
argument_parser.add_argument(
    "--io-encoding",
    "-i",
    default="UTF-8",
    help="Encoding used to communicate with subprocesses",
)
argument_parser.add_argument(
    "--user-maxlen",
    dest="user_maxlen",
    default=25,
    help="Maximum chars for username displayed in picker.",
)
argument_parser.add_argument(
    "--merge-candidates",
    "-m",
    action="store_true",
    help="Merge pass candidates for fully-qualified and registered domain name",
)
group = argument_parser.add_mutually_exclusive_group()
group.add_argument(
    "--username-only", "-e", action="store_true", help="Only insert username"
)
group.add_argument(
    "--password-only", "-w", action="store_true", help="Only insert password"
)
group.add_argument(
    "--totp-only", "-T", action="store_true", help="Only insert totp code"
)

stderr = functools.partial(print, file=sys.stderr)


class ExitCodes(enum.IntEnum):
    SUCCESS = 0
    FAILURE = 1
    # 1 is automatically used if Python throws an exception
    NO_PASS_CANDIDATES = 2
    COULD_NOT_MATCH_USERNAME = 3
    COULD_NOT_MATCH_PASSWORD = 4


def qute_command(command):
    with open(os.environ["QUTE_FIFO"], "w") as fifo:
        fifo.write(command + "\n")
        fifo.flush()


def format_choice(choice):
    idx, (user, domain) = choice[0], choice[1].split("\t")
    if len(user) > arguments.user_maxlen:
        user = f"{user[: arguments.user_maxlen - 2]}.."
    return f"{idx}: {user.ljust(arguments.user_maxlen)} @ {domain}"


def authenticate(password_prompt_invocation):
    process = subprocess.run(["rbw", "unlocked"], capture_output=True, text=True)
    if process.returncode == 0:
        return
    process = subprocess.run(
        shlex.split(password_prompt_invocation),
        text=True,
        stdout=subprocess.PIPE,
    )
    master_pass = process.stdout.strip()
    child = pexpect.spawn("rbw unlock")
    child.expect("Master Password:")
    child.sendline(master_pass)
    returncode = child.expect([pexpect.EOF, "Master Password:"])
    child.close()
    if returncode:
        qute_command("message-error 'Wrong Password'")
        raise ValueError("Wrong Password")


def list_vault_entries(domain, encoding, password_prompt_invocation):
    process = subprocess.run(
        [
            "rbw",
            "search",
            domain,
            "--fields",
            "user,name",
        ],
        capture_output=True,
    )
    err = process.stderr.decode(encoding).strip()
    if err:
        msg = "Bitwarden CLI returned for {:s} - {:s}".format(domain, err)
        stderr(msg)

    out = process.stdout.decode(encoding).strip()
    if process.returncode or not out:
        return []

    return out.split("\n")


def get_vault_entry(domain, username, target, encoding):
    process = subprocess.run(
        ["rbw", "get", domain, username],
        capture_output=True,
    )
    err = process.stderr.decode(encoding).strip()
    if err:
        stderr(err)

    if process.returncode:
        return "[]"
    return process.stdout.decode(encoding).strip()


def get_password(domain, username, encoding):
    return get_vault_entry(domain, username, "get", encoding)


def get_totp_code(domain, username, encoding):
    return get_vault_entry(domain, username, "totp", encoding)


def dmenu(items, invocation, encoding):
    command = shlex.split(invocation)
    process = subprocess.run(
        command, input="\n".join(items).encode(encoding), stdout=subprocess.PIPE
    )
    return process.stdout.decode(encoding).strip()


def fake_key_raw(text):
    for character in text:
        # Escape all characters by default, space requires special handling
        sequence = '" "' if character == " " else r"\{}".format(character)
        qute_command("fake-key {}".format(sequence))


def main(arguments):
    if not arguments.url:
        argument_parser.print_help()
        return ExitCodes.FAILURE

    authenticate(arguments.password_prompt_invocation)
    extract_result = tldextract.extract(arguments.url)

    # Try to find candidates using targets in the following order: fully-qualified domain name (includes subdomains),
    # the registered domain name and finally: the IPv4 address if that's what
    # the URL represents
    candidates = []

    for target in filter(
        None,
        [
            extract_result.fqdn,
            (
                extract_result.top_domain_under_public_suffix
                if hasattr(extract_result, "top_domain_under_public_suffix")
                else extract_result.registered_domain
            ),
            extract_result.subdomain + "." + extract_result.domain,
            extract_result.domain,
            extract_result.ipv4,
        ],
    ):
        target_candidates = list_vault_entries(
            target,
            arguments.io_encoding,
            arguments.password_prompt_invocation,
        )
        candidates = candidates + target_candidates
        if not arguments.merge_candidates and target_candidates:
            break
    else:
        if not candidates:
            err_msg = "No pass candidates for URL {!r} found!".format(arguments.url)
            stderr(err_msg)
            qute_command(f"message-error {err_msg}")
            return ExitCodes.NO_PASS_CANDIDATES

    if len(candidates) == 1:
        selected_idx = 0
    else:
        choice = dmenu(
            map(format_choice, enumerate(candidates)),
            arguments.dmenu_invocation,
            arguments.io_encoding,
        )
        # Nothing was selected, simply return
        if choice == "":
            return ExitCodes.SUCCESS
        selected_idx = int(choice.split(":")[0])

    username, domain = candidates[selected_idx].split("\t")
    password = get_password(domain, username, arguments.io_encoding)
    totp = get_totp_code(domain, username, arguments.io_encoding)

    if arguments.username_only:
        fake_key_raw(username)
    elif arguments.password_only:
        fake_key_raw(password)
    elif arguments.totp_only:
        # No point in moving it to the clipboard in this case
        fake_key_raw(totp)
    else:
        # Enter username and password using fake-key and <Tab> (which seems to work almost universally), then switch
        # back into insert-mode, so the form can be directly submitted by
        # hitting enter afterwards
        fake_key_raw(username)
        qute_command("fake-key <Tab>")
        fake_key_raw(password)

    if arguments.insert_mode:
        qute_command("mode-enter insert")

    # If it finds a TOTP code, it copies it to the clipboard,
    # which is the same behavior as the Firefox add-on.
    if not arguments.totp_only and totp and arguments.totp:
        # The import is done here, to make pyperclip an optional dependency
        import pyperclip

        pyperclip.copy(totp)

    return ExitCodes.SUCCESS


if __name__ == "__main__":
    arguments = argument_parser.parse_args()
    sys.exit(main(arguments))
