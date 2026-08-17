"""Local accounts and revocable browser sessions for Advertising Agent.

Raw passwords and account-session tokens exist only for the duration of the
request that creates/verifies them. MongoDB stores Argon2id password hashes and
SHA-256 account-token digests; public helpers remove both credential fields.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import re
import secrets
import time
import uuid

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from config import config


_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_PASSWORD_HASHER = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
    type=Type.ID,
)
_DUMMY_PASSWORD_HASH = _PASSWORD_HASHER.hash("not-a-real-account-password")

_mem_users: dict[str, dict] = {}
_mem_auth_identities: dict[tuple[str, str], dict] = {}
_mem_account_sessions: dict[str, dict] = {}
_mem_account_session_by_hash: dict[str, str] = {}
_mem_auth_rate_limits: dict[str, dict] = {}
_mem_auth_audit_events: list[dict] = []


class AccountConflict(Exception):
    """A normalized local identity already exists."""


class InvalidCredentials(Exception):
    """Authentication failed without disclosing which credential was wrong."""


class AccountDisabled(Exception):
    """An account exists but is not allowed to authenticate."""


class AuthRateLimited(Exception):
    """An authentication rate-limit bucket is exhausted."""


class ValidationError(ValueError):
    """Account input failed local validation."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _public(doc: dict | None) -> dict | None:
    if doc is None:
        return None
    value = deepcopy(doc)
    value.pop("_id", None)
    value.pop("password_hash", None)
    value.pop("token_hash", None)
    return value


def normalize_email(email: str) -> str:
    normalized = (email or "").strip().casefold()
    if not normalized or len(normalized) > 254 or not _EMAIL_RE.fullmatch(normalized):
        raise ValidationError("email is invalid")
    local, _, domain = normalized.partition("@")
    if not local or len(local) > 64 or not domain or ".." in normalized:
        raise ValidationError("email is invalid")
    return normalized


def normalize_display_name(display_name: str) -> str:
    normalized = " ".join((display_name or "").split())
    if not 1 <= len(normalized) <= 80:
        raise ValidationError("display_name must contain 1 to 80 characters")
    if any(ord(char) < 32 for char in normalized):
        raise ValidationError("display_name contains invalid characters")
    return normalized


def validate_password(password: str) -> str:
    if not isinstance(password, str) or not 10 <= len(password) <= 128:
        raise ValidationError("password must contain 10 to 128 characters")
    return password


def hash_password(password: str) -> str:
    return _PASSWORD_HASHER.hash(validate_password(password))


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return bool(_PASSWORD_HASHER.verify(password_hash, password))
    except (InvalidHashError, VerificationError, VerifyMismatchError, TypeError):
        return False


async def _collections() -> dict[str, object] | None:
    from session import _ensure_mongo

    if not await _ensure_mongo():
        return None
    import session as session_store

    db = session_store._client[config.MONGODB_DB]
    return {
        "users": db["users"],
        "identities": db["auth_identities"],
        "sessions": db["account_sessions"],
        "limits": db["auth_rate_limits"],
        "audit": db["auth_audit_events"],
    }


async def ensure_account_indexes() -> None:
    """Create additive account/identity indexes; safe to call on every startup."""
    collections = await _collections()
    if collections is None:
        return
    await collections["users"].create_index("user_id", unique=True, name="user_id_unique")
    await collections["identities"].create_index(
        [("provider", 1), ("provider_subject", 1)],
        unique=True,
        name="provider_subject_unique",
    )
    await collections["identities"].create_index("user_id", name="identity_user_id")
    await collections["sessions"].create_index(
        "token_hash", unique=True, name="account_token_hash_unique"
    )
    await collections["sessions"].create_index("user_id", name="account_session_user")
    await collections["sessions"].create_index(
        "expires_at", expireAfterSeconds=0, name="account_session_expiry_ttl"
    )
    await collections["limits"].create_index(
        "expires_at", expireAfterSeconds=0, name="auth_rate_limit_expiry_ttl"
    )
    await collections["audit"].create_index(
        [("user_id", 1), ("created_at", -1)], name="auth_audit_user_time"
    )


