#!/usr/bin/env python
# -*- coding: utf-8 -*-

import imaplib
import email
import html
import re
import requests
import os
import time
import yaml
import json


def load_json(filename):
    with open(filename) as f:
        return json.load(f)


def dump_json(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, sort_keys=True, indent=2)


def load_yaml(filename):
    with open(filename) as f:
        return yaml.safe_load(f)


def dump_yaml(filename, data):
    with open(filename, "w") as f:
        yaml.safe_dump(data, f)


class IMAPSettings:
    def __init__(self, imap_url, username, password):
        self.url = imap_url
        self.username = username
        self.password = password


class IMAPMailBox:
    def __init__(self, settings):
        self.settings = settings
        self.mailbox = None

    def __enter__(self):
        self.mailbox = imaplib.IMAP4_SSL(self.settings.url)
        self.mailbox.login(self.settings.username,
                           self.settings.password)
        return self.mailbox

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.mailbox.close()
        self.mailbox.logout()


class EmailParseException(Exception):
    pass


def check_imap_email(imap_settings, *,
                     n_checks=10, wait_in_seconds=30):
    """Checks an IMAP email for new messages from tdvms@afad.gov.tr
    and attempts to find the link for the zip file and download it."""
    download_links = []

    while n_checks > 0:
        with IMAPMailBox(imap_settings) as mailbox:
            mailbox.select("Inbox")
            typ, data = mailbox.search(None, "UNSEEN", "FROM", '"tdvms@afad.gov.tr"')
            mails = data[0].split()
            n_messages = len(mails)
            if n_messages == 0:
                print(f"No email found. Waiting for {wait_in_seconds} seconds")
                n_checks -= 1
            else:
                for num in reversed(mails):
                    link = get_download_link_from_email(mailbox, num)
                    if link:
                        download_links.append(link)
                break
        time.sleep(wait_in_seconds)

    for link in download_links:
        filename = link.split("/")[-1]
        if os.path.isfile(filename):
            print(f"Already downloaded: {filename}")
        else:
            print(f"Downloading {filename}...")
            with open(filename, "wb") as f:
                f.write(requests.get(link).content)


def get_download_link_from_email(mailbox, num):
    typ, data = mailbox.fetch(num, '(RFC822)')
    msg = email.message_from_bytes(data[0][1])
    txt = msg.get_payload(None, True).decode()
    if m := re.search("https://tdvms.afad.gov.tr/files/[a-zA-Z0-9_]+.zip", txt):
        zip_url = m.group(0)
        return zip_url
    else:
        raise EmailParseException(f"Link couldn't be found in the message {html.unescape(txt)}")
