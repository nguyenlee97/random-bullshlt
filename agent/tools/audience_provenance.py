"""Stable source citation metadata for executable audience recommendations."""
from __future__ import annotations


def catalog_source(segment: dict, index_metadata: dict | None = None) -> dict:
    source = {
        "type": "dmp_catalog",
        "endpoint": "/api/dmp/attributes",
        "segmentId": segment.get("segmentId"),
        "recordId": str(segment.get("_id") or ""),
    }
    metadata = index_metadata or {}
    if metadata.get("catalog_fingerprint"):
        source["catalogFingerprint"] = metadata["catalog_fingerprint"]
    if metadata.get("schema") is not None:
        source["indexSchema"] = metadata["schema"]
    return source
