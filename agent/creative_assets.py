"""Owned named reference assets for GPT Image creative generation."""
from __future__ import annotations

import base64
import hashlib
import uuid
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from io import BytesIO

import httpx
from PIL import Image

from config import config
from image_quota import actor_keys


ASSET_KINDS = {
    "logo", "product", "packshot", "character", "style_reference",
    "background", "legal",
}
MAX_ASSET_BYTES = 10 * 1024 * 1024
_mem_assets: dict[str, dict] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _collection():
    from session import _ensure_mongo
    if not await _ensure_mongo():
        return None
    import session as session_store
    return session_store._client[config.MONGODB_DB]["creative_reference_assets"]


async def ensure_indexes() -> None:
    collection = await _collection()
    if collection is None:
        return
    await collection.create_index([("actor_key", 1), ("created_at", -1)], name="creative_assets_owner")
    await collection.create_index(
        [("actor_key", 1), ("session_id", 1), ("created_at", -1)],
        name="creative_assets_owner_session",
    )
    await collection.create_index("sha256", name="creative_assets_hash")
    await collection.create_index("expires_at", expireAfterSeconds=0, name="creative_assets_retention")


def _public(doc: dict) -> dict:
    result = deepcopy(doc)
    result.pop("_id", None)
    result.pop("actor_key", None)
    result.pop("linked_actor_keys", None)
    return result


def _decode_data_url(data_url: str) -> tuple[bytes, str]:
    if not isinstance(data_url, str) or not data_url.startswith("data:image/") or ";base64," not in data_url:
        raise ValueError("asset must be a base64 image data URL")
    header, encoded = data_url.split(",", 1)
    mime = header[5:].split(";", 1)[0].lower()
    if mime not in {"image/png", "image/jpeg", "image/webp"}:
        raise ValueError("asset type must be PNG, JPEG, or WebP")
    try:
        payload = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise ValueError("asset image data is invalid") from exc
    if not payload or len(payload) > MAX_ASSET_BYTES:
        raise ValueError("asset must be between 1 byte and 10MB")
    return payload, mime


async def create_asset(
    actor: dict, *, session_id: str, name: str, kind: str,
    use_instruction: str, required: bool, data_url: str,
) -> dict:
    clean_name = " ".join(str(name or "").split())[:80]
    clean_kind = str(kind or "").strip().lower()
    if not clean_name:
        raise ValueError("asset name is required")
    if clean_kind not in ASSET_KINDS:
        raise ValueError("unsupported asset kind")
    payload, mime = _decode_data_url(data_url)
    try:
        with Image.open(BytesIO(payload)) as image:
            image.verify()
        with Image.open(BytesIO(payload)) as image:
            width, height = image.size
    except Exception as exc:
        raise ValueError("asset is not a readable image") from exc
    if width < 32 or height < 32 or width > 8000 or height > 8000:
        raise ValueError("asset dimensions must be between 32px and 8000px per edge")

    actor_key, linked = actor_keys(actor)
    asset_id = f"asset_{uuid.uuid4().hex}"
    digest = hashlib.sha256(payload).hexdigest()
    extension = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}[mime]
    filename = f"creative-ref-{digest[:24]}.{extension}"
    upload_url = f"{config.BACKEND_URL.rstrip('/')}/api/creative/upload-base64"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(upload_url, json={
            "base64": base64.b64encode(payload).decode("ascii"),
            "filename": filename, "mimeType": mime,
            "idempotencyKey": f"creative-reference:{digest}",
        })
    if response.status_code not in {200, 201}:
        raise RuntimeError(f"asset storage failed ({response.status_code})")
    stored = response.json()
    if not stored.get("url"):
        raise RuntimeError("asset storage returned no URL")

    now = _now()
    doc = {
        "_id": asset_id, "asset_id": asset_id, "actor_key": actor_key,
        "linked_actor_keys": linked, "session_id": session_id,
        "name": clean_name, "kind": clean_kind,
        "use_instruction": " ".join(str(use_instruction or "").split())[:500],
        "required": bool(required), "url": stored["url"],
        "filename": stored.get("filename") or filename, "mime_type": mime,
        "width": width, "height": height, "bytes": len(payload), "sha256": digest,
        "moderation": {"status": "validated_image", "checked_at": now},
        "lifecycle": "active", "created_at": now, "updated_at": now,
        "expires_at": now + timedelta(days=90),
    }
    collection = await _collection()
    if collection is None:
        _mem_assets[asset_id] = doc
    else:
        await collection.insert_one(doc)
    return _public(doc)


def _owner_keys(actor: dict) -> list[str]:
    primary, linked = actor_keys(actor)
    return [primary, *linked]


async def list_assets(actor: dict, session_id: str) -> list[dict]:
    keys = _owner_keys(actor)
    collection = await _collection()
    if collection is None:
        docs = [
            item for item in _mem_assets.values()
            if item.get("actor_key") in keys
            and item.get("session_id") == session_id
            and item.get("lifecycle") == "active"
        ]
    else:
        docs = await collection.find({
            "actor_key": {"$in": keys}, "session_id": session_id,
            "lifecycle": "active",
        }).sort("created_at", -1).to_list(length=100)
    return [_public(item) for item in docs]


async def get_assets(actor: dict, asset_ids: list[str], session_id: str) -> list[dict]:
    requested = list(dict.fromkeys(str(value) for value in asset_ids if value))
    if not requested:
        return []
    keys = _owner_keys(actor)
    collection = await _collection()
    if collection is None:
        docs = [
            _mem_assets[value] for value in requested
            if value in _mem_assets and _mem_assets[value].get("actor_key") in keys
            and _mem_assets[value].get("session_id") == session_id
            and _mem_assets[value].get("lifecycle") == "active"
        ]
    else:
        docs = await collection.find({
            "_id": {"$in": requested}, "actor_key": {"$in": keys},
            "session_id": session_id, "lifecycle": "active",
        }).to_list(length=100)
    by_id = {item["asset_id"]: item for item in docs}
    return [_public(by_id[value]) for value in requested if value in by_id]


async def delete_asset(actor: dict, asset_id: str, session_id: str) -> bool:
    keys = _owner_keys(actor)
    collection = await _collection()
    now = _now()
    if collection is None:
        doc = _mem_assets.get(asset_id)
        if (
            not doc
            or doc.get("actor_key") not in keys
            or doc.get("session_id") != session_id
        ):
            return False
        doc.update(lifecycle="deleted", updated_at=now)
        return True
    result = await collection.update_one(
        {
            "_id": asset_id, "actor_key": {"$in": keys},
            "session_id": session_id, "lifecycle": "active",
        },
        {"$set": {"lifecycle": "deleted", "updated_at": now}},
    )
    return result.modified_count == 1
