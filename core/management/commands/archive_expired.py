from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.db.models import Q
from gifts.models import GiftList
from events.models import Event


class Command(BaseCommand):
    help = 'Archive expired gift lists and events (14 days after event_date)'

    def handle(self, *args, **options):
        cutoff = date.today() - timedelta(days=14)

        # Archive expired gift lists
        expired_lists = GiftList.objects.filter(
            is_archived=False,
            event_date__lt=cutoff,
        )
        expired_count = expired_lists.count()
        expired_lists.update(is_archived=True)
        self.stdout.write(f"Archived {expired_count} expired gift lists")

        # Archive expired events
        expired_events = Event.objects.filter(
            is_archived=False,
            event_date__lt=cutoff,
        )
        expired_event_count = expired_events.count()
        expired_events.update(is_archived=True)
        self.stdout.write(f"Archived {expired_event_count} expired events")

        total = expired_count + expired_event_count
        self.stdout.write(self.style.SUCCESS(f"Total archived: {total}"))