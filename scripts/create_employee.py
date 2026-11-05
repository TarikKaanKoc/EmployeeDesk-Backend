"""Set (or reset) the local password of a synthetic employee.

pdm run set-password E1001 'Some-Password-1'
pdm run set-password --all 'Synthetic-Pass-1'    # every identity without one
"""

import argparse
import asyncio
import sys
from pathlib import Path

from loguru import logger
from sqlalchemy import select, update

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.app.database.connections import close_engine, get_session_factory  # noqa: E402
from src.app.database.models import Identity  # noqa: E402
from src.app.modules.auth.security import hash_password  # noqa: E402


async def main(employee_id: str | None, password: str, everyone: bool) -> None:
    hashed = await hash_password(password)
    async with get_session_factory()() as session:
        async with session.begin():
            if everyone:
                result = await session.execute(
                    update(Identity)
                    .where(Identity.password_hash.is_(None))
                    .values(password_hash=hashed)
                )
                logger.info(f"Password set for {result.rowcount} identities")
            else:
                identity = (
                    await session.execute(
                        select(Identity).where(Identity.employee_id == employee_id)
                    )
                ).scalar_one_or_none()
                if identity is None:
                    raise SystemExit(f"No identity for {employee_id}")
                identity.password_hash = hashed
                logger.info(f"Password set for {employee_id}")
    await close_engine()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("employee_id", nargs="?")
    ap.add_argument("password")
    ap.add_argument(
        "--all", action="store_true", help="every identity that has no password yet"
    )
    a = ap.parse_args()
    if not a.all and not a.employee_id:
        ap.error("employee_id or --all is required")
    asyncio.run(main(a.employee_id, a.password, a.all))
