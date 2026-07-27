# -*- mode: python ; coding: utf-8 -*-


block_cipher = None


a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("organizer/templates", "organizer/templates"),
        ("organizer/static", "organizer/static"),
        ("organizer/core/certs", "organizer/core/certs"),
    ],
    # Django resolves {% load %} tags and TEMPLATES["context_processors"]
    # dotted paths via importlib at runtime, which PyInstaller's static
    # import scanner can't see -- without these, the packaged exe would 500
    # on any page (context_processors runs on every page; orch_extras loads
    # wherever {% load orch_extras %} appears).
    hiddenimports=["organizer.templatetags.orch_extras", "organizer.context_processors"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Orch",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX-compressed executables are a well-known antivirus false-positive
    # trigger (malware droppers commonly use UPX too, so AV heuristics
    # treat any UPX-packed binary with suspicion) -- off on purpose.
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="organizer/static/organizer/img/orch-mark.ico",
    version="version_info.txt",
)

# onedir, not onefile: a onefile build has to re-extract its whole bundle
# to a fresh temp folder on every single launch (not just install), which
# is slow enough that Windows can show a blank "ghost" placeholder window
# alongside the real one until it finishes. This collects everything into
# dist/Orch/ once at build time instead -- Orch.exe plus a support
# _internal/ folder next to it, extracted once, not on every run. See
# .github/workflows/release.yml for how this gets zipped for release, and
# organizer/core/updater.py for how the in-app self-updater swaps a onedir
# install in place.
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Orch",
)
