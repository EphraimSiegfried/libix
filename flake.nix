{
  description = "Libix - Self-hosted audiobook management application";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-parts.url = "github:hercules-ci/flake-parts";
  };

  outputs = inputs@{ flake-parts, ... }:
    flake-parts.lib.mkFlake { inherit inputs; } {
      systems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];

      imports = [
        ./nix/devShells.nix
        ./nix/packages.nix
        ./nix/checks.nix
      ];

      flake = {
        nixosModules.default = import ./nix/module.nix;
      };
    };
}