async def _audit(event: str, *, user_id: str | None = None, **data) -> None:
    doc = {
        "event": event,
        "user_id": user_id,
        "created_at": _now(),
        **{key: value for key, value in data.items() if value is not None},
    }
    collections = await _collections()
    if collections is not None:
        await collections["audit"].insert_one(doc)
    else:
        _mem_auth_audit_events.append(doc)


def _rate_key(kind: str, scope: str, value: str, bucket: int) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return f"{kind}:{scope}:{digest}:{bucket}"


async def check_auth_rate_limit(kind: str, *, client_ip: str, email: str) -> None:
    """Apply process-independent per-IP and normalized-account rate limits."""
    if kind not in {"register", "login"}:
        raise ValueError("unsupported auth rate-limit kind")
    try:
        normalized = normalize_email(email)
    except ValidationError:
        # Invalid account keys still consume a bucket and receive the same
        # login behavior; only a one-way digest is persisted below.
        normalized = f"invalid:{(email or '').strip().casefold()[:254]}"
    window = max(60, int(config.AUTH_RATE_LIMIT_WINDOW_SECONDS))
    bucket = int(time.time()) // window
    expires_at = datetime.fromtimestamp((bucket + 2) * window, timezone.utc)
    if kind == "register":
        limits = {
            "ip": max(1, int(config.AUTH_REGISTER_IP_LIMIT)),
            "account": max(1, int(config.AUTH_REGISTER_ACCOUNT_LIMIT)),
        }
    else:
        limits = {
            "ip": max(1, int(config.AUTH_LOGIN_IP_LIMIT)),
            "account": max(1, int(config.AUTH_LOGIN_ACCOUNT_LIMIT)),
        }
    values = {"ip": client_ip or "unknown", "account": normalized}
    collections = await _collections()
    for scope, limit in limits.items():
        key = _rate_key(kind, scope, values[scope], bucket)
        if collections is not None:
            doc = await collections["limits"].find_one_and_update(
                {"_id": key},
                {
                    "$inc": {"count": 1},
                    "$setOnInsert": {
                        "kind": kind,
                        "scope": scope,
                        "expires_at": expires_at,
                    },
                },
                upsert=True,
                return_document=ReturnDocument.AFTER,
            )
        else:
            doc = _mem_auth_rate_limits.setdefault(
                key,
                {"_id": key, "kind": kind, "scope": scope, "count": 0,
                 "expires_at": expires_at},
            )
            doc["count"] += 1
        if int(doc.get("count", 0)) > limit:
            raise AuthRateLimited("too many authentication attempts")


async def _find_local_identity(email_normalized: str) -> dict | None:
    return await _find_provider_identity("local", email_normalized)


async def _find_provider_identity(provider: str, provider_subject: str) -> dict | None:
    collections = await _collections()
    if collections is not None:
        return await collections["identities"].find_one({
            "provider": provider, "provider_subject": provider_subject,
        })
    return _mem_auth_identities.get((provider, provider_subject))


async def _find_provider_identity_for_user(provider: str, user_id: str) -> dict | None:
    """Return a provider identity already attached to one internal account."""
    collections = await _collections()
    if collections is not None:
        return await collections["identities"].find_one({
            "provider": provider, "user_id": user_id,
        })
    return next(
        (
            identity for identity in _mem_auth_identities.values()
            if identity.get("provider") == provider
            and identity.get("user_id") == user_id
        ),
        None,
    )


async def _find_user(user_id: str) -> dict | None:
    collections = await _collections()
    if collections is not None:
        return await collections["users"].find_one({"_id": user_id})
    return _mem_users.get(user_id)


