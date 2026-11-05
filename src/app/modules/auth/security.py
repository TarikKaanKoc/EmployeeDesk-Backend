import asyncio

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_hasher = PasswordHasher(time_cost=3, memory_cost=64 * 1024, parallelism=4)


async def hash_password(password: str) -> str:
    return await asyncio.to_thread(_hasher.hash, password)


async def verify_password(password: str, hashed: str) -> bool:
    try:
        return await asyncio.to_thread(_hasher.verify, hashed, password)
    except VerifyMismatchError, VerificationError, InvalidHashError:
        return False
