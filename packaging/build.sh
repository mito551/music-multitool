#!/usr/bin/env bash
# Builds dist/: wheel, sdist, and a tarball with the wheel plus install notes.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
python3 -m pip install -q build
python3 -m build
v=$(python3 -c "import tomllib;print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")
work=$(mktemp -d)
stage="$work/music-multitool-$v"
mkdir -p "$stage"
cp "dist/musicmultitool-$v-"*.whl README.md "$stage/"
cat > "$stage/install.sh" <<'EOS'
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
command -v pipx >/dev/null || { echo "Install pipx first: sudo dnf install pipx" >&2; exit 1; }
pipx install --force --system-site-packages ./*.whl
"$HOME/.local/bin/music-multitool" --install-desktop
EOS
chmod +x "$stage/install.sh"
tar -C "$work" -czf "dist/music-multitool-$v.tar.gz" "music-multitool-$v"
ls -1 dist
