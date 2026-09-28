#!/usr/bin/env python3
"""
Seed script to create the initial default organization and Super Admin user.

The script is idempotent:
- Creates the default organization if it does not exist.
- Creates the Super Admin if it does not exist.
- Does NOT reset an existing Super Admin's password.
- Never logs passwords or password hashes.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.app.auth import hash_password
from backend.app.config import settings
from backend.app.db import db
from backend.app.models import Organization, User, UserRole


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

LOGGER = logging.getLogger("seed")


DEFAULT_ORG_NAME = "Default Organization"
DEFAULT_ADMIN_EMAIL = "admin@platform.local"
DEFAULT_ADMIN_PASSWORD = "adminpassword123"
DEFAULT_ADMIN_NAME = "System Super Admin"


async def main() -> None:
    """Create the default organization and Super Admin if they do not exist."""

    LOGGER.info(
        "Connecting to MongoDB (%s)...",
        settings.mongodb_database,
    )

    connected = await db.connect()

    if not connected:
        LOGGER.error(
            "Could not connect to MongoDB. "
            "Verify MongoDB connectivity and configuration."
        )
        sys.exit(1)

    try:
        # ---------------------------------------------------------
        # 0. Ensure database indexes
        # ---------------------------------------------------------
        await db.ensure_indexes()

        # ---------------------------------------------------------
        # 1. Ensure Default Organization
        # ---------------------------------------------------------
        org_doc = await db.organizations.find_one(
            {"name": DEFAULT_ORG_NAME}
        )

        if not org_doc:
            org = Organization(
                name=DEFAULT_ORG_NAME,
                description=(
                    "Default root organization for remote camera surveillance"
                ),
            )

            await db.organizations.insert_one(
                org.model_dump(mode="json")
            )

            org_id = org.id

            LOGGER.info(
                "Created default organization: %s (id: %s)",
                org.name,
                org_id,
            )

        else:
            org_id = org_doc["id"]

            LOGGER.info(
                "Found existing organization: %s (id: %s)",
                org_doc["name"],
                org_id,
            )

        # ---------------------------------------------------------
        # 2. Ensure Super Admin User
        # ---------------------------------------------------------
        admin_email = DEFAULT_ADMIN_EMAIL.lower()

        admin_doc = await db.users.find_one(
            {"email": admin_email}
        )

        if not admin_doc:
            # Hash the initial password only when creating the user.
            password_hash = hash_password(DEFAULT_ADMIN_PASSWORD)

            admin_user = User(
                organization_id=org_id,
                email=admin_email,
                name=DEFAULT_ADMIN_NAME,
                password_hash=password_hash,
                role=UserRole.SUPER_ADMIN,
                is_active=True,
            )

            await db.users.insert_one(
                admin_user.model_dump(mode="json")
            )

            LOGGER.info("Created Super Admin user:")
            LOGGER.info("  Email:  %s", admin_email)
            LOGGER.info("  Role:   %s", UserRole.SUPER_ADMIN.value)
            LOGGER.info("  Org ID: %s", org_id)

            LOGGER.warning(
                "Initial Super Admin password was configured from the "
                "seed configuration. Change it before production deployment."
            )

        else:
            # -----------------------------------------------------
            # Existing user
            # -----------------------------------------------------
            LOGGER.info(
                "Super Admin already exists. "
                "No password or account changes were made."
            )

            LOGGER.info("  Email:  %s", admin_doc["email"])
            LOGGER.info(
                "  Role:   %s",
                admin_doc.get("role"),
            )
            LOGGER.info(
                "  Org ID: %s",
                admin_doc.get("organization_id"),
            )

        LOGGER.info("Seeding complete.")

    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())