async def create_local_account(email: str, password: str, display_name: str) -> dict:
    email_normalized = normalize_email(email)
    clean_name = normalize_display_name(display_name)
    password_hash = hash_password(password)
    now = _now()
    user_id = f"usr_{uuid.uuid4().hex}"
    identity_id = f"aid_{uuid.uuid4().hex}"
    user = {
        "_id": user_id,
        "user_id": user_id,
        "display_name": clean_name,
        "status": "active",
        "created_at": now,
        "updated_at": now,
        "last_seen_at": now,
    }
    identity = {
        "_id": identity_id,
        "identity_id": identity_id,
        "user_id": user_id,
        "provider": "local",
        "provider_subject": email_normalized,
        "email_normalized": email_normalized,
        "email_verified": False,
        "password_hash": password_hash,
        "created_at": now,
        "updated_at": now,
    }
    collections = await _collections()
    if collections is not None:
        await collections["users"].insert_one(user)
        try:
            await collections["identities"].insert_one(identity)
        except DuplicateKeyError as exc:
            await collections["users"].delete_one({"_id": user_id})
            raise AccountConflict("local account already exists") from exc
    else:
        key = ("local", email_normalized)
        if key in _mem_auth_identities:
            raise AccountConflict("local account already exists")
        _mem_users[user_id] = user
        _mem_auth_identities[key] = identity
    await _audit("account_registered", user_id=user_id, provider="local")
    return public_user(user, identity)


def public_user(user: dict, identity: dict | list[dict] | None = None) -> dict:
    identities = identity if isinstance(identity, list) else ([identity] if identity else [])
    local = next((item for item in identities if item.get("provider") == "local"), None)
    zalo = next((item for item in identities if item.get("provider") == "zalo"), None)
    return {
        "user_id": user["user_id"],
        "display_name": user["display_name"],
        "email": (local or {}).get("email_normalized"),
        "email_verified": bool((local or {}).get("email_verified", False)),
        "avatar_url": (zalo or {}).get("avatar_url"),
        "providers": sorted({item.get("provider") for item in identities if item.get("provider")}),
        "status": user.get("status", "active"),
    }


def _normalize_provider_subject(value: str) -> str:
    normalized = (value or "").strip()
    if not 1 <= len(normalized) <= 200 or any(ord(char) < 32 for char in normalized):
        raise ValidationError("provider subject is invalid")
    return normalized


def _safe_avatar_url(value: str | None) -> str | None:
    url = (value or "").strip()
    if not url:
        return None
    if len(url) > 1000 or not url.startswith("https://"):
        return None
    return url


