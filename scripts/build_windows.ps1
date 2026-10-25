# Build 视频下载器.exe on Windows (PowerShell 5+).
# Usage:  powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

function Get-Python {
    if ($env:PYTHON) { return $env:PYTHON }
    foreach ($candidate in @("python", "py")) {
        try { & $candidate --version *> $null; return $candidate } catch { }
    }
    throw "未找到 Python，请先安装 Python 3.10+ 并加入 PATH"
}

$Python = Get-Python

Write-Host "==> 1/5 准备虚拟环境"
if (-not (Test-Path ".venv")) {
    & $Python -m venv .venv
}
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
& $VenvPython -m pip install -q -U pip
& $VenvPython -m pip install -q -r requirements.txt
& $VenvPython -m pip install -q "pyinstaller>=6.0"

Write-Host "==> 2/5 生成图标"
& $VenvPython scripts\make_icons.py

Write-Host "==> 3/5 打包（PyInstaller one-dir）"
if (Test-Path build) { Remove-Item -Recurse -Force build }
if (Test-Path dist) { Remove-Item -Recurse -Force dist }
& $VenvPython -m PyInstaller --noconfirm --clean scripts\glowdl.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller 打包失败" }

Write-Host "==> 4/5 校验产物"
$Exe = "dist\视频下载器\视频下载器.exe"
if (-not (Test-Path $Exe)) { throw "未找到 $Exe" }
Write-Host ("产物大小：{0:N1} MB" -f ((Get-Item $Exe).Length / 1MB))

Write-Host "==> 5/5 生成 zip 压缩包"
$Version = (& $VenvPython -c "from app import __version__; print(__version__)").Trim()
$Zip = "dist\视频下载器-$Version-Windows-x64.zip"
if (Test-Path $Zip) { Remove-Item -Force $Zip }
Compress-Archive -Path "dist\视频下载器\*" -DestinationPath $Zip
Write-Host "完成：$Zip"
