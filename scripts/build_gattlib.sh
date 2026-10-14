#!/usr/bin/env bash
# Build and install gattlib on Raspberry Pi OS (Debian trixie).
# Patches the examples to use libpcre2-8 because the old libpcre is no longer available.
set -euo pipefail

SRC_DIR="${1:-$HOME/gattlib}"

sudo apt install -y git cmake build-essential pkg-config \
    libbluetooth-dev libreadline-dev libglib2.0-dev libpcre2-dev

if [ ! -d "$SRC_DIR" ]; then
    git clone https://github.com/labapart/gattlib.git "$SRC_DIR"
fi
cd "$SRC_DIR"

# Replace libpcre with libpcre2-8 in all example CMakeLists
grep -rl "REQUIRED libpcre)" --include=CMakeLists.txt . \
    | xargs -r sed -i 's/REQUIRED libpcre)/REQUIRED libpcre2-8)/'

rm -rf build && mkdir build && cd build
cmake -DGATTLIB_BUILD_DOCS=OFF -DGATTLIB_PYTHON_INTERFACE=OFF ..
make -j"$(nproc)"
sudo make install
sudo ldconfig

echo
echo "gattlib installed. Examples are in: $SRC_DIR/build/examples/"
