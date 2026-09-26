from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class Account(BaseModel):
    account_id: str
    email: str
    display_name: str
    password_hash: str
    password_salt: str
    failed_attempts: int
    last_failed_at: datetime | None


class Session(BaseModel):
    token_hash: str
    user_id: str
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None


class AccountOutcome(BaseModel):
    account: Account | None
    token: str | None
    reason: str | None
