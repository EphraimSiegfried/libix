"""Transmission RPC client."""

from urllib.parse import urlparse

from transmission_rpc import Client as TransmissionRPCClient
from transmission_rpc.error import TransmissionError

from ..config import get_config


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
            path = parsed.path or "/transmission/rpc"

            self._client = TransmissionRPCClient(
                host=host,
                port=port,
                path=path,
                username=self.username,
                password=self.password,
            )
        return self._client

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
        torrent = client.add_torrent(
            url_or_magnet,
            download_dir=download_dir or self.download_dir,
            paused=paused,
        )
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
        client = self._get_client()
        try:
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
        except TransmissionError:
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
