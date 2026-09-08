# 短剧生成器（Drama Factory）开源版 · 一键打包脚本
# 用法（在仓库根目录，或任意位置用完整路径调用）：
#   powershell -ExecutionPolicy Bypass -File .\build_release.ps1 [-Python D:\Comfyui\python\python.exe]
# 产物：
#   release_os\短剧生成器安装向导.exe          （Tk 安装向导，与 InstallFiles 同目录发布）
#   release_os\InstallFiles\drama-gui.exe       （图形界面）
#   release_os\InstallFiles\drama-cli-onefile.exe（命令行引擎）
#   release_os\InstallFiles\使用说明.txt、drama_icon.png
#   release_os.zip                              （整包压缩，方便上传 GitHub Releases）
# 依赖：Python 3.10+ 且已安装 pyinstaller 与 requirements.txt；无 torch 等重依赖（已在 spec 中排除）。

param(
    [string]$Python = "",
    [string]$Repo  = ""
)

$ErrorActionPreference = "Stop"

if (-not $Repo) { $Repo = $PSScriptRoot }
if (-not $Python) {
    $cand = Join-Path (Split-Path $Repo -Parent) "python\python.exe"
    if (Test-Path $cand) { $Python = $cand } else { $Python = "python" }
}
$Stage  = Join-Path $Repo "release_os"
$Work   = Join-Path $Repo "release_os\_work"
$DistT  = Join-Path $Repo "release_os\_dist"
$Zip    = Join-Path $Repo "release_os.zip"

Write-Host "[1/4] 环境检查: $Python"
& $Python -m PyInstaller --version | Out-Host
if ($LASTEXITCODE -ne 0) { throw "PyInstaller 不可用，请先: $Python -m pip install pyinstaller -r requirements.txt" }

if (Test-Path $Stage) { Remove-Item -Recurse -Force $Stage }
New-Item -ItemType Directory -Force -Path $Stage, $DistT, $Work | Out-Null

Write-Host "[2/4] 打包 drama-gui / drama-cli-onefile / drama-setup（约需 5~15 分钟）"
foreach ($spec in @("drama-gui.spec", "drama-cli-onefile.spec", "drama-setup.spec")) {
    Write-Host ("--- PyInstaller " + $spec)
    & $Python -m PyInstaller --noconfirm --clean `
        --distpath $DistT `
        --workpath $Work `
        (Join-Path $Repo $spec)
    if ($LASTEXITCODE -ne 0) { throw "打包失败: $spec" }
}

Write-Host "[3/4] 组装发布目录"
$Inst = Join-Path $Stage "InstallFiles"
New-Item -ItemType Directory -Force -Path $Inst | Out-Null
Copy-Item (Join-Path $DistT "drama-gui.exe")         $Inst
Copy-Item (Join-Path $DistT "drama-cli-onefile.exe") $Inst
Copy-Item (Join-Path $Repo "assets\drama_icon.png")  $Inst
Copy-Item (Join-Path $Repo "deploy\使用说明.txt")    (Join-Path $Inst "使用说明.txt")
Copy-Item (Join-Path $DistT "drama-setup.exe")       (Join-Path $Stage "短剧生成器安装向导.exe")

Write-Host "[4/4] 压缩整包"
if (Test-Path $Zip) { Remove-Item -Force $Zip }
Compress-Archive -Path (Join-Path $Stage "*") -DestinationPath $Zip -CompressionLevel Optimal

Write-Host ""
Write-Host "完成。发布方式：把 release_os 整个文件夹（或 release_os.zip）分发即可；"
Write-Host "安装向导与 InstallFiles 必须保持同级目录。"
Get-ChildItem $Stage -Recurse -File | Select-Object FullName, Length | Format-Table -AutoSize
