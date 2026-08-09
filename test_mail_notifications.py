#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025 David Ferraes

"""
Unit tests for mail_notifications.py.

These tests never touch the network: the SMTP layer is mocked. The Jinja2
template is rendered for real, so a broken template fails the suite.

Run with:  python3 -m unittest discover
"""

import argparse
import ssl
import sys
import unittest
from unittest.mock import MagicMock, patch

import mail_notifications

BASE_ARGV = [
    "--smtp-sender", "icinga@example.com",
    "--smtp-host", "smtp.example.com",
    "--smtp-user", "icinga",
    "--smtp-password", "secret",
    "--user-email", "oncall@example.com",
    "--notificationtype", "PROBLEM",
    "--hostdisplayname", "web01",
    "--state", "DOWN",
]


def run_main(extra_argv=None):
    """Run main() with send_mail mocked, and return the mock's call args."""
    argv = ["mail_notifications.py"] + BASE_ARGV + (extra_argv or [])
    with patch.object(sys, "argv", argv), \
            patch.object(mail_notifications, "send_mail") as send_mail:
        mail_notifications.main()
    send_mail.assert_called_once()
    recipient, subject, body, args = send_mail.call_args.args
    return recipient, subject, body, args


def smtp_args(**overrides):
    """Build the argparse namespace that send_mail expects."""
    values = {
        "smtp_sender_name": "Icinga 2",
        "smtp_sender": "icinga@example.com",
        "smtp_host": "smtp.example.com",
        "smtp_port": 587,
        "smtp_user": "icinga",
        "smtp_password": "secret",
    }
    values.update(overrides)
    return argparse.Namespace(**values)


class TestNotificationContent(unittest.TestCase):
    """main() builds the subject, recipient and rendered body."""

    def test_host_notification_subject(self):
        recipient, subject, _, _ = run_main()
        self.assertEqual(recipient, "oncall@example.com")
        self.assertEqual(subject, "[PROBLEM] Host web01 is DOWN")

    def test_service_notification_subject(self):
        _, subject, _, _ = run_main(["--servicedisplayname", "http"])
        self.assertEqual(subject, "[PROBLEM] Service http on web01 is DOWN")

    def test_spanish_translation(self):
        _, subject, _, _ = run_main(["--lang", "es"])
        self.assertEqual(subject, "[PROBLEM] Host web01 está DOWN")

    def test_unknown_language_falls_back_to_english(self):
        _, subject, _, _ = run_main(["--lang", "de"])
        self.assertEqual(subject, "[PROBLEM] Host web01 is DOWN")

    def test_body_contains_host_and_output(self):
        _, _, body, _ = run_main(["--output", "PING CRITICAL - 100% loss"])
        self.assertIn("web01", body)
        self.assertIn("PING CRITICAL - 100% loss", body)

    def test_problem_state_uses_red(self):
        _, _, body, _ = run_main()
        self.assertIn("#F44336", body)

    def test_recovery_type_wins_over_state(self):
        # A RECOVERY is green even though the state string is unknown to the map.
        _, _, body, _ = run_main(["--notificationtype", "RECOVERY", "--state", "UP"])
        self.assertIn("#4CAF50", body)

    def test_icingaweb2_link_present_when_base_url_given(self):
        _, _, body, _ = run_main(
            ["--icingaweb2_base_url", "https://icinga.example.com/icingaweb2"]
        )
        self.assertIn(
            "https://icinga.example.com/icingaweb2/monitoring/host/show?host=web01",
            body,
        )

    def test_no_link_without_base_url(self):
        _, _, body, _ = run_main()
        self.assertNotIn("/monitoring/host/show", body)

    def test_check_output_is_html_escaped(self):
        """Jinja2 autoescaping must neutralize markup coming from a check."""
        _, _, body, _ = run_main(["--output", "<script>alert(1)</script>"])
        self.assertNotIn("<script>", body)
        self.assertIn("&lt;script&gt;", body)


class TestSendMail(unittest.TestCase):
    """send_mail() talks to SMTP correctly, or refuses to."""

    def test_starttls_verifies_the_certificate(self):
        with patch.object(mail_notifications.smtplib, "SMTP") as smtp:
            server = smtp.return_value.__enter__.return_value
            mail_notifications.send_mail(
                "oncall@example.com", "subject", "<p>body</p>", smtp_args()
            )

        context = server.starttls.call_args.kwargs["context"]
        self.assertIsInstance(context, ssl.SSLContext)
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)

    def test_message_is_sent_to_the_recipient(self):
        with patch.object(mail_notifications.smtplib, "SMTP") as smtp:
            server = smtp.return_value.__enter__.return_value
            mail_notifications.send_mail(
                "oncall@example.com", "subject", "<p>body</p>", smtp_args()
            )

        server.login.assert_called_once_with("icinga", "secret")
        sender, recipients, raw = server.sendmail.call_args.args
        self.assertEqual(sender, "icinga@example.com")
        self.assertEqual(recipients, ["oncall@example.com"])
        self.assertIn("To: oncall@example.com", raw)

    def test_recipient_with_newline_is_refused(self):
        """A recipient carrying CRLF would inject arbitrary headers."""
        with patch.object(mail_notifications.smtplib, "SMTP") as smtp:
            with self.assertRaises(SystemExit) as ctx:
                mail_notifications.send_mail(
                    "oncall@example.com\r\nBcc: attacker@example.com",
                    "subject",
                    "<p>body</p>",
                    smtp_args(),
                )

        self.assertEqual(ctx.exception.code, 2)
        smtp.assert_not_called()

    def test_smtp_failure_exits_nonzero(self):
        with patch.object(mail_notifications.smtplib, "SMTP") as smtp:
            server = smtp.return_value.__enter__.return_value
            server.sendmail.side_effect = mail_notifications.smtplib.SMTPException("nope")
            with self.assertRaises(SystemExit) as ctx:
                mail_notifications.send_mail(
                    "oncall@example.com", "subject", "<p>body</p>", smtp_args()
                )

        self.assertEqual(ctx.exception.code, 1)


class TestArgumentHandling(unittest.TestCase):
    def test_missing_required_argument_exits_2(self):
        with patch.object(sys, "argv", ["mail_notifications.py"]), \
                patch.object(sys, "stderr", MagicMock()):
            with self.assertRaises(SystemExit) as ctx:
                mail_notifications.main()
        self.assertEqual(ctx.exception.code, 2)

    def test_help_exits_0(self):
        with patch.object(sys, "argv", ["mail_notifications.py", "--help"]), \
                patch.object(sys, "stdout", MagicMock()):
            with self.assertRaises(SystemExit) as ctx:
                mail_notifications.main()
        self.assertEqual(ctx.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
