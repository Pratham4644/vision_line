from __future__ import annotations

from typing import Literal
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_env: Literal["development", "production", "testing"] = Field(
        default="development",
        validation_alias="APP_ENV",
    )
    app_name: str = Field(
        default="Remote Camera Streaming Platform",
        validation_alias="APP_NAME",
    )
    debug: bool = Field(
        default=False,
        validation_alias="DEBUG",
    )
    app_host: str = Field(
        default="127.0.0.1",
        validation_alias="APP_HOST",
    )
    app_port: int = Field(
        default=8000,
        validation_alias="APP_PORT",
    )

    # Database
    mongodb_uri: str = Field(
        default="mongodb://127.0.0.1:27017",
        validation_alias="MONGODB_URI",
    )
    mongodb_database: str = Field(
        default="camera_stream_platform",
        validation_alias="MONGODB_DATABASE",
    )

    # Auth
    jwt_secret: str = Field(
        default="",
        validation_alias="JWT_SECRET",
    )
    jwt_algorithm: str = Field(
        default="HS256",
        validation_alias="JWT_ALGORITHM",
    )
    access_token_expire_minutes: int = Field(
        default=720,
        validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES",
    )

    # Cookies
    cookie_name: str = Field(
        default="camera_session",
        validation_alias="COOKIE_NAME",
    )
    cookie_secure: bool = Field(
        default=False,
        validation_alias="COOKIE_SECURE",
    )
    cookie_http_only: bool = Field(
        default=True,
        validation_alias="COOKIE_HTTP_ONLY",
    )
    cookie_samesite: Literal["lax", "strict", "none"] = Field(
        default="lax",
        validation_alias="COOKIE_SAMESITE",
    )

    # Encryption
    camera_encryption_key: str = Field(
        default="",
        validation_alias="CAMERA_ENCRYPTION_KEY",
    )

    # MediaMTX
    mediamtx_host: str = Field(
        default="127.0.0.1",
        validation_alias="MEDIAMTX_HOST",
    )
    mediamtx_rtsp_port: int = Field(
        default=8554,
        validation_alias="MEDIAMTX_RTSP_PORT",
    )
    mediamtx_webrtc_port: int = Field(
        default=8889,
        validation_alias="MEDIAMTX_WEBRTC_PORT",
    )
    mediamtx_webrtc_public_url: str = Field(
        default="",
        validation_alias="MEDIAMTX_WEBRTC_PUBLIC_URL",
    )
    mediamtx_api_url: str = Field(
        default="http://127.0.0.1:9997",
        validation_alias="MEDIAMTX_API_URL",
    )
    mediamtx_publish_username: str = Field(
        default="edge-publisher",
        validation_alias="MEDIAMTX_PUBLISH_USERNAME",
    )
    mediamtx_publish_password: str = Field(
        default="",
        validation_alias="MEDIAMTX_PUBLISH_PASSWORD",
    )
    mediamtx_read_username: str = Field(
        default="webrtc_reader",
        validation_alias="MEDIAMTX_READ_USERNAME",
    )
    mediamtx_read_password: str = Field(
        default="",
        validation_alias="MEDIAMTX_READ_PASSWORD",
    )

    # Edge Gateway
    edge_gateway_id: str = Field(
        default="edge-gateway-001",
        validation_alias="EDGE_GATEWAY_ID",
    )

    edge_gateway_token: str = Field(
        default="",
        validation_alias="EDGE_GATEWAY_TOKEN",
    )
    # Recording
    recordings_dir: str = Field(
        default="recordings",
        validation_alias="RECORDINGS_DIR",
    )
    recording_segment_minutes: int = Field(
        default=60,
        validation_alias="RECORDING_SEGMENT_MINUTES",
    )
    recording_retention_hours: int = Field(
        default=2,
        validation_alias="RECORDING_RETENTION_HOURS",
    )

    # CORS
    frontend_origin: str = Field(
        default="http://localhost:5173",
        validation_alias="FRONTEND_ORIGIN",
    )

    @property
    def cors_origins(self) -> list[str]:
        return [orig.strip() for orig in self.frontend_origin.split(",") if orig.strip()]

    @model_validator(mode="after")
    def validate_production_security(self) -> Settings:
        is_prod = self.app_env == "production"

        # Check JWT Secret
        if not self.jwt_secret or self.jwt_secret.startswith("replace_") or len(self.jwt_secret) < 32:
            if is_prod:
                raise ValueError("In production, JWT_SECRET must be set and be at least 32 characters long.")
            elif not self.jwt_secret:
                object.__setattr__(self, "jwt_secret", "dev_insecure_jwt_secret_must_change_in_production_32b")

        # Check Camera Encryption Key
        if not self.camera_encryption_key or self.camera_encryption_key.startswith("replace_") or len(self.camera_encryption_key) < 16:
            if is_prod:
                raise ValueError("In production, CAMERA_ENCRYPTION_KEY must be set with a strong key.")
            elif not self.camera_encryption_key:
                object.__setattr__(self, "camera_encryption_key", "dev_camera_enc_key_32_bytes_long_ok!!")

        # In production, ensure secure cookies are forced
        if is_prod:
            object.__setattr__(self, "cookie_secure", True)
            if not self.mediamtx_publish_password:
                raise ValueError("In production, MEDIAMTX_PUBLISH_PASSWORD must be configured.")
            if not self.mediamtx_read_password:
                raise ValueError("In production, MEDIAMTX_READ_PASSWORD must be configured.")
        else:
            if not self.mediamtx_publish_password:
                object.__setattr__(self, "mediamtx_publish_password", "dev_mediamtx_pub_pwd_secure")
            if not self.mediamtx_read_password:
                object.__setattr__(self, "mediamtx_read_password", "dev_mediamtx_read_pwd_secure")

        return self


settings = Settings()
