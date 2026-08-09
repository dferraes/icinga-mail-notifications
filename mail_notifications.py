#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Copyright (C) 2025 David Ferraes
#
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
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Icinga2 Notification Script

This script sends detailed HTML email notifications for Icinga2 host and
service alerts. It is designed to be called by an Icinga2 NotificationCommand
and configured entirely through command-line arguments.
"""

import os
import smtplib
import ssl
import sys
import argparse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email.utils import formataddr
from urllib.parse import quote as url_quote

try:
    from jinja2 import Environment, FileSystemLoader
except ImportError:
    print("FATAL: The 'jinja2' library is required. Please install it in the virtual environment.", file=sys.stderr)
    sys.exit(2)

def send_mail(recipient, subject, body, smtp_args):
    """
    Connects to an SMTP server and sends the notification email.
    All SMTP parameters are passed via the smtp_args object.
    """
    sender_name = smtp_args.smtp_sender_name
    sender_email = smtp_args.smtp_sender
    smtp_host = smtp_args.smtp_host
    smtp_port = smtp_args.smtp_port
    smtp_user = smtp_args.smtp_user
    smtp_password = smtp_args.smtp_password

    if not all([sender_email, smtp_host, smtp_port, smtp_user, smtp_password]):
        print("FATAL: SMTP settings are not fully configured. Please check your "
              "SMTP command-line arguments.", file=sys.stderr)
        sys.exit(2)

    # A recipient carrying a newline would let the caller append arbitrary
    # headers to the message. Icinga user emails are semi-trusted input, so
    # refuse rather than silently sanitize.
    if any(c in recipient for c in "\r\n"):
        print("FATAL: The recipient address contains a line break.", file=sys.stderr)
        sys.exit(2)

    message = MIMEMultipart("alternative")
    message["Subject"] = Header(subject, 'utf-8')
    message["From"] = formataddr((str(Header(sender_name, 'utf-8')), sender_email))
    message["To"] = recipient

    # Attach the HTML body. The email client will try to render the last part first.
    html_part = MIMEText(body, "html", 'utf-8')
    message.attach(html_part)

    try:
        # For security, this script uses STARTTLS.
        # It will not work with legacy SMTP over SSL on port 465.
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            # Without an explicit context, smtplib does not verify the server
            # certificate, so the channel is encrypted but not authenticated.
            server.starttls(context=ssl.create_default_context())
            server.login(smtp_user, smtp_password)
            server.sendmail(sender_email, [recipient], message.as_string())
            print(f"Notification email sent successfully to {recipient}.")
    except smtplib.SMTPException as e:
        print(f"ERROR: Unable to send email: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    """
    Main function to gather Icinga2 data, construct the email subject and
    body, and trigger the send mail function.
    """
    # --- Argument Parsing ---
    parser = argparse.ArgumentParser(description="Icinga2 HTML Email Notification Script")

    # SMTP Arguments
    # SECURITY WARNING: Passing passwords via command-line arguments can be insecure as they may be visible in the process list.
    parser.add_argument("--smtp-sender", required=True, help="Sender email address")
    parser.add_argument("--smtp-sender-name", default="Icinga 2", help="Sender display name")
    parser.add_argument("--smtp-host", required=True, help="SMTP server hostname")
    parser.add_argument("--smtp-port", type=int, default=587, help="SMTP server port")
    parser.add_argument("--smtp-user", required=True, help="SMTP username")
    parser.add_argument("--smtp-password", required=True, help="SMTP password")

    parser.add_argument("--lang", default="en", help="Language for the notification (e.g., 'en', 'es')")
    parser.add_argument("--user-email", required=True, help="Recipient email address")
    parser.add_argument("--notificationtype", required=True, help="Type of notification (e.g., PROBLEM, RECOVERY)")
    parser.add_argument("--notification_author", default="", help="Author of the notification comment")
    parser.add_argument("--notification_comment", default="", help="The notification comment text")
    parser.add_argument("--hostdisplayname", required=True, help="The display name of the host")
    parser.add_argument("--state", required=True, help="The state of the host or service")
    parser.add_argument("--output", default="", help="The output of the host or service check")
    parser.add_argument("--notification_hostnotes", default="", help="Notes for the host")
    parser.add_argument("--servicedisplayname", default="", help="The display name of the service (if applicable)")
    parser.add_argument("--notification_servicenotes", default="", help="Notes for the service")
    parser.add_argument("--icingaweb2_base_url", default="", help="Base URL for Icinga Web 2")

    try:
        args = parser.parse_args()
    except SystemExit as exc:
        # argparse exits 0 for --help and 2 for a usage error. Preserve the
        # success case; turn anything else into the failure code Icinga expects.
        sys.exit(0 if exc.code == 0 else 2)

    # --- i18n Translations ---
    translations = {
        'en': {
            'host': 'Host',
            'service': 'Service',
            'on': 'on',
            'is': 'is',
            'state': 'State',
            'notes': 'Notes',
            'plugin_output': 'Plugin Output',
            'notification_comment': 'Notification Comment',
            'author': 'Author',
            'comment': 'Comment',
        },
        'es': {
            'host': 'Host',
            'service': 'Servicio',
            'on': 'en',
            'is': 'está',
            'state': 'Estado',
            'notes': 'Notas',
            'plugin_output': 'Salida del Plugin',
            'notification_comment': 'Comentario de la Notificación',
            'author': 'Autor',
            'comment': 'Comentario',
        }
    }
    # Fallback to English if the language is not defined
    t = translations.get(args.lang, translations['en'])

    icingaweb2_url = ""
    # --- Determine if it's a Host or Service notification ---
    is_host_notification = not args.servicedisplayname
    if is_host_notification:
        subject = f"[{args.notificationtype}] {t['host']} {args.hostdisplayname} {t['is']} {args.state}"
        notes = args.notification_hostnotes
        object_type = t['host']
        object_name = args.hostdisplayname
        if args.icingaweb2_base_url:
            icingaweb2_url = f"{args.icingaweb2_base_url}/monitoring/host/show?host={url_quote(args.hostdisplayname)}"
    else:
        subject = f"[{args.notificationtype}] {t['service']} {args.servicedisplayname} {t['on']} {args.hostdisplayname} {t['is']} {args.state}"
        notes = args.notification_servicenotes
        object_type = t['service']
        object_name = args.servicedisplayname
        if args.icingaweb2_base_url:
            icingaweb2_url = f"{args.icingaweb2_base_url}/monitoring/service/show?host={url_quote(args.hostdisplayname)}&service={url_quote(args.servicedisplayname)}"

    # --- Map state and notification type to color for better visual representation ---
    type_and_state_colors = {
        "RECOVERY": "#4CAF50", "UP": "#4CAF50", "OK": "#4CAF50",
        "PROBLEM": "#F44336", "DOWN": "#F44336", "CRITICAL": "#F44336",
        "ACKNOWLEDGEMENT": "#2196F3",
        "WARNING": "#FFC107",
        "UNKNOWN": "#9E9E9E", "UNREACHABLE": "#9E9E9E",
    }
    # Notification type takes precedence (e.g., a RECOVERY is always green)
    state_color = type_and_state_colors.get(args.notificationtype.upper()) or type_and_state_colors.get(args.state.upper(), "#607D8B")

    # --- Prepare template rendering ---
    template_dir = os.path.dirname(os.path.abspath(__file__))
    jinja_env = Environment(loader=FileSystemLoader(template_dir), autoescape=True)

    template_context = {
        "t": t,  # Pass the translation dictionary to the template
        "notification_type": args.notificationtype,
        "host_name": args.hostdisplayname,
        "service_desc": args.servicedisplayname,
        "state": args.state,
        "output": args.output,
        "notes": notes,
        "author": args.notification_author,
        "comment": args.notification_comment,
        "object_type": object_type,
        "object_name": object_name,
        "state_color": state_color,
        "icingaweb2_url": icingaweb2_url,
    }

    html_body = jinja_env.get_template("email_template.html.j2").render(template_context)
    send_mail(args.user_email, subject, html_body, args)

if __name__ == "__main__":
    main()
