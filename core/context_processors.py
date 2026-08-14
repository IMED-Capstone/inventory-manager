"""Template context shared across authenticated application pages."""

from .models import Notification


def notification_inbox(request):
    if not request.user.is_authenticated:
        return {
            "recent_notifications": [],
            "unread_notification_count": 0,
        }

    visible = Notification.objects.filter(
        recipient=request.user,
        dismissed_at__isnull=True,
    )
    return {
        "recent_notifications": visible.select_related("device", "item")[:5],
        "unread_notification_count": visible.filter(read_at__isnull=True).count(),
    }
