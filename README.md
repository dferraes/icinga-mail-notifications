# Icinga 2 HTML Email Notifications

A small Python script that sends readable HTML email notifications for Icinga 2
host and service alerts. It replaces the stock Perl and shell notification
scripts with something easier to read, translate and modify.

![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)

## Features

- **Rich HTML email** — clean, responsive layout that renders well on phones.
- **Direct links** — a button that opens the host or service in Icinga Web 2.
- **Internationalization** — English and Spanish included; adding a language is
  a dictionary entry.
- **Full context** — host/service notes, plugin output, and the author and
  comment of the notification.
- **Stateful colors** — the header turns green, red, amber or grey depending on
  the notification type and state.
- **Verified TLS** — connects over STARTTLS and validates the server
  certificate.

## Requirements

- An Icinga 2 instance.
- Python 3.9+ with the `venv` module on the Icinga 2 master or satellite.
  (CI covers 3.9, 3.11 and 3.13.)
- **Jinja2** — the only external dependency, used to render the template.
- An SMTP server that offers STARTTLS on the submission port and requires
  authentication (see [Limitations](#limitations)).

## Installation

1. **Create a directory for the script and its template:**

   ```bash
   sudo mkdir -p /etc/icinga2/scripts/mail_notifications
   ```

2. **Copy `mail_notifications.py` and `email_template.html.j2` into it.** Both
   must live in the same directory — the script loads the template from its own
   location.

3. **Create a virtual environment and install Jinja2:**

   ```bash
   sudo python3 -m venv /opt/mail_notifications_venv
   sudo /opt/mail_notifications_venv/bin/pip install jinja2
   ```

4. **Give the Icinga user ownership** (the user is `icinga` on most distributions,
   `nagios` on some):

   ```bash
   sudo chown -R icinga:icinga /etc/icinga2/scripts/mail_notifications
   sudo chown -R icinga:icinga /opt/mail_notifications_venv
   ```

## Icinga 2 configuration

Icinga 2 has no generic "current object" macro, so host and service
notifications need one `NotificationCommand` each. They differ only in which
state, output and display name they pass.

**Keep the SMTP password in `constants.conf`** and restrict that file
(`chmod 600`), rather than writing it into a command definition that is usually
world-readable.

```icinga
// In /etc/icinga2/constants.conf
const SmtpPassword = "your-smtp-password"

// In /etc/icinga2/conf.d/commands.conf
object NotificationCommand "python-html-mail-host" {
  command = [
    "/opt/mail_notifications_venv/bin/python",
    "/etc/icinga2/scripts/mail_notifications/mail_notifications.py"
  ]

  arguments = {
    "--smtp-sender"        = "icinga@example.com"
    "--smtp-sender-name"   = "Icinga Monitoring"
    "--smtp-host"          = "smtp.example.com"
    "--smtp-port"          = "587"
    "--smtp-user"          = "your-smtp-username"
    "--smtp-password"      = SmtpPassword

    "--icingaweb2_base_url"   = "https://icinga.example.com/icingaweb2"
    "--lang"                  = "$user.vars.language$"
    "--user-email"            = "$user.email$"
    "--notificationtype"      = "$notification.type$"
    "--notification_author"   = "$notification.author$"
    "--notification_comment"  = "$notification.comment$"
    "--hostdisplayname"       = "$host.display_name$"
    "--state"                 = "$host.state$"
    "--output"                = "$host.output$"
    "--notification_hostnotes" = "$host.notes$"
  }
}

object NotificationCommand "python-html-mail-service" {
  command = [
    "/opt/mail_notifications_venv/bin/python",
    "/etc/icinga2/scripts/mail_notifications/mail_notifications.py"
  ]

  arguments = {
    "--smtp-sender"        = "icinga@example.com"
    "--smtp-sender-name"   = "Icinga Monitoring"
    "--smtp-host"          = "smtp.example.com"
    "--smtp-port"          = "587"
    "--smtp-user"          = "your-smtp-username"
    "--smtp-password"      = SmtpPassword

    "--icingaweb2_base_url"   = "https://icinga.example.com/icingaweb2"
    "--lang"                  = "$user.vars.language$"
    "--user-email"            = "$user.email$"
    "--notificationtype"      = "$notification.type$"
    "--notification_author"   = "$notification.author$"
    "--notification_comment"  = "$notification.comment$"
    "--hostdisplayname"       = "$host.display_name$"
    "--servicedisplayname"    = "$service.display_name$"
    "--state"                 = "$service.state$"
    "--output"                = "$service.output$"
    "--notification_servicenotes" = "$service.notes$"
  }
}
```

The script decides between the host and service layout by whether
`--servicedisplayname` arrives with a value.

**Per-user language (optional).** `--lang` falls back to English when the value
is empty or unknown, so users without the variable still get notifications.

```icinga
object User "juan" {
  email = "juan@example.com"
  vars.language = "es"
}
```

**Apply the notifications:**

```icinga
apply Notification "python-mail-host" to Host {
  command = "python-html-mail-host"
  users = host.vars.notification_users
  assign where host.vars.notification_users
}

apply Notification "python-mail-service" to Service {
  command = "python-html-mail-service"
  users = host.vars.notification_users
  assign where host.vars.notification_users
}
```

**Validate and reload:**

```bash
sudo icinga2 daemon -C
sudo systemctl reload icinga2
```

## Limitations

- **STARTTLS only.** Implicit TLS on port 465 is not supported; use the
  submission port (587).
- **Authentication is required.** `--smtp-user` and `--smtp-password` are
  mandatory, so an unauthenticated local relay cannot be used as-is.
- **The password is passed as a command-line argument**, which makes it visible
  in the process list to other users on the Icinga host. This is how Icinga 2
  passes arguments to notification commands; if that is unacceptable in your
  environment, restrict shell access on that machine.
- **Links target the legacy `monitoring` module** (`/monitoring/host/show`).
  Installations that use Icinga DB Web need a different path.

## Testing

Unit tests mock the SMTP layer and render the real template, so no mail is sent
and no network is touched:

```bash
python3 -m unittest discover
```

To send one real message and confirm your SMTP settings, credentials and
firewall rules, run the script directly with real values:

```bash
python3 mail_notifications.py \
    --smtp-host smtp.example.com \
    --smtp-user icinga \
    --smtp-password "$SMTP_PASSWORD" \
    --smtp-sender icinga@example.com \
    --user-email you@example.com \
    --notificationtype CUSTOM \
    --hostdisplayname test-host \
    --state DOWN \
    --output "Manual test"
```

## Contributing

Issues and pull requests are welcome.

## License

Copyright (C) 2025 David Ferraes.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version. See [LICENSE](LICENSE) for the full text.
