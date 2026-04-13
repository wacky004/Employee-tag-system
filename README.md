# Attendance Monitoring System

Initial Django scaffold for an employee attendance and status monitoring system.

## Stack

- Django
- Django Templates
- Bootstrap
- PostgreSQL
- Gunicorn
- Nginx

## Apps

- `accounts`
- `employees`
- `tagging`
- `attendance`
- `auditlogs`
- `core`

## Quick start

1. Create a virtual environment.
2. Install the requirements.
3. Run migrations.
4. Create a superuser.
5. Start the development server.

## Seed default tag types

Run the following command to create the default attendance tags:

```bash
python manage.py seed_tag_types
```

## Local office deployment

This project can be hosted on one Windows office PC and accessed by other computers on the same Wi-Fi or LAN.

### First-time setup

Run:

```powershell
PowerShell -ExecutionPolicy Bypass -File .\deploy\office_first_run.ps1
```

The startup script will auto-detect the current office IP each time it runs, so you do not need to edit `.env` whenever the Wi-Fi changes.

### Start the office server

Run:

```powershell
PowerShell -ExecutionPolicy Bypass -File .\deploy\start_office_server.ps1
```

This starts the app with `Waitress` on:

```text
http://0.0.0.0:8000
```

The script will print both URLs to use:

- `http://127.0.0.1:8000/` on the server PC
- `http://<detected-ip>:8000/` on other office computers

Other office computers should open it using the detected host PC IPv4 address, for example:

```text
http://192.168.1.20:8000/
```

### Notes

- Keep the host PC turned on while the office is using the app.
- Allow port `8000` through Windows Firewall if other PCs cannot connect.
- For multi-user office use, PostgreSQL is recommended over SQLite.
