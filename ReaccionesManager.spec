from PyInstaller.utils.hooks import collect_submodules

selenium_hiddenimports = collect_submodules('selenium.webdriver')
selenium_hiddenimports += collect_submodules('selenium.common')

a = Analysis(
	['app.py'],
	pathex=[],
	binaries=[],
	datas=[('templates', 'templates'), ('static', 'static')],
	hiddenimports=selenium_hiddenimports,
	hookspath=[],
	hooksconfig={},
	runtime_hooks=[],
	excludes=[],
	noarchive=False,
	optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
	pyz,
	a.scripts,
	a.binaries,
	a.datas,
	[],
	name='VIEWS',
	debug=False,
	bootloader_ignore_signals=False,
	strip=False,
	upx=True,
	upx_exclude=[],
	runtime_tmpdir=None,
	console=False,
	disable_windowed_traceback=False,
	argv_emulation=False,
	target_arch=None,
	codesign_identity=None,
	entitlements_file=None,
)
