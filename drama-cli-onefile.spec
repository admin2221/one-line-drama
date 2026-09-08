# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = []
tmp_ret = collect_all('factory')

# OpenAI 兼容提供商依赖（PyInstaller 对 try/except import 不自动收集，这里显式声明）
hiddenimports += ['openai', 'httpx', 'httpcore', 'distro', 'jiter']
# TTS 配音：edge-tts 及其 aiohttp 栈
hiddenimports += ['edge_tts', 'aiohttp', 'aiohappyeyeballs', 'aiodns', 'yarl',
                  'multidict', 'propcache', 'frozenlist', 'attrs', 'certifi', 'charset_normalizer']

a = Analysis(
    ['factory/drama_factory.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tensorflow','keras','tf_keras','jax','torch','torchvision','torchaudio','transformers','diffusers','accelerate','peft','lightning','pytorch_lightning','datasets','tokenizers','wandb','torchmetrics','timm','kornia','onnx','onnxruntime','sklearn','scipy','pyarrow','numba','sympy','networkx','nltk','botocore','boto3','googleapiclient','jedi','parso','matplotlib','av','xgboost','statsmodels','seaborn','plotly','pytest','sphinx','grpc','triton','nvidia','cupy','dask','fsspec','IPython','notebook','jupyter','opencv','cv2','moviepy','torchaudio','torchvision'],
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
    name='drama-cli-onefile',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/drama_icon.ico'],
)
