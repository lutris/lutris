"""Inspect or skip GOG cloud-save transfers without exposing game objects."""

from dataclasses import dataclass

from lutris.services import gog_cloud_operation as sync
from lutris.util.notifications import NotificationSource

CLOUD_SAVE_STARTED = NotificationSource()
CLOUD_SAVE_ENDED = NotificationSource()


@dataclass(frozen=True)
class CloudSaveTransfer:
    id: str
    label: str
    progress: float
    can_skip: bool


def _id(operation: sync.CloudSyncOperation) -> str:
    return f"{operation.game.id}:{operation.direction}"


async def list_transfers() -> tuple[CloudSaveTransfer, ...]:
    return tuple(
        CloudSaveTransfer(_id(operation), progress.label_markup, progress.progress or 0.0, progress.can_stop)
        for operation in sync.list_operations()
        if not (progress := operation.get_progress()).has_ended
    )


async def skip_transfer(transfer_id: str) -> None:
    for operation in sync.list_operations():
        if _id(operation) == transfer_id and operation.get_progress().can_stop:
            operation.cancel()
            break


sync.CLOUD_SYNC_STARTED.register(lambda operation: CLOUD_SAVE_STARTED.fire(_id(operation)))
sync.CLOUD_SYNC_ENDED.register(lambda operation: CLOUD_SAVE_ENDED.fire(_id(operation)))
