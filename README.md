# Wing Theatre Controller

Professional show-control software for Behringer Wing mixer.  
DiGiCo-inspired: snapshots/cues, GO, Auto Update, Recall Scope, Fades, OSC/TCP control.

## Developers
- **Mikkel Peter Larsen**
- **Claude** (Anthropic — claude.ai)

## Credits
- **wingmon** — Mikkel Peter Larsen & Claude (Anthropic), built on libwing by dannyfiresnake
- **libwing** — dannyfiresnake (https://github.com/dannyfiresnake/libwing)
- **Protocol documentation** — Patrick-Gilles Maillot (Behringer Wing TCP/OSC)
- **python-osc** — attwad
- **PyQt6** — Riverbank Computing

## License
MIT

## Downloads
See [Releases](../../releases) for pre-built binaries for macOS and Windows.

## Structure
```
wing_theatre.py          ← Main application (Python/PyQt6)
wingmon/wingmon.rs       ← Wing binary bridge (Rust)
companion-module/        ← Bitfocus Companion v5 module
.github/workflows/       ← Automated build (macOS + Windows)
```

## Building from source

### macOS
```bash
# Install dependencies
pip3 install PyQt6 python-osc

# Build wingmon
cd /path/to/libwing
cargo build --release --example wingmon

# Run
python3 wing_theatre.py
```

### Windows
```bash
# Install Python 3.11+ and run
pip install PyQt6 python-osc pyinstaller

# Build wingmon (requires Rust)
cargo build --release --example wingmon

# Or download pre-built from Releases
```
