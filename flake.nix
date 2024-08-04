{
  inputs.nixpkgs.url = "github:nixos/nixpkgs/nixpkgs-unstable";
  outputs =
    { nixpkgs, ... }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs { inherit system; };
      lib = nixpkgs.lib;
    in
    {
      devShells.${system}.default = pkgs.mkShell {
        buildInputs = with pkgs; [
          (python3.withPackages (
            pyPkgs: with pyPkgs; [
              # for interactive debugging
              ipython
              # needed libraries
              pygobject3
              requests
              pillow
              pyyaml
              setproctitle
              distro
              evdev
              dbus-python
              magic
              lxml
              google
            ]
          ))
          gobject-introspection
          webkitgtk
          gtk3
          cairo
          p7zip
          vulkan-tools
          psmisc
          fluidsynth
        ];
        packages = with pkgs; [
            ruff
            mypy
        ];
        shellHook = ''
          export LD_LIBRARY_PATH='${lib.makeLibraryPath (with pkgs; [ file ])}';
        '';
      };
    };
}
