{
  description = "Libix - Self-hosted audiobook management application";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-parts.url = "github:hercules-ci/flake-parts";
  };

  outputs = { self, flake-parts, ... }@inputs:
    flake-parts.lib.mkFlake { inherit inputs; } {
      systems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];

      imports = [
        ./nix/devShells.nix
        ./nix/packages.nix
        ./nix/checks.nix
      ];

      flake = {
        overlays.default = final: prev: {
          libix = self.packages.${final.system}.default;
        };

        nixosModules.default = import ./nix/module.nix;
      };
    };
}
