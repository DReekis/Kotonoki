import re
from typing import Optional, Tuple
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from sqlalchemy import func
from app.extensions import db
from app.models import PenName, utc_now

# Argon2id password hasher with secure parameters
_ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,  # 64 MB
    parallelism=4,
    hash_len=32
)

PEN_NAME_REGEX = re.compile(r"^[a-zA-Z0-9_\-\.]{2,30}$")

class AuthService:
    @staticmethod
    def validate_handle(handle: str) -> Tuple[bool, Optional[str]]:
        if not handle:
            return False, "Pen name cannot be empty."
        handle = handle.strip()
        if len(handle) < 2 or len(handle) > 30:
            return False, "Pen name must be between 2 and 30 characters."
        if not PEN_NAME_REGEX.match(handle):
            return False, "Pen name can only contain letters, numbers, underscores, hyphens, and periods."
        return True, None

    @staticmethod
    def validate_password(password: str) -> Tuple[bool, Optional[str]]:
        if not password:
            return False, "Password cannot be empty."
        if len(password) < 8:
            return False, "Password must be at least 8 characters long."
        if len(password) > 128:
            return False, "Password cannot exceed 128 characters."
        return True, None

    @classmethod
    def register(cls, handle: str, password: str) -> Tuple[Optional[PenName], Optional[str]]:
        handle = handle.strip()
        valid_handle, handle_err = cls.validate_handle(handle)
        if not valid_handle:
            return None, handle_err

        valid_pw, pw_err = cls.validate_password(password)
        if not valid_pw:
            return None, pw_err

        # Case-insensitive uniqueness check
        existing = db.session.execute(
            db.select(PenName).where(func.lower(PenName.handle) == handle.lower())
        ).scalar_one_or_none()

        if existing:
            return None, f"The pen name '{handle}' is already claimed. If it is yours, open your desk."

        password_hash = _ph.hash(password)
        pen_name = PenName(
            handle=handle,
            password_hash=password_hash,
            last_login_at=utc_now()
        )
        db.session.add(pen_name)
        db.session.commit()
        return pen_name, None

    @classmethod
    def authenticate(cls, handle: str, password: str) -> Tuple[Optional[PenName], Optional[str]]:
        handle = handle.strip()
        if not handle or not password:
            return None, "Pen name and password are required."

        pen_name = db.session.execute(
            db.select(PenName).where(func.lower(PenName.handle) == handle.lower())
        ).scalar_one_or_none()

        if not pen_name:
            return None, "Invalid pen name or password."

        try:
            _ph.verify(pen_name.password_hash, password)
            # Rehash if parameters updated
            if _ph.check_needs_rehash(pen_name.password_hash):
                pen_name.password_hash = _ph.hash(password)
            
            pen_name.last_login_at = utc_now()
            db.session.commit()
            return pen_name, None
        except (VerifyMismatchError, InvalidHashError):
            return None, "Invalid pen name or password."

    @classmethod
    def change_password(cls, pen_name: PenName, old_password: str, new_password: str) -> Tuple[bool, Optional[str]]:
        valid_pw, pw_err = cls.validate_password(new_password)
        if not valid_pw:
            return False, pw_err

        # Ensure instance is managed in active session
        managed_pen_name = db.session.get(PenName, pen_name.id)
        if not managed_pen_name:
            managed_pen_name = pen_name
            db.session.add(managed_pen_name)

        try:
            _ph.verify(managed_pen_name.password_hash, old_password)
        except (VerifyMismatchError, InvalidHashError):
            return False, "Current password does not match."

        managed_pen_name.password_hash = _ph.hash(new_password)
        db.session.commit()
        return True, None
