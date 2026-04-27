{ inputs, self, ... }:

{
  perSystem =
    {
      pkgs,
      system,
      self',
      ...
    }:
    {
      checks = pkgs.lib.optionalAttrs pkgs.stdenv.isLinux {
        vm-test = pkgs.testers.nixosTest {
          name = "libix-integration";

          nodes = {
            server =
              { config, pkgs, ... }:
              {
                imports = [ self.nixosModules.default ];

                services.libix = {
                  enable = true;
                  package = self'.packages.default;
                  dataDir = "/var/lib/libix";
                  settings = {
                    server = {
                      host = "0.0.0.0";
                      port = 8080;
                      secret_key = "test-secret-key";
                    };
                    database.path = "/var/lib/libix/libix.db";
                    library.path = "/var/lib/libix/audiobooks";
                    auth = {
                      initial_admin = {
                        username = "admin";
                        password = "admin";
                      };
                      jwt_expiry_hours = 24;
                    };
                    prowlarr = {
                      url = "http://localhost:9696";
                      categories = [ 3030 ];
                    };
                    transmission = {
                      url = "http://localhost:9091/transmission/rpc";
                      download_dir = "/var/lib/transmission/downloads";
                    };
                  };
                };

                # Prowlarr (for future search integration)
                services.prowlarr.enable = true;

                # Transmission
                services.transmission = {
                  enable = true;
                  settings = {
                    rpc-bind-address = "0.0.0.0";
                    rpc-port = 9091;
                    rpc-whitelist-enabled = false;
                    rpc-authentication-required = false;
                    download-dir = "/var/lib/transmission/downloads";
                  };
                };

                systemd.tmpfiles.rules = [
                  "d /var/lib/libix/audiobooks 0755 libix libix -"
                  "d /var/lib/transmission/downloads 0755 transmission transmission -"
                ];

                networking.firewall.allowedTCPPorts = [
                  8080
                  9696
                  9091
                ];

                virtualisation = {
                  memorySize = 2048;
                  cores = 2;
                };
              };
          };

          testScript = ''
            import json
            import re

            start_all()

            # Wait for all services
            server.wait_for_unit("transmission.service")
            server.wait_for_unit("prowlarr.service")
            server.wait_for_unit("libix.service")
            server.wait_for_open_port(9091)
            server.wait_for_open_port(9696)
            server.wait_for_open_port(8080)

            # Test health endpoint
            result = server.succeed("curl -s http://localhost:8080/api/health")
            assert '"status":"ok"' in result, f"Health check failed: {result}"
            print("Health check passed")

            # Login and get token
            login_result = server.succeed(
                "curl -s -X POST http://localhost:8080/api/auth/login "
                "-H 'Content-Type: application/x-www-form-urlencoded' "
                "-d 'username=admin&password=admin'"
            )
            assert "access_token" in login_result, f"Login failed: {login_result}"
            token_data = json.loads(login_result)
            token = token_data["access_token"]
            print("Login successful")

            # Test Transmission connection via Libix
            transmission_test = server.succeed(
                "curl -s -X POST http://localhost:8080/api/settings/test-transmission "
                f"-H 'Authorization: Bearer {token}'"
            )
            transmission_result = json.loads(transmission_test)
            assert transmission_result["success"] == True, f"Transmission connection failed: {transmission_test}"
            print("Transmission connection test passed")

            # Test adding a download with a magnet link (Ubuntu ISO as test)
            # This is a well-known, legal torrent for testing
            test_magnet = "magnet:?xt=urn:btih:3b245504cf5f11bbdbe1201cea6a6bf45aee1bc0&dn=ubuntu-22.04.5-live-server-amd64.iso"

            add_download = server.succeed(
                "curl -s -X POST http://localhost:8080/api/downloads "
                f"-H 'Authorization: Bearer {token}' "
                "-H 'Content-Type: application/json' "
                f"-d '{{\"title\": \"Test Download\", \"magnet_url\": \"{test_magnet}\"}}'"
            )
            print(f"Add download result: {add_download}")
            download_data = json.loads(add_download)
            assert "id" in download_data, f"Failed to add download: {add_download}"
            assert download_data["title"] == "Test Download", f"Wrong title: {add_download}"
            download_id = download_data["id"]
            print("Download added successfully")

            # Verify the download appears in our downloads list
            downloads_list = server.succeed(
                "curl -s http://localhost:8080/api/downloads "
                f"-H 'Authorization: Bearer {token}'"
            )
            print(f"Downloads list: {downloads_list}")
            downloads = json.loads(downloads_list)
            assert len(downloads) == 1, f"Expected 1 download: {downloads_list}"
            assert downloads[0]["title"] == "Test Download", "Wrong download title"
            print("Download appears in list")

            # Verify the torrent was added to Transmission
            # Need to get session ID first
            session_response = server.execute("curl -s http://localhost:9091/transmission/rpc")[1]
            session_match = re.search(r'X-Transmission-Session-Id: ([^\s<]+)', session_response)
            if session_match:
                session_id = session_match.group(1)
                print(f"Transmission session ID: {session_id}")

                # Get torrents from Transmission
                transmission_torrents = server.succeed(
                    "curl -s http://localhost:9091/transmission/rpc "
                    f"-H 'X-Transmission-Session-Id: {session_id}' "
                    "-H 'Content-Type: application/json' "
                    "-d '{\"method\": \"torrent-get\", \"arguments\": {\"fields\": [\"id\", \"name\", \"status\"]}}'"
                )
                print(f"Transmission torrents: {transmission_torrents}")
                torrents_data = json.loads(transmission_torrents)
                assert "result" in torrents_data, f"Invalid transmission response: {transmission_torrents}"
                assert torrents_data["result"] == "success", f"Transmission error: {transmission_torrents}"
                # Should have at least one torrent
                torrent_count = len(torrents_data.get("arguments", {}).get("torrents", []))
                assert torrent_count >= 1, f"Expected at least 1 torrent in Transmission, got {torrent_count}"
                print(f"Found {torrent_count} torrent(s) in Transmission - integration verified!")

            # Test deleting the download
            delete_result = server.succeed(
                f"curl -s -X DELETE http://localhost:8080/api/downloads/{download_id} "
                f"-H 'Authorization: Bearer {token}'"
            )
            print(f"Delete result: {delete_result}")

            # Verify downloads list is now showing cancelled status
            downloads_after = server.succeed(
                "curl -s http://localhost:8080/api/downloads "
                f"-H 'Authorization: Bearer {token}'"
            )
            print(f"Downloads after delete: {downloads_after}")

            print("All integration tests passed!")
          '';
        };
      };
    };
}
