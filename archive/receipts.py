import json
from dataclasses import dataclass

from archive.artifacts import SealedBatch


@dataclass(frozen=True, slots=True)
class PublicationReceipt:
    artifact_id: int
    day: str
    counter_revision: str
    route_revision: str
    line_total: int
    pool_total: int


def build_receipt(batch: SealedBatch) -> PublicationReceipt:
    evidence = batch.evidence
    issued, received = evidence.totals
    return PublicationReceipt(
        batch.artifact_id, evidence.day, evidence.counter_revision,
        evidence.route_revision, issued, received,
    )


def receipt_matches_batch(receipt: PublicationReceipt, batch: SealedBatch) -> bool:
    return receipt == build_receipt(batch)


def encode_receipt(receipt: PublicationReceipt) -> str:
    return json.dumps({
        'artifact_id': receipt.artifact_id,
        'day': receipt.day,
        'counter_revision': receipt.counter_revision,
        'route_revision': receipt.route_revision,
        'line_total': hex(receipt.line_total),
        'pool_total': hex(receipt.pool_total),
    }, separators=(',', ':'))


def decode_receipt(payload: str) -> PublicationReceipt:
    data = json.loads(payload)
    return PublicationReceipt(
        data['artifact_id'], data['day'], data['counter_revision'], data['route_revision'],
        int(data['line_total'], 16), int(data['pool_total'], 16),
    )
