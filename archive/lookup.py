from archive.artifacts import SealedBatch, decode_sealed_batch
from archive.receipts import PublicationReceipt, decode_receipt, receipt_matches_batch
from archive.store import ArchiveStore


class UnknownArtifactError(LookupError):
    """The archive has no publication under the supplied identifier."""


class ArchiveConsistencyError(RuntimeError):
    """The stored artifact and receipt cannot be read as one publication."""


def _read_pair(archive: ArchiveStore, artifact_id: int) -> tuple[SealedBatch, PublicationReceipt]:
    artifact_payload, receipt_payload = archive.read_publication(artifact_id)
    if artifact_payload is None and receipt_payload is None:
        raise UnknownArtifactError(f'unknown artifact {artifact_id!r}')
    if artifact_payload is None or receipt_payload is None:
        raise ArchiveConsistencyError(f'incomplete publication {artifact_id}')
    try:
        batch = decode_sealed_batch(artifact_payload)
        receipt = decode_receipt(receipt_payload)
    except (KeyError, TypeError, ValueError) as error:
        raise ArchiveConsistencyError(f'invalid publication payload {artifact_id}') from error
    if batch.artifact_id != artifact_id or not receipt_matches_batch(receipt, batch):
        raise ArchiveConsistencyError(f'artifact and receipt disagree for {artifact_id}')
    return batch, receipt


def read_receipt(archive: ArchiveStore, artifact_id: int) -> PublicationReceipt:
    return _read_pair(archive, artifact_id)[1]


def get_sealed_batch(archive: ArchiveStore, artifact_id: int) -> SealedBatch:
    return _read_pair(archive, artifact_id)[0]
