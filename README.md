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
