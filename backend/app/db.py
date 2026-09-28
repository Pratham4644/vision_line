import logging

from pymongo import AsyncMongoClient, ASCENDING, IndexModel
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import PyMongoError

from backend.app.config import settings

LOGGER = logging.getLogger("camera.db")


class DatabaseConnectionError(Exception):
    """Raised when the database cannot be reached and fail-closed behavior triggers."""
    pass


class DatabaseIndexConflictError(Exception):
    """Raised when an existing MongoDB index conflicts with the desired schema."""
    pass


class Database:
    def __init__(self) -> None:
        self.client: AsyncMongoClient | None = None
        self.db: AsyncDatabase | None = None
        self._connected: bool = False

    async def connect(
        self,
        uri: str | None = None,
        database_name: str | None = None,
    ) -> bool:
        """Initialize AsyncMongoClient and verify connectivity with a ping."""
        target_uri = uri or settings.mongodb_uri
        target_db = database_name or settings.mongodb_database

        try:
            LOGGER.info(
                "Connecting to MongoDB database '%s' via native AsyncMongoClient...",
                target_db,
            )

            self.client = AsyncMongoClient(
    target_uri,
                serverSelectionTimeoutMS=10000,
                connectTimeoutMS=10000,
                socketTimeoutMS=10000,
                maxPoolSize=25,
                minPoolSize=0,
            )

            self.db = self.client[target_db]

            await self.client.admin.command("ping")

            self._connected = True
            LOGGER.info("MongoDB connected successfully.")
            return True

        except Exception as exc:
            self._connected = False
            LOGGER.error(
                "Failed to connect to MongoDB (%s). Failing closed.",
                exc,
            )
            return False

    async def close(self) -> None:
        """Close the MongoDB client connection cleanly."""
        if self.client is not None:
            await self.client.close()
            self.client = None
            self.db = None
            self._connected = False
            LOGGER.info("MongoDB client disconnected.")

    async def ping(self) -> bool:
        """Ping MongoDB to verify live connectivity."""
        if not self._connected or self.client is None:
            return False

        try:
            await self.client.admin.command("ping")
            return True
        except Exception:
            return False

    @property
    def is_connected(self) -> bool:
        return self._connected and self.db is not None

    def _get_collection(self, name: str) -> AsyncCollection:
        if not self._connected or self.db is None:
            raise DatabaseConnectionError(
                "Database is currently unavailable. Failing closed."
            )

        return self.db[name]

    @property
    def organizations(self) -> AsyncCollection:
        return self._get_collection("organizations")

    @property
    def users(self) -> AsyncCollection:
        return self._get_collection("users")

    @property
    def sites(self) -> AsyncCollection:
        return self._get_collection("sites")

    @property
    def cameras(self) -> AsyncCollection:
        return self._get_collection("cameras")

    @property
    def recordings(self) -> AsyncCollection:
        return self._get_collection("recordings")

    @property
    def audit_logs(self) -> AsyncCollection:
        return self._get_collection("audit_logs")

    @staticmethod
    def _freeze(value):
        """
        Convert nested MongoDB index option structures into a comparable,
        hashable representation.
        """
        if isinstance(value, dict):
            return tuple(
                sorted(
                    (key, Database._freeze(val))
                    for key, val in value.items()
                )
            )

        if isinstance(value, (list, tuple)):
            return tuple(Database._freeze(item) for item in value)

        return value

    @classmethod
    def _index_signature(cls, index: dict) -> tuple:
        """
        Build an index signature that intentionally excludes the index name.

        Equivalent indexes with different MongoDB names are treated as
        the same index.
        """
        key = tuple(index.get("key", []))

        options = (
            ("unique", bool(index.get("unique", False))),
            ("sparse", bool(index.get("sparse", False))),
            (
                "partialFilterExpression",
                cls._freeze(index.get("partialFilterExpression")),
            ),
            (
                "collation",
                cls._freeze(index.get("collation")),
            ),
            (
                "expireAfterSeconds",
                index.get("expireAfterSeconds"),
            ),
            (
                "hidden",
                bool(index.get("hidden", False)),
            ),
        )

        return (
            key,
            options,
        )

    async def _ensure_collection_indexes(
        self,
        collection: AsyncCollection,
        desired_indexes: list[IndexModel],
    ) -> None:
        """
        Ensure indexes exist without treating the index name as part of
        the index identity.

        Behavior:

        - Equivalent existing index with another name:
          leave it untouched.

        - Missing index:
          create it.

        - Same key pattern but incompatible options:
          raise a clear schema conflict.
        """

        # IMPORTANT:
        # PyMongo Async list_indexes() is awaitable and returns an
        # AsyncCommandCursor.
        cursor = await collection.list_indexes()

        existing_indexes: list[dict] = []

        async for index in cursor:
            existing_indexes.append(index)

        existing_by_signature = {
            self._index_signature(index): index
            for index in existing_indexes
        }

        for index_model in desired_indexes:
            desired_document = index_model.document
            desired_signature = self._index_signature(
                desired_document
            )

            # ---------------------------------------------------------
            # Equivalent index already exists
            # ---------------------------------------------------------
            existing = existing_by_signature.get(
                desired_signature
            )

            if existing is not None:
                existing_name = existing.get("name")
                desired_name = desired_document.get("name")

                if existing_name != desired_name:
                    LOGGER.info(
                        "Equivalent index already exists on collection "
                        "'%s' as '%s'; desired name is '%s'. "
                        "Leaving existing index unchanged.",
                        collection.name,
                        existing_name,
                        desired_name,
                    )
                else:
                    LOGGER.debug(
                        "Index '%s' already exists on collection '%s'.",
                        existing_name,
                        collection.name,
                    )

                continue

            # ---------------------------------------------------------
            # Same key pattern but incompatible options
            # ---------------------------------------------------------
            desired_key = tuple(
                desired_document.get("key", [])
            )

            conflicting_indexes = [
                index
                for index in existing_indexes
                if tuple(index.get("key", [])) == desired_key
            ]

            if conflicting_indexes:
                conflict = conflicting_indexes[0]

                raise DatabaseIndexConflictError(
                    f"Index conflict on collection "
                    f"'{collection.name}': desired index "
                    f"'{desired_document.get('name')}' uses key "
                    f"pattern {desired_key}, but existing index "
                    f"'{conflict.get('name')}' has incompatible "
                    f"options. "
                    f"Existing={conflict}, "
                    f"Desired={desired_document}"
                )

            # ---------------------------------------------------------
            # Missing index
            # ---------------------------------------------------------
            created_names = await collection.create_indexes(
                [index_model]
            )

            created_name = created_names[0]

            LOGGER.info(
                "Created missing index '%s' on collection '%s'.",
                created_name,
                collection.name,
            )

            # Keep local state synchronized.
            created_document = dict(desired_document)
            created_document["name"] = created_name

            existing_indexes.append(created_document)

            existing_by_signature[
                desired_signature
            ] = created_document

    async def ensure_indexes(self) -> None:
        """
        Ensure all required database indexes exist.

        This method is idempotent and safe to execute repeatedly.
        """

        if not self.is_connected:
            raise DatabaseConnectionError(
                "Cannot create indexes: database is not connected."
            )

        index_definitions = [
            # ---------------------------------------------------------
            # Organizations
            # ---------------------------------------------------------
            (
                self.organizations,
                [
                    IndexModel(
                        [("id", ASCENDING)],
                        unique=True,
                        name="idx_org_id_unique",
                    ),
                    IndexModel(
                        [("name", ASCENDING)],
                        unique=True,
                        name="idx_org_name_unique",
                    ),
                ],
            ),

            # ---------------------------------------------------------
            # Users
            # ---------------------------------------------------------
            (
                self.users,
                [
                    IndexModel(
                        [("id", ASCENDING)],
                        unique=True,
                        name="idx_user_id_unique",
                    ),
                    IndexModel(
                        [("email", ASCENDING)],
                        unique=True,
                        name="idx_user_email_unique",
                    ),
                    IndexModel(
                        [
                            ("organization_id", ASCENDING),
                            ("role", ASCENDING),
                        ],
                        name="idx_user_org_role",
                    ),
                ],
            ),

            # ---------------------------------------------------------
            # Sites
            # ---------------------------------------------------------
            (
                self.sites,
                [
                    IndexModel(
                        [("id", ASCENDING)],
                        unique=True,
                        name="idx_site_id_unique",
                    ),
                    IndexModel(
                        [("organization_id", ASCENDING)],
                        name="idx_site_org",
                    ),
                    IndexModel(
                        [
                            ("organization_id", ASCENDING),
                            ("name", ASCENDING),
                        ],
                        unique=True,
                        name="idx_site_org_name_unique",
                    ),
                ],
            ),

           # ---------------------------------------------------------
# Cameras
# ---------------------------------------------------------
(
    self.cameras,
    [
        IndexModel(
            [("id", ASCENDING)],
            unique=True,
            name="idx_camera_id_unique",
        ),
        IndexModel(
            [("organization_id", ASCENDING)],
            name="idx_camera_org",
        ),
        IndexModel(
            [
                ("organization_id", ASCENDING),
                ("site_id", ASCENDING),
            ],
            name="idx_camera_org_site",
        ),
        IndexModel(
            [
                ("organization_id", ASCENDING),
                ("media_path", ASCENDING),
            ],
            unique=True,
            partialFilterExpression={
                "media_path": {
                    "$type": "string",
                },
            },
            name="idx_camera_org_media_path_unique",
        ),
    ],
),

            # ---------------------------------------------------------
            # Recordings
            # ---------------------------------------------------------
            (
                self.recordings,
                [
                    IndexModel(
                        [("id", ASCENDING)],
                        unique=True,
                        name="idx_recording_id_unique",
                    ),
                    IndexModel(
                        [
                            ("organization_id", ASCENDING),
                            ("camera_id", ASCENDING),
                            ("start_time", ASCENDING),
                        ],
                        name="idx_rec_org_cam_time",
                    ),
                    IndexModel(
                        [
                            ("status", ASCENDING),
                            ("start_time", ASCENDING),
                        ],
                        name="idx_rec_status_time",
                    ),
                ],
            ),

            # ---------------------------------------------------------
            # Audit logs
            # ---------------------------------------------------------
            (
                self.audit_logs,
                [
                    IndexModel(
                        [
                            ("organization_id", ASCENDING),
                            ("timestamp", ASCENDING),
                        ],
                        name="idx_audit_org_time",
                    ),
                    IndexModel(
                        [("timestamp", ASCENDING)],
                        name="idx_audit_time",
                    ),
                ],
            ),
        ]

        try:
            for collection, indexes in index_definitions:
                await self._ensure_collection_indexes(
                    collection,
                    indexes,
                )

            LOGGER.info(
                "Database indexes ensured successfully."
            )

        except DatabaseIndexConflictError:
            LOGGER.exception(
                "Database index schema conflict detected."
            )
            raise

        except PyMongoError as err:
            LOGGER.exception(
                "Failed to create database indexes: %s",
                err,
            )
            raise

db = Database()