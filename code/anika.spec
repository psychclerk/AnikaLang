# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None
base_dir = os.path.dirname(os.path.abspath(SPEC))

a = Analysis(
    ['main.py'],
    pathex=[base_dir],
    binaries=[],
    # Bundle core/ and plugins/ as data files so PluginManager can discover them
    datas=[
        ('core', 'core'),
        ('plugins', 'plugins'),
    ],
    hiddenimports=[
        # wxPython internals
        'wx._xml', 'wx._richtext', 'wx._html2', 'wx._adv', 
        'wx._grid', 'wx._stc', 'wx._core',
        # Core modules
        'core.errors', 'core.lexer', 'core.ast_nodes', 'core.parser', 
        'core.interpreter', 'core.compiler', 'core.plugin_manager', 'core.utils',
        # Plugins
        'plugins.base_plugin', 'plugins.plugin_stdlib', 'plugins.plugin_ui',
        'plugins.plugin_stats', 'plugins.plugin_ml', 'plugins.plugin_graphs',
        'plugins.plugin_ai_rag', 'plugins.plugin_docs', 'plugins.plugin_excel',
        'plugins.plugin_network', 'plugins.plugin_media', 'plugins.plugin_lang_voice',
        'plugins.plugin_db_files', 'plugins.plugin_joplin',
        # Heavy Data Science / AI dependencies
        'numpy', 'scipy', 'scipy.stats', 'scipy.special', 'scipy.spatial',
        'sklearn', 'sklearn.tree', 'sklearn.ensemble', 'sklearn.linear_model',
        'sklearn.neighbors', 'sklearn.svm', 'sklearn.cluster', 'sklearn.decomposition',
        'sklearn.preprocessing', 'sklearn.metrics', 'sklearn.model_selection',
        'matplotlib', 'matplotlib.pyplot', 'PIL', 'PIL.Image',
        'openpyxl', 'docx', 'pptx', 'PyPDF2', 'faiss',
        'markdown', 'markdownify', 'deep_translator', 'pyttsx3', 'gtts',
    ],
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

# CRITICAL: Build a SMALL exe with exclude_binaries=True
exe = EXE(
    pyz,
    a.scripts,
    [],                          # Empty list = no binaries bundled into exe
    exclude_binaries=True,       # Keep the exe small!
    name='AnikaLang',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,                # Set to False to hide the console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='your_icon.ico',     # Uncomment if you have an icon
)

# CRITICAL: Collect everything else into the _internal folder
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AnikaLang',
)