async def authenticate_zalo_account(
    provider_subject: str,
    display_name: str,
    *,
    avatar_url: str | None = None,
    link_user_id: str | None = None,
) -> dict:
    """Find/create a Zalo account or explicitly attach Zalo to an active user.

    The Zalo access token is deliberately not accepted by this storage layer and
    therefore cannot be persisted accidentally.  A subject already attached to
    another user is never merged by name, email, or any browser-provided owner ID.
    """
    subject = _normalize_provider_subject(provider_subject)
    clean_name = normalize_display_name(display_name or "Zalo user")
    clean_avatar = _safe_avatar_url(avatar_url)
    now = _now()
    existing = await _find_provider_identity("zalo", subject)
    if existing:
        if link_user_id and existing.get("user_id") != link_user_id:
            raise AccountConflict("zalo identity already belongs to another account")
        user = await _find_user(existing.get("user_id", ""))
        if not user or user.get("status") != "active":
            raise AccountDisabled("account is disabled")
        updates = {
            "profile_name": clean_name,
            "avatar_url": clean_avatar,
            "updated_at": now,
        }
        collections = await _collections()
        if collections is not None:
            await collections["identities"].update_one(
                {"_id": existing["_id"]}, {"$set": updates}
            )
            await collections["users"].update_one(
                {"_id": user["_id"]}, {"$set": {"last_seen_at": now, "updated_at": now}}
            )
        else:
            existing.update(updates)
            user["last_seen_at"] = now
            user["updated_at"] = now
        identities = await _find_identities_for_user(user["user_id"])
        await _audit("account_login_verified", user_id=user["user_id"], provider="zalo")
        return public_user(user, identities)

    if link_user_id:
        user = await _find_user(link_user_id)
        if not user or user.get("status") != "active":
            raise AccountDisabled("account is disabled")
        user_id = user["user_id"]
    else:
        user_id = f"usr_{uuid.uuid4().hex}"
        user = {
            "_id": user_id,
            "user_id": user_id,
            "display_name": clean_name,
            "status": "active",
            "created_at": now,
            "updated_at": now,
            "last_seen_at": now,
        }

    identity_id = f"aid_{uuid.uuid4().hex}"
    identity = {
        "_id": identity_id,
        "identity_id": identity_id,
        "user_id": user_id,
        "provider": "zalo",
        "provider_subject": subject,
        "profile_name": clean_name,
        "avatar_url": clean_avatar,
        "created_at": now,
        "updated_at": now,
    }
    collections = await _collections()
    if collections is not None:
        if not link_user_id:
            await collections["users"].insert_one(user)
        try:
            await collections["identities"].insert_one(identity)
        except DuplicateKeyError as exc:
            if not link_user_id:
                await collections["users"].delete_one({"_id": user_id})
            raise AccountConflict("zalo identity already belongs to an account") from exc
    else:
        key = ("zalo", subject)
        if key in _mem_auth_identities:
            raise AccountConflict("zalo identity already belongs to an account")
        if not link_user_id:
            _mem_users[user_id] = user
        _mem_auth_identities[key] = identity
    event = "account_identity_linked" if link_user_id else "account_registered"
    await _audit(event, user_id=user_id, provider="zalo")
    return public_user(user, await _find_identities_for_user(user_id))


async def authenticate_local_account(email: str, password: str) -> dict:
    email_normalized = normalize_email(email)
    if not isinstance(password, str) or len(password) > 128:
        password = ""
    identity = await _find_local_identity(email_normalized)
    candidate_hash = (identity or {}).get("password_hash") or _DUMMY_PASSWORD_HASH
    valid = verify_password(candidate_hash, password)
    user = await _find_user((identity or {}).get("user_id", "")) if identity else None
    if not identity or not user or not valid:
        raise InvalidCredentials("invalid email or password")
    if user.get("status") != "active":
        raise AccountDisabled("account is disabled")
    now = _now()
    collections = await _collections()
    if collections is not None:
        await collections["users"].update_one(
            {"_id": user["_id"]}, {"$set": {"last_seen_at": now, "updated_at": now}}
        )
        if _PASSWORD_HASHER.check_needs_rehash(identity["password_hash"]):
            await collections["identities"].update_one(
                {"_id": identity["_id"]},
                {"$set": {"password_hash": hash_password(password), "updated_at": now}},
            )
    else:
        user["last_seen_at"] = now
        user["updated_at"] = now
        if _PASSWORD_HASHER.check_needs_rehash(identity["password_hash"]):
            identity["password_hash"] = hash_password(password)
            identity["updated_at"] = now
    await _audit("account_login_verified", user_id=user["user_id"], provider="local")
    return public_user(user, identity)


async def create_account_session(user_id: str, *, user_agent_label: str = "") -> dict:
    raw_token = f"aa_acct_{secrets.token_urlsafe(48)}"
    token_hash = _token_hash(raw_token)
    session_id = f"ase_{uuid.uuid4().hex}"
    now = _now()
    expires_at = now + timedelta(days=max(1, int(config.ACCOUNT_SESSION_MAX_AGE_DAYS)))
    doc = {
        "_id": session_id,
        "session_id": session_id,
        "user_id": user_id,
        "token_hash": token_hash,
        "created_at": now,
        "last_seen_at": now,
        "expires_at": expires_at,
        "revoked_at": None,
        "user_agent_label": " ".join((user_agent_label or "").split())[:120],
    }
    collections = await _collections()
    if collections is not None:
        await collections["sessions"].insert_one(doc)
    else:
        _mem_account_sessions[session_id] = doc
        _mem_account_session_by_hash[token_hash] = session_id
    await _audit("account_session_created", user_id=user_id, session_id=session_id)
    return {**_public(doc), "token": raw_token}


