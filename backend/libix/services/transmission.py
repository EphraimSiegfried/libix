"""Transmission RPC client."""

import base64
import logging
from urllib.parse import urlparse

import httpx
from transmission_rpc import Client as TransmissionRPCClient
from transmission_rpc.error import TransmissionError

from ..config import get_config

logger = logging.getLogger(__name__)


class TransmissionClient:
    """Client for interacting with Transmission via RPC."""

    def __init__(self) -> None:
        config = get_config()
        self.url = config.transmission.url
        self.username = config.transmission.username
        self.password = config.transmission.get_password()
        self.download_dir = config.transmission.download_dir
        self._client: TransmissionRPCClient | None = None

    def _get_client(self) -> TransmissionRPCClient:
        """Get or create a Transmission RPC client."""
        if self._client is None:
            parsed = urlparse(self.url)
            host = parsed.hostname or "localhost"
            port = parsed.port or 9091
            # transmission-rpc expects path without trailing slash
            # and handles /rpc suffix internally in some versions
            path = parsed.path.rstrip("/") if parsed.path else "/transmission/rpc"

            self._client = TransmissionRPCClient(
                host=host,
                port=port,
                path=path,
                username=self.username,
                password=self.password,
            )
        return self._client

    def _download_torrent_file(self, url: str) -> str | None:
        """Download a torrent file and return base64-encoded content.

        Args:
            url: URL to the torrent file.

        Returns:
            Base64-encoded torrent file content, or None if redirected to magnet.
        """
        # Don't follow redirects automatically - we need to check for magnet redirects
        with httpx.Client(follow_redirects=False, timeout=30.0) as http_client:
            response = http_client.get(url)

            # Handle redirects manually to catch magnet links
            redirect_count = 0
            while response.is_redirect and redirect_count < 10:
                redirect_count += 1
                location = response.headers.get("location", "")

                # Check if redirecting to a magnet link
                if location.lower().startswith("magnet:"):
                    return location  # Return the magnet link itself

                # Follow the redirect
                response = http_client.get(location)

            response.raise_for_status()
            return base64.b64encode(response.content).decode("ascii")

    def add_torrent(
        self,
        url_or_magnet: str,
        download_dir: str | None = None,
        paused: bool = False,
    ) -> dict:
        """Add a torrent to Transmission.

        Args:
            url_or_magnet: Torrent URL or magnet link.
            download_dir: Optional download directory override.
            paused: Whether to add the torrent paused.

        Returns:
            Dictionary with torrent info including 'id'.
        """
        client = self._get_client()

        url_or_magnet = url_or_magnet.strip()
        url_lower = url_or_magnet.lower()

        logger.info(f"add_torrent called with URL: {url_or_magnet[:100]}...")
        logger.info(f"URL starts with magnet: {url_lower.startswith('magnet:')}")

        # Detect if it's a magnet link (handle both magnet: and magnet:// formats, case-insensitive)
        is_magnet = url_lower.startswith("magnet:")

        if is_magnet:
            # Normalize magnet:// to magnet:? if needed (some indexers use wrong format)
            if url_lower.startswith("magnet://"):
                url_or_magnet = "magnet:?" + url_or_magnet[9:]
            # Magnet links go directly to Transmission
            torrent = client.add_torrent(
                url_or_magnet,
                download_dir=download_dir or self.download_dir,
                paused=paused,
            )
        elif url_lower.startswith("http://") or url_lower.startswith("https://"):
            # Download torrent file (may return magnet link if Prowlarr redirects)
            torrent_data = self._download_torrent_file(url_or_magnet)

            # Check if we got a magnet link back (from redirect)
            if torrent_data and torrent_data.lower().startswith("magnet:"):
                # Normalize magnet:// to magnet:? if needed
                if torrent_data.lower().startswith("magnet://"):
                    torrent_data = "magnet:?" + torrent_data[9:]
                torrent = client.add_torrent(
                    torrent_data,
                    download_dir=download_dir or self.download_dir,
                    paused=paused,
                )
            else:
                # It's base64-encoded torrent file data
                torrent = client.add_torrent(
                    torrent_data,
                    download_dir=download_dir or self.download_dir,
                    paused=paused,
                )
        else:
            raise ValueError(f"Unsupported URL format: {url_or_magnet[:50]}")

        return {
            "id": torrent.id,
            "name": torrent.name,
            "hash_string": torrent.hashString,
        }

    def get_torrent(self, torrent_id: int) -> dict | None:
        """Get torrent status by ID.

        Args:
            torrent_id: Transmission torrent ID.

        Returns:
            Torrent info dict or None if not found.
        """
        try:
            client = self._get_client()
            torrents = client.get_torrents(ids=[torrent_id])
            if not torrents:
                return None
            t = torrents[0]
            return {
                "id": t.id,
                "name": t.name,
                "status": t.status,
                "progress": int(t.progress),
                "size_bytes": t.total_size,
                "download_dir": t.download_dir,
                "error": t.error,
                "error_string": t.error_string,
            }
        except (TransmissionError, Exception):
            return None

    def get_all_torrents(self) -> list[dict]:
        """Get all torrents.

        Returns:
            List of torrent info dicts.
        """
        client = self._get_client()
        torrents = client.get_torrents()
        return [
            {
                "id": t.id,
                "name": t.name,
                "status": t.status,
                "progress": int(t.progress),
                "size_bytes": t.total_size,
                "download_dir": t.download_dir,
            }
            for t in torrents
        ]

    def remove_torrent(self, torrent_id: int, delete_data: bool = False) -> bool:
        """Remove a torrent.

        Args:
            torrent_id: Transmission torrent ID.
            delete_data: Whether to delete downloaded data.

        Returns:
            True if removed successfully.
        """
        client = self._get_client()
        try:
            client.remove_torrent(torrent_id, delete_data=delete_data)
            return True
        except TransmissionError:
            return False

    def get_torrent_files(self, torrent_id: int) -> dict | None:
        """Get torrent files and download location.

        Args:
            torrent_id: Transmission torrent ID.

        Returns:
            Dict with download_dir, name, and files list, or None if not found.
        """
        try:
            client = self._get_client()
            torrents = client.get_torrents(ids=[torrent_id])
            if not torrents:
                return None
            t = torrents[0]
            return {
                "download_dir": t.download_dir,
                "name": t.name,
                "files": [
                    {
                        "name": f.name,
                        "size": f.size,
                        "completed": f.completed,
                    }
                    for f in t.files()
                ],
            }
        except (TransmissionError, Exception):
            return None

    def test_connection(self) -> tuple[bool, str, dict | None]:
        """Test connection to Transmission.

        Returns:
            Tuple of (success, message, details).
        """
        try:
            client = self._get_client()
            session = client.get_session()
            return (
                True,
                f"Connected successfully. Version: {session.version}",
                {
                    "version": session.version,
                    "download_dir": session.download_dir,
                },
            )
        except TransmissionError as e:
            return (False, f"Transmission error: {str(e)}", None)
        except Exception as e:
            return (False, f"Connection failed: {str(e)}", None)
