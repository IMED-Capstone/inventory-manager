"""Atomic inventory operations for individual UDI-identified items."""

from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import (
    Device,
    DeviceThresholdTransaction,
    Item,
    ItemTransaction,
    WasteReversalRequest,
)


class InventoryError(Exception):
    """Base exception for inventory operations that cannot be completed."""


class ItemNotFoundError(InventoryError):
    pass


class ItemAlreadyAvailableError(InventoryError):
    pass


class ItemUnavailableError(InventoryError):
    pass


class ItemAlreadyWastedError(InventoryError):
    pass


class InventoryStateError(InventoryError):
    pass


class ReversalError(InventoryError):
    pass


class ThresholdError(InventoryError):
    pass


def normalize_udi(udi: str) -> str:
    value = (udi or "").strip()
    if len(value) >= 2 and value.startswith("\\") and value.endswith("\\"):
        value = value[1:-1]
    return value


def _change_device_count(device_id: int | None, change: int):
    if device_id is None:
        return None

    try:
        device = Device.objects.select_for_update().get(pk=device_id)
    except Device.DoesNotExist as exc:
        raise InventoryStateError("The item's device does not exist.") from exc

    previous_count = device.current_count
    new_count = previous_count + change
    if new_count < 0:
        raise InventoryStateError("The device inventory count is inconsistent.")

    Device.objects.filter(pk=device_id).update(current_count=F("current_count") + change)
    device.current_count = new_count
    return device, previous_count, new_count


def _schedule_stock_notification(
    *, device, previous_count: int, new_count: int, event_key: str, actor
) -> None:
    from .notification_services import notify_low_stock_state_change

    transaction.on_commit(
        lambda: notify_low_stock_state_change(
            device_id=device.pk,
            was_low=previous_count <= device.low_stock_threshold,
            is_low=new_count <= device.low_stock_threshold,
            event_key=event_key,
            actor_id=getattr(actor, "pk", None),
        ),
        robust=True,
    )


@transaction.atomic
def record_stock_in(*, item: Item, actor, occurred_at=None) -> ItemTransaction:
    locked_item = Item.objects.select_for_update().get(pk=item.pk)
    if locked_item.is_available:
        raise ItemAlreadyAvailableError("This UDI is already available in inventory.")

    locked_item.is_available = True
    locked_item.save(update_fields=["is_available"])
    count_change = _change_device_count(locked_item.device_id, 1)

    inventory_transaction = ItemTransaction.objects.create(
        item=locked_item,
        transaction_type=ItemTransaction.TransactionType.STOCK_IN,
        event_type=ItemTransaction.EventType.STOCK_IN,
        change=1,
        occurred_at=occurred_at or timezone.now(),
        created_by=actor,
    )
    if count_change:
        device, previous_count, new_count = count_change
        _schedule_stock_notification(
            device=device,
            previous_count=previous_count,
            new_count=new_count,
            event_key=f"low-stock:inventory-transaction:{inventory_transaction.pk}",
            actor=actor,
        )
    return inventory_transaction


@transaction.atomic
def record_item_removal(
    *,
    udi: str,
    actor,
    is_waste: bool = False,
    occurred_at=None,
    notes: str = "",
    estimated_cost: Decimal | None = None,
) -> ItemTransaction:
    normalized_udi = normalize_udi(udi)
    try:
        item = (
            Item.objects.select_for_update()
            .select_related("device")
            .get(item_no=normalized_udi)
        )
    except Item.DoesNotExist as exc:
        raise ItemNotFoundError("No item exists for this UDI.") from exc

    if is_waste and ItemTransaction.objects.filter(
        item=item,
        event_type=ItemTransaction.EventType.WASTE,
        reversal__isnull=True,
    ).exists():
        raise ItemAlreadyWastedError("This item is already recorded as waste.")

    if not item.is_available:
        raise ItemUnavailableError("This item is not currently available in inventory.")

    item.is_available = False
    item.save(update_fields=["is_available"])
    count_change = _change_device_count(item.device_id, -1)

    inventory_transaction = ItemTransaction.objects.create(
        item=item,
        transaction_type=ItemTransaction.TransactionType.STOCK_OUT,
        event_type=(
            ItemTransaction.EventType.WASTE
            if is_waste
            else ItemTransaction.EventType.STOCK_OUT
        ),
        change=-1,
        occurred_at=occurred_at or timezone.now(),
        reason=notes if is_waste else "",
        estimated_cost=estimated_cost if is_waste else None,
        created_by=actor,
    )
    if count_change:
        device, previous_count, new_count = count_change
        _schedule_stock_notification(
            device=device,
            previous_count=previous_count,
            new_count=new_count,
            event_key=f"low-stock:inventory-transaction:{inventory_transaction.pk}",
            actor=actor,
        )
    from .notification_services import resolve_item_expiration_notifications

    transaction.on_commit(
        lambda: resolve_item_expiration_notifications(item.pk),
        robust=True,
    )
    return inventory_transaction


