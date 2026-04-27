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
          ];

          shellHook = ''
            echo "Libix development environment"
            echo ""
            echo "Backend: cd backend && python -m libix"
            echo "Frontend: cd frontend && npm install && npm run dev"
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
