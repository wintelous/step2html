# Build the Step2HTML Windows packages (run on Windows x64 from anywhere):
#   powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1
# -> dist\windows\Step2HTML-<version>-windows-x64.zip   portable (unzip and run Step2HTML.exe)
#    dist\windows\Step2HTML-<version>-Setup.exe         installer (Inno Setup 6)
# Needs Python 3.12 (py launcher) and Inno Setup 6; creates build\venv-win on first run.
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
function Check($what) { if ($LASTEXITCODE -ne 0) { throw "$what failed (exit code $LASTEXITCODE)" } }

$Venv = 'build\venv-win'
$VPy = "$Venv\Scripts\python.exe"
if (-not (Test-Path $VPy)) {
  Write-Host '[build] creating build\venv-win (Python 3.12)'
  py -3.12 -m venv $Venv; Check 'creating the venv'
}
& $VPy -m pip install --quiet --upgrade pip; Check 'pip upgrade'
& $VPy -m pip install --quiet -r packaging\requirements-app.txt; Check 'installing build requirements'
$Version = (Select-String -Path step2html.py -Pattern '__version__ = "([^"]+)"').Matches[0].Groups[1].Value

Write-Host '[build] icons'
& $VPy packaging\make_icon.py build\icons | Out-Null; Check 'icons'

Write-Host '[build] bundle (PyInstaller)'
& "$Venv\Scripts\pyinstaller.exe" --noconfirm --clean --log-level WARN --distpath dist --workpath build\pyinstaller packaging\step2html.spec
Check 'PyInstaller'

Write-Host '[build] smoke tests'
& $VPy packaging\make_test_step.py build\smoke.step | Out-Null; Check 'test STEP'
Remove-Item build\smoke.html -ErrorAction SilentlyContinue
# via cmd: Windows PowerShell 5.1 would turn the converter's progress output (stderr) into errors
cmd /c "dist\Step2HTML\step2html-cli.exe build\smoke.step -o build\smoke.html 2>&1" | Select-String '^\[|^done|^error' | ForEach-Object { $_.Line }
if (-not (Test-Path build\smoke.html)) { throw 'smoke conversion failed' }
$env:STEP2HTML_SELFTEST = '1'; $env:QT_QPA_PLATFORM = 'offscreen'
$p = Start-Process -FilePath dist\Step2HTML\Step2HTML.exe -Wait -PassThru
Remove-Item Env:STEP2HTML_SELFTEST, Env:QT_QPA_PLATFORM
if ($p.ExitCode -ne 0) { throw "window self-test failed (exit code $($p.ExitCode))" }
Write-Host 'selftest: window ok'

Write-Host '[build] portable zip'
New-Item -ItemType Directory -Force dist\windows | Out-Null
$Zip = "dist\windows\Step2HTML-$Version-windows-x64.zip"
Remove-Item $Zip -ErrorAction SilentlyContinue
tar.exe -a -c -f $Zip -C dist Step2HTML; Check 'zip'

Write-Host '[build] installer (Inno Setup)'
$Iscc = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
          "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Iscc) { throw 'Inno Setup 6 (ISCC.exe) not found - install it with: winget install JRSoftware.InnoSetup' }
& $Iscc /Q "/DAppVersion=$Version" "/DRoot=$Root" packaging\windows\step2html.iss; Check 'Inno Setup'

Get-ChildItem dist\windows | ForEach-Object { '{0}  {1:N0} MB' -f $_.Name, ($_.Length / 1MB) }
