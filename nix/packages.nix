{ inputs, ... }:

{
  perSystem = { pkgs, self', ... }: {
    packages = {
      backend = pkgs.python312Packages.buildPythonApplication {
        pname = "libix";
        version = "0.1.0";
        pyproject = true;

        src = ../backend;

        build-system = [ pkgs.python312Packages.setuptools ];

        dependencies = with pkgs.python312Packages; [
          fastapi
          uvicorn
          httpx
          pyyaml
          sqlalchemy
          python-jose
          passlib
          bcrypt
          python-multipart
          transmission-rpc
          aiosqlite
        ];

        doCheck = false;

        meta = {
          description = "Libix audiobook management backend";
          mainProgram = "libix";
        };
      };

      frontend = pkgs.buildNpmPackage {
        pname = "libix-frontend";
        version = "0.1.0";
        src = ../frontend;

        npmDepsHash = "sha256-cwuyYMuAQ1X6vcWiGXySdUwfizKE2bqLRWYl8QCgFoQ=";

        installPhase = ''
          runHook preInstall
          cp -r dist $out
          runHook postInstall
        '';

        meta = {
          description = "Libix audiobook management frontend";
        };
      };

      default = pkgs.stdenv.mkDerivation {
        pname = "libix";
        version = "0.1.0";

        dontUnpack = true;

        installPhase = ''
          mkdir -p $out/bin $out/share/libix/static

          # Copy backend
          cp -r ${self'.packages.backend}/lib $out/lib
          cp -r ${self'.packages.backend}/bin/* $out/bin/

          # Copy frontend static files
          cp -r ${self'.packages.frontend}/* $out/share/libix/static/

          # Create wrapper script
          cat > $out/bin/libix-wrapped <<'WRAPPER'
          #!/usr/bin/env bash
          export LIBIX_STATIC_DIR="$(dirname "$(dirname "$(readlink -f "$0")")")/share/libix/static"
          exec "$(dirname "$0")/libix" "$@"
          WRAPPER
          chmod +x $out/bin/libix-wrapped
        '';

        meta = {
          description = "Libix - Self-hosted audiobook management application";
          mainProgram = "libix";
        };
      };
    };
  };
}