@transaction.atomic
def request_waste_reversal(
    *, transaction_id: int, requested_by, reason: str = ""
) -> WasteReversalRequest:
    try:
        waste_transaction = ItemTransaction.objects.select_for_update().get(
            pk=transaction_id,
            event_type=ItemTransaction.EventType.WASTE,
        )
    except ItemTransaction.DoesNotExist as exc:
        raise ReversalError("The selected waste transaction does not exist.") from exc

    if hasattr(waste_transaction, "reversal"):
        raise ReversalError("This waste transaction has already been reversed.")
    if waste_transaction.reversal_requests.filter(
        status=WasteReversalRequest.Status.PENDING
    ).exists():
        raise ReversalError("A reversal request is already pending.")

    reversal_request = WasteReversalRequest.objects.create(
        waste_transaction=waste_transaction,
        requested_by=requested_by,
        reason=reason,
    )
    from .notification_services import notify_waste_reversal_requested

    transaction.on_commit(
        lambda: notify_waste_reversal_requested(reversal_request.pk),
        robust=True,
    )
    return reversal_request


@transaction.atomic
def review_waste_reversal(*, request_id: int, reviewer, approve: bool):
    if not reviewer.is_staff:
        raise ReversalError("Only staff users may review reversal requests.")

    try:
        reversal_request = (
            WasteReversalRequest.objects.select_for_update()
            .select_related("waste_transaction__item")
            .get(pk=request_id)
        )
    except WasteReversalRequest.DoesNotExist as exc:
        raise ReversalError("The reversal request does not exist.") from exc

    if reversal_request.status != WasteReversalRequest.Status.PENDING:
        raise ReversalError("This reversal request has already been reviewed.")
    if reversal_request.requested_by_id == reviewer.pk:
        raise ReversalError("You cannot review your own reversal request.")

    reviewed_at = timezone.now()
    reversal_request.reviewed_by = reviewer
    reversal_request.reviewed_at = reviewed_at

    if not approve:
        reversal_request.status = WasteReversalRequest.Status.REJECTED
        reversal_request.save(
            update_fields=["status", "reviewed_by", "reviewed_at"]
        )
        from .notification_services import notify_waste_reversal_reviewed

        transaction.on_commit(
            lambda: notify_waste_reversal_reviewed(reversal_request.pk),
            robust=True,
        )
        return None

    waste_transaction = reversal_request.waste_transaction
    if hasattr(waste_transaction, "reversal"):
        raise ReversalError("This waste transaction has already been reversed.")

    item = Item.objects.select_for_update().get(pk=waste_transaction.item_id)
    if item.is_available:
        raise ReversalError(
            "This item is already available and cannot be restored again."
        )

    item.is_available = True
    item.save(update_fields=["is_available"])
    count_change = _change_device_count(item.device_id, 1)

    reversal = ItemTransaction.objects.create(
        item=item,
        transaction_type=ItemTransaction.TransactionType.STOCK_IN,
        event_type=ItemTransaction.EventType.WASTE_REVERSAL,
        change=1,
        occurred_at=reviewed_at,
        reason=reversal_request.reason,
        created_by=reviewer,
        reversal_of=waste_transaction,
    )
    reversal_request.status = WasteReversalRequest.Status.APPROVED
    reversal_request.save(update_fields=["status", "reviewed_by", "reviewed_at"])
    if count_change:
        device, previous_count, new_count = count_change
        _schedule_stock_notification(
            device=device,
            previous_count=previous_count,
            new_count=new_count,
            event_key=f"low-stock:inventory-transaction:{reversal.pk}",
            actor=reviewer,
        )
    from .notification_services import notify_waste_reversal_reviewed

    transaction.on_commit(
        lambda: notify_waste_reversal_reviewed(reversal_request.pk),
        robust=True,
    )
    return reversal


@transaction.atomic
def update_device_threshold(
    *,
    device_id: int,
    threshold: int,
    actor,
    source=DeviceThresholdTransaction.Source.MANUAL,
    reason: str = "",
):
    """Update a device threshold and append an audit-history record."""
    if source == DeviceThresholdTransaction.Source.MANUAL and not actor.is_staff:
        raise ThresholdError("Only staff users may change device thresholds.")
    if threshold < 0:
        raise ThresholdError("The low-stock threshold cannot be negative.")

    try:
        device = Device.objects.select_for_update().get(pk=device_id)
    except Device.DoesNotExist as exc:
        raise ThresholdError("The selected device does not exist.") from exc

    previous_threshold = device.low_stock_threshold
    if previous_threshold == threshold:
        return None

    was_low = device.current_count <= previous_threshold
    is_low = device.current_count <= threshold
    device.low_stock_threshold = threshold
    device.save(update_fields=["low_stock_threshold"])
    threshold_change = DeviceThresholdTransaction.objects.create(
        device=device,
        previous_threshold=previous_threshold,
        new_threshold=threshold,
        source=source,
        reason=reason,
        changed_by=actor,
    )

    from .notification_services import notify_low_stock_state_change

    transaction.on_commit(
        lambda: notify_low_stock_state_change(
            device_id=device.pk,
            was_low=was_low,
            is_low=is_low,
            event_key=f"low-stock:threshold-change:{threshold_change.pk}",
            actor_id=getattr(actor, "pk", None),
        ),
        robust=True,
    )
    return threshold_change
