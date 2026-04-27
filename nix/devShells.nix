{ inputs, ... }:

{
  perSystem = { pkgs, ... }:
    let
      pythonEnv = pkgs.python312.withPackages (ps: with ps; [
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
        pytest
        pytest-asyncio
      ]);

      devScript = pkgs.writeShellScriptBin "dev" ''
        # Start both backend and frontend for development
        cleanup() {
          echo ""
          echo "Stopping servers..."
          kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
          wait $BACKEND_PID $FRONTEND_PID 2>/dev/null
          exit 0
        }
        trap cleanup INT TERM

        echo "Starting Libix development servers..."
        echo ""

        # Start backend with dev config (use absolute path since we cd into backend/)
        export LIBIX_CONFIG="$PWD/config.dev.yaml"
        (cd backend && exec ${pythonEnv}/bin/python -m libix) &
        BACKEND_PID=$!

        # Wait a moment for backend to start
        sleep 2

        # Start frontend (install deps if needed)
        (cd frontend && npm install --silent && exec npm run dev) &
        FRONTEND_PID=$!

        echo ""
        echo "Backend:  http://localhost:8080"
        echo "Frontend: http://localhost:5173"
        echo ""
        echo "Press Ctrl+C to stop both servers"

        wait $BACKEND_PID $FRONTEND_PID
      '';
    in
    {
      devShells = {
        default = pkgs.mkShell {
          buildInputs = [
            pythonEnv
            pkgs.nodejs_20
            pkgs.typescript
            pkgs.typescript-language-server
            pkgs.python312Packages.python-lsp-server
            devScript
          ];

          shellHook = ''
            echo "Libix development environment"
            echo ""
            echo "Run 'dev' to start both backend and frontend"
            echo ""
            echo "Or run them separately:"
            echo "  Backend:  cd backend && python -m libix"
            echo "  Frontend: cd frontend && npm install && npm run dev"
            echo ""
            echo "The backend runs on http://localhost:8080"
            echo "The frontend dev server runs on http://localhost:5173"
          '';
        };

        backend = pkgs.mkShell {
          buildInputs = [
            pythonEnv
            pkgs.python312Packages.python-lsp-server
          ];

          shellHook = ''
            echo "Libix backend development environment"
            echo "Run 'python -m libix' to start the server"
          '';
        };

        frontend = pkgs.mkShell {
          buildInputs = [
            pkgs.nodejs_20
            pkgs.typescript
            pkgs.typescript-language-server
          ];

          shellHook = ''
            echo "Libix frontend development environment"
            echo "Run 'npm install && npm run dev' to start the dev server"
          '';
        };
      };
    };
}
