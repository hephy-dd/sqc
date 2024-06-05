import os
from pyinstaller_versionfile import create_versionfile

import sqc

version = sqc.__version__
bundle = "sqc"
filename = "sqc.exe"
console = False
debug = False
block_cipher = None

package_root = os.path.join(os.path.dirname(sqc.__file__))
package_icon = os.path.join(package_root, "assets", "icons", "sqc.ico")

version_info = os.path.join(os.getcwd(), "version_info.txt")

# Create windows version info
create_versionfile(
    output_file=version_info,
    version=f"{version}.0",
    company_name="HEPHY",
    file_description="Sensor Quality Control for the CMS Tracker",
    internal_name="SQC",
    legal_copyright="Copyright © 2022-2024 HEPHY. All rights reserved.",
    original_filename=filename,
    product_name="SQC",
)

a = Analysis(
    ["entry_point.py"],
    pathex=[os.getcwd()],
    binaries=[],
    datas=[
        (os.path.join(package_root, "assets", "icons", "*.svg"), os.path.join("sqc", "assets", "icons")),
        (os.path.join(package_root, "assets", "icons", "*.ico"), os.path.join("sqc", "assets", "icons")),
    ],
    hiddenimports=[
        "pyvisa",
        "pyvisa_py",
        "serial",
        "usb",
        "gpib_ctypes",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher,
)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=filename,
    version=version_info,
    debug=debug,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=console,
    icon=package_icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=bundle,
)
