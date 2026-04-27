"""Configuration loading with file-based secrets support."""

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


def read_secret_file(path: str) -> str:
    """Read a secret from a file, stripping trailing whitespace."""
    return Path(path).read_text().strip()


def resolve_secret(value: str | None, file_path: str | None) -> str | None:
    """Resolve a secret from either a direct value or file path."""
    if file_path:
        return read_secret_file(file_path)
    return value


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8080
    secret_key: str | None = None
    secret_key_file: str | None = None

    def get_secret_key(self) -> str:
        """Get the secret key from direct value or file."""
        result = resolve_secret(self.secret_key, self.secret_key_file)
        return result if result else "change-me-in-production"


class DatabaseConfig(BaseModel):
    path: str = "/var/lib/libix/libix.db"


class LibraryConfig(BaseModel):
    path: str = "/media/audiobooks"


class InitialAdminConfig(BaseModel):
    username: str = "admin"
    password: str | None = None
    password_file: str | None = None

    def get_password(self) -> str:
        """Get the admin password from direct value or file."""
        result = resolve_secret(self.password, self.password_file)
        return result if result else "admin"


class AuthConfig(BaseModel):
    initial_admin: InitialAdminConfig = Field(default_factory=InitialAdminConfig)
    jwt_expiry_hours: int = 24


class ProwlarrConfig(BaseModel):
    url: str = "http://localhost:9696"
    api_key: str | None = None
    api_key_file: str | None = None
    categories: list[int] = Field(default_factory=lambda: [3030])
    limit: int = 100

    def get_api_key(self) -> str | None:
        """Get the API key from direct value or file."""
        return resolve_secret(self.api_key, self.api_key_file)


class TransmissionConfig(BaseModel):
    url: str = "http://localhost:9091/transmission/rpc"
    username: str | None = None
    password: str | None = None
    password_file: str | None = None
    download_dir: str = "/downloads/audiobooks"

    def get_password(self) -> str | None:
        """Get the password from direct value or file."""
        return resolve_secret(self.password, self.password_file)


class Config(BaseModel):
    server: ServerConfig = Field(default_factory=ServerConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    library: LibraryConfig = Field(default_factory=LibraryConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    prowlarr: ProwlarrConfig = Field(default_factory=ProwlarrConfig)
    transmission: TransmissionConfig = Field(default_factory=TransmissionConfig)


def load_config(config_path: str | None = None) -> Config:
    """Load configuration from YAML file.

    Args:
        config_path: Path to config file. If None, searches in standard locations.

    Returns:
        Loaded configuration.
    """
    if config_path is None:
        # Check standard locations
        candidates = [
            Path("config.yaml"),
            Path("config.yml"),
            Path("/etc/libix/config.yaml"),
            Path("/etc/libix/config.yml"),
        ]
        # Also check LIBIX_CONFIG environment variable
        env_path = os.environ.get("LIBIX_CONFIG")
        if env_path:
            candidates.insert(0, Path(env_path))

        for candidate in candidates:
            if candidate.exists():
                config_path = str(candidate)
                break

    if config_path and Path(config_path).exists():
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}
        return Config.model_validate(data)

    # Return default config if no file found
    return Config()


# Global config instance
_config: Config | None = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def set_config(config: Config) -> None:
    """Set the global configuration instance."""
    global _config
    _config = config
