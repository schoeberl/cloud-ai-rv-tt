{
  description = "Chisel and LibreLane ASIC development environment";
  inputs.librelane.url = "github:librelane/librelane/3.0.16";
  outputs = { self, librelane }: let
    system = "x86_64-linux";
    pkgs = librelane.legacyPackages.${system};
  in {
    devShells.${system}.default = pkgs.librelane-shell.override {
      extra-packages = with pkgs; [ jdk21 gnumake curl ];
      extra-env = [ { name = "PDK_ROOT"; eval = "$PWD/pdks"; } ];
    };
  };
}
