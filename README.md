# Libix

Audiobook manager with torrent downloading and metadata enrichment. Integrates
with Transmission for downloads and Audnexus/OpenLibrary for metadata. Organizes
your library in an Audiobookshelf-compatible folder structure.

## Features

- Search torrents via Prowlarr or built-in AudioBookBay scraper
- Two-stage metadata search with cover images
- Auto-import completed downloads to library
- Author-based folder organization (`/library/Author/Title/`)
- Language indicators and series info

## Getting started

### NixOS

Add the flake to your inputs and import the NixOS module:

```nix
{
  inputs.libix.url = "github:EphraimSiegfried/libix";
}
```

```nix
{ inputs, ... }:
{
  imports = [ inputs.libix.nixosModules.default ];
  services.libix = {
    enable = true;
    settings = {
      library.path = "/media/audiobooks";
      transmission.url = "http://localhost:9091/transmission/rpc";
    };
  };
}
```

### Development

```sh
nix develop
dev  # starts backend + frontend
```

## Configuration

See [config.example.yaml](./config.example.yaml) for all options.

## License

GPL-3.0
