{
  description = "A simple flake that builds Lutris-like packages";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";  # Adjust for your architecture
      pkgs = import nixpkgs { inherit system; };
    in {
      packages.${system}.myApp = pkgs.python3.pkgs.callPackage ./default.nix { };

      devShells.${system}.default = pkgs.mkShell {
        buildInputs = [ pkgs.python3 ];
      };
    };
}

