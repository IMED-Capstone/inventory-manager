"""Generate time-based in-app notifications."""

from django.core.management.base import BaseCommand

from core.notification_services import generate_expiration_notifications


class Command(BaseCommand):
    help = "Generate idempotent expiration notifications for available inventory."

    def handle(self, *args, **options):
        delivered = generate_expiration_notifications()
        self.stdout.write(
            self.style.SUCCESS(f"Delivered {delivered} expiration notifications.")
        )
