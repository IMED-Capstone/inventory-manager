"""Creation and lifecycle services for persistent in-app notifications."""

import datetime
from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from .models import (
    Device,
    Item,
    Notification,
    NotificationEvent,
    WasteReversalRequest,
)


EXPIRATION_INTERVALS = (1, 7, 14, 30)


def _item_url(item: Item) -> str:
    query = {"search_field": "item_no", "search_term": item.item_no}
    if item.device_id:
        query["device"] = item.device_id
    return f"{reverse('item-details')}?{urlencode(query)}"


def _deliver_event(*, recipients, event_key: str, **notification_data) -> int:
    """Snapshot recipients once and idempotently deliver one event to each."""
    with transaction.atomic():
        _, event_created = NotificationEvent.objects.get_or_create(event_key=event_key)
        if not event_created:
            return 0

        recipient_ids = list(recipients.values_list("pk", flat=True))
        Notification.objects.bulk_create(
            [
                Notification(
                    recipient_id=recipient_id,
                    event_key=event_key,
                    **notification_data,
                )
                for recipient_id in recipient_ids
            ],
            ignore_conflicts=True,
        )
        return len(recipient_ids)


def _all_active_users():
    return get_user_model().objects.filter(is_active=True)


def notify_low_stock_state_change(
    *,
    device_id: int,
    was_low: bool,
    is_low: bool,
    event_key: str,
    actor_id: int | None = None,
) -> int:
    """Create a threshold-crossing alert or resolve prior low-stock alerts."""
    if was_low == is_low:
        return 0

    if not is_low:
        Notification.objects.filter(
            device_id=device_id,
            kind=Notification.Kind.LOW_STOCK,
            resolved_at__isnull=True,
        ).update(resolved_at=timezone.now())
        return 0

    device = Device.objects.get(pk=device_id)
    return _deliver_event(
        recipients=_all_active_users(),
        event_key=event_key,
        kind=Notification.Kind.LOW_STOCK,
        severity=Notification.Severity.WARNING,
        title=f"Low stock: {device.device_name or device.device_identifier}",
        message=(
            f"Available inventory is {device.current_count}, at or below the "
            f"threshold of {device.low_stock_threshold}."
        ),
        actor_id=actor_id,
        device=device,
        target_url=f"{reverse('item-details')}?{urlencode({'device': device.pk})}",
    )


def notify_waste_reversal_requested(reversal_request_id: int) -> int:
    reversal_request = WasteReversalRequest.objects.select_related(
        "waste_transaction__item", "requested_by"
    ).get(pk=reversal_request_id)
    item = reversal_request.waste_transaction.item
    recipients = _all_active_users().filter(is_staff=True).exclude(
        pk=reversal_request.requested_by_id
    )
    return _deliver_event(
        recipients=recipients,
        event_key=f"waste-reversal-requested:{reversal_request.pk}",
        kind=Notification.Kind.WASTE_REVERSAL_REQUESTED,
        severity=Notification.Severity.WARNING,
        title="Waste reversal awaiting review",
        message=f"A reversal was requested for UDI {item.item_no}.",
        actor=reversal_request.requested_by,
        item=item,
        waste_reversal_request=reversal_request,
        target_url=reverse("waste-log"),
    )


def notify_waste_reversal_reviewed(reversal_request_id: int) -> int:
    reversal_request = WasteReversalRequest.objects.select_related(
        "waste_transaction__item", "requested_by", "reviewed_by"
    ).get(pk=reversal_request_id)
    approved = reversal_request.status == WasteReversalRequest.Status.APPROVED
    status_label = "approved" if approved else "rejected"
    Notification.objects.filter(
        event_key=f"waste-reversal-requested:{reversal_request.pk}",
        resolved_at__isnull=True,
    ).update(resolved_at=timezone.now())
    kind = (
        Notification.Kind.WASTE_REVERSAL_APPROVED
        if approved
        else Notification.Kind.WASTE_REVERSAL_REJECTED
    )
    return _deliver_event(
        recipients=_all_active_users().filter(pk=reversal_request.requested_by_id),
        event_key=f"waste-reversal-{status_label}:{reversal_request.pk}",
        kind=kind,
        severity=(
            Notification.Severity.INFO
            if approved
            else Notification.Severity.WARNING
        ),
        title=f"Waste reversal {status_label}",
        message=(
            f"Your reversal request for UDI "
            f"{reversal_request.waste_transaction.item.item_no} was {status_label}."
        ),
        actor=reversal_request.reviewed_by,
        item=reversal_request.waste_transaction.item,
        waste_reversal_request=reversal_request,
        target_url=reverse("waste-log"),
    )


def resolve_item_expiration_notifications(item_id: int) -> None:
    Notification.objects.filter(
        item_id=item_id,
        kind__in=[Notification.Kind.EXPIRING_ITEM, Notification.Kind.EXPIRED_ITEM],
        resolved_at__isnull=True,
    ).update(resolved_at=timezone.now())


def generate_expiration_notifications(*, today=None) -> int:
    """Generate idempotent expiration milestones for currently available items."""
    today = today or timezone.localdate()
    delivered = 0
    items = Item.objects.filter(
        is_available=True,
        exp_date__isnull=False,
        exp_date__lte=today + datetime.timedelta(days=max(EXPIRATION_INTERVALS)),
    ).select_related("device")

    for item in items:
        days_remaining = (item.exp_date - today).days
        if days_remaining <= 0:
            milestone = 0
            kind = Notification.Kind.EXPIRED_ITEM
            severity = Notification.Severity.CRITICAL
            title = f"Expired item: {item.item_no}"
            message = f"UDI {item.item_no} expired on {item.exp_date:%Y-%m-%d}."
        else:
            milestone = next(
                (
                    interval
                    for interval in EXPIRATION_INTERVALS
                    if days_remaining <= interval
                ),
                None,
            )
            if milestone is None:
                continue
            kind = Notification.Kind.EXPIRING_ITEM
            severity = (
                Notification.Severity.CRITICAL
                if milestone == 1
                else Notification.Severity.WARNING
            )
            title = f"Item expires within {milestone} day{'s' if milestone != 1 else ''}"
            message = (
                f"UDI {item.item_no} expires on {item.exp_date:%Y-%m-%d} "
                f"({days_remaining} day{'s' if days_remaining != 1 else ''} remaining)."
            )

        delivered += _deliver_event(
            recipients=_all_active_users(),
            event_key=(
                f"expiration:item:{item.pk}:date:{item.exp_date.isoformat()}:"
                f"milestone:{milestone}"
            ),
            kind=kind,
            severity=severity,
            title=title,
            message=message,
            item=item,
            device=item.device,
            target_url=_item_url(item),
        )

    return delivered
