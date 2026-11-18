from archive.artifacts import SealedBatch
from archive.receipts import PublicationReceipt, build_receipt
from archive.store import ArchiveStore, BeforeCommit
from settlement.evidence import AllocationEvidence


def publish_batch(
    archive: ArchiveStore, evidence: AllocationEvidence, before_commit: BeforeCommit | None,
) -> int:
    def materialize(artifact_id: int) -> tuple[SealedBatch, PublicationReceipt]:
        batch = SealedBatch(artifact_id, evidence)
        return batch, build_receipt(batch)

    return archive.commit_publication(materialize, before_commit)