async def require_account_session(token: str | None) -> dict:
    supplied = (token or "").strip()
    if not supplied:
        raise PermissionError("account session is required")
    digest = _token_hash(supplied)
    now = _now()
    collections = await _collections()
    if collections is not None:
        session = await collections["sessions"].find_one({
            "token_hash": digest,
            "revoked_at": None,
            "expires_at": {"$gt": now},
        })
    else:
        session = _mem_account_sessions.get(_mem_account_session_by_hash.get(digest, ""))
        if session and (session.get("revoked_at") or session.get("expires_at") <= now):
            session = None
    if not session:
        raise PermissionError("account session is invalid or expired")
    user = await _find_user(session["user_id"])
    if not user or user.get("status") != "active":
        raise PermissionError("account session is invalid or expired")
    identities = await _find_identities_for_user(user["user_id"])
    if collections is not None:
        await collections["sessions"].update_one(
            {"_id": session["_id"]}, {"$set": {"last_seen_at": now}}
        )
    else:
        session["last_seen_at"] = now
    return {
        "session": _public(session),
        "user": public_user(user, identities),
    }


async def _find_identities_for_user(user_id: str) -> list[dict]:
    collections = await _collections()
    if collections is not None:
        return await collections["identities"].find({"user_id": user_id}).to_list(length=20)
    return [
        doc for doc in _mem_auth_identities.values()
        if doc.get("user_id") == user_id
    ]


async def revoke_account_session(user_id: str, session_id: str) -> bool:
    now = _now()
    collections = await _collections()
    if collections is not None:
        result = await collections["sessions"].update_one(
            {"_id": session_id, "user_id": user_id, "revoked_at": None},
            {"$set": {"revoked_at": now}},
        )
        revoked = result.modified_count == 1
    else:
        session = _mem_account_sessions.get(session_id)
        revoked = bool(session and session.get("user_id") == user_id
                       and session.get("revoked_at") is None)
        if revoked:
            session["revoked_at"] = now
    if revoked:
        await _audit("account_session_revoked", user_id=user_id, session_id=session_id)
    return revoked


async def list_account_sessions(user_id: str, *, current_session_id: str) -> list[dict]:
    now = _now()
    collections = await _collections()
    if collections is not None:
        docs = await collections["sessions"].find({
            "user_id": user_id, "revoked_at": None, "expires_at": {"$gt": now},
        }).sort("last_seen_at", -1).to_list(length=100)
    else:
        docs = [
            doc for doc in _mem_account_sessions.values()
            if doc.get("user_id") == user_id and not doc.get("revoked_at")
            and doc.get("expires_at") > now
        ]
        docs.sort(key=lambda item: item.get("last_seen_at") or item["created_at"], reverse=True)
    return [
        {**_public(doc), "current": doc.get("session_id") == current_session_id}
        for doc in docs
    ]


async def get_account_storage_for_test() -> dict:
    """Focused tests only: inspect stored hashes without exposing them via HTTP."""
    collections = await _collections()
    if collections is not None:
        return {
            "users": await collections["users"].find({}).to_list(length=None),
            "identities": await collections["identities"].find({}).to_list(length=None),
            "sessions": await collections["sessions"].find({}).to_list(length=None),
        }
    return {
        "users": list(_mem_users.values()),
        "identities": list(_mem_auth_identities.values()),
        "sessions": list(_mem_account_sessions.values()),
    }
