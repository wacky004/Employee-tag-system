from django.core.management.base import BaseCommand

from tagging.models import TagType


DEFAULT_TAG_TYPES = [
    {
        "code": "TIME_IN",
        "name": "Time In",
        "category": TagType.Category.SHIFT,
        "direction": TagType.Direction.IN,
        "default_allowed_minutes": None,
        "sort_order": 1,
    },
    {
        "code": "TIME_OUT",
        "name": "Time Out",
        "category": TagType.Category.SHIFT,
        "direction": TagType.Direction.OUT,
        "default_allowed_minutes": None,
        "sort_order": 2,
    },
    {
        "code": "LUNCH_OUT",
        "name": "Lunch Out",
        "category": TagType.Category.LUNCH,
        "direction": TagType.Direction.OUT,
        "default_allowed_minutes": 60,
        "sort_order": 3,
    },
    {
        "code": "LUNCH_IN",
        "name": "Lunch In",
        "category": TagType.Category.LUNCH,
        "direction": TagType.Direction.IN,
        "default_allowed_minutes": None,
        "sort_order": 4,
    },
    {
        "code": "BREAK_OUT",
        "name": "Break Out",
        "category": TagType.Category.BREAK,
        "direction": TagType.Direction.OUT,
        "default_allowed_minutes": 15,
        "sort_order": 5,
    },
    {
        "code": "BREAK_IN",
        "name": "Break In",
        "category": TagType.Category.BREAK,
        "direction": TagType.Direction.IN,
        "default_allowed_minutes": None,
        "sort_order": 6,
    },
    {
        "code": "BIO_OUT",
        "name": "Bio Out",
        "category": TagType.Category.BIO,
        "direction": TagType.Direction.OUT,
        "default_allowed_minutes": 10,
        "sort_order": 7,
    },
    {
        "code": "BIO_IN",
        "name": "Bio In",
        "category": TagType.Category.BIO,
        "direction": TagType.Direction.IN,
        "default_allowed_minutes": None,
        "sort_order": 8,
    },
]


class Command(BaseCommand):
    help = "Create or update the default attendance tag types."

    def handle(self, *args, **options):
        created_count = 0
        updated_count = 0

        for tag_data in DEFAULT_TAG_TYPES:
            tag_type, created = TagType.objects.update_or_create(
                code=tag_data["code"],
                defaults=tag_data,
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"Created {tag_type.code}"))
            else:
                updated_count += 1
                self.stdout.write(self.style.WARNING(f"Updated {tag_type.code}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeding complete. Created: {created_count}, Updated: {updated_count}"
            )
        )
