{ config, lib, pkgs, ... }:

let
  cfg = config.services.libix;
  settingsFormat = pkgs.formats.yaml { };
  configFile = settingsFormat.generate "config.yaml" cfg.settings;
in
{
  options.services.libix = {
    enable = lib.mkEnableOption "Libix audiobook management service";

    package = lib.mkOption {
      type = lib.types.package;
      default = pkgs.libix;
      defaultText = lib.literalExpression "pkgs.libix";
      description = "The Libix package to use. Requires the libix overlay.";
    };

    user = lib.mkOption {
      type = lib.types.str;
      default = "libix";
      description = "User under which Libix runs.";
    };

    group = lib.mkOption {
      type = lib.types.str;
      default = "libix";
      description = "Group under which Libix runs.";
    };

    dataDir = lib.mkOption {
      type = lib.types.path;
      default = "/var/lib/libix";
      description = "Directory to store Libix data.";
    };

    downloadDir = lib.mkOption {
      type = lib.types.nullOr lib.types.path;
      default = null;
      description = ''
        Transmission download directory that Libix needs access to.
        Required for importing completed downloads to the library.
      '';
      example = "/var/lib/transmission/downloads";
    };

    extraGroups = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [ ];
      description = ''
        Additional groups for the libix user.
        Add "transmission" to allow access to Transmission downloads.
      '';
      example = [ "transmission" ];
    };

    settings = lib.mkOption {
      type = settingsFormat.type;
      default = { };
      description = ''
        Configuration for Libix. Will be converted to YAML.
        See config.example.yaml for available options.

        Secrets should use file paths (e.g., api_key_file instead of api_key)
        which the application will read at runtime.
      '';
      example = lib.literalExpression ''
        {
          server = {
            host = "0.0.0.0";
            port = 8080;
            secret_key_file = "/run/secrets/libix-secret-key";
          };
          database.path = "/var/lib/libix/libix.db";
          library.path = "/media/audiobooks";
          auth.initial_admin = {
            username = "admin";
            password_file = "/run/secrets/libix-admin-password";
          };
          prowlarr = {
            url = "http://localhost:9696";
            api_key_file = "/run/secrets/prowlarr-api-key";
          };
          transmission = {
            url = "http://localhost:9091/transmission/rpc";
            password_file = "/run/secrets/transmission-password";
          };
        }
      '';
    };
  };

  config = lib.mkIf cfg.enable {
    users.users.${cfg.user} = {
      isSystemUser = true;
      group = cfg.group;
      home = cfg.dataDir;
      createHome = true;
      extraGroups = cfg.extraGroups;
    };

    users.groups.${cfg.group} = { };

    systemd.services.libix = {
      description = "Libix Audiobook Management Service";
      wantedBy = [ "multi-user.target" ];
      after = [ "network.target" ];

      serviceConfig = {
        Type = "simple";
        User = cfg.user;
        Group = cfg.group;
        SupplementaryGroups = cfg.extraGroups;
        ExecStart = "${cfg.package}/bin/libix -c ${configFile}";
        Restart = "on-failure";
        RestartSec = 5;

        # Hardening
        NoNewPrivileges = true;
        PrivateTmp = true;
        CapabilityBoundingSet = "";
        SystemCallArchitectures = "native";
      };
    };
  };
}
