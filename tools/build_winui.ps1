param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$env:DOTNET_CLI_TELEMETRY_OPTOUT = '1'
$env:DOTNET_NOLOGO = '1'

function Invoke-Checked([string]$Executable, [string[]]$Arguments) {
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Executable failed with exit code $LASTEXITCODE" }
}

Invoke-Checked $Python @('tools/prepare_winui.py')
Invoke-Checked $Python @('-m', 'pip', 'install', '--upgrade', '--only-binary=:all:', '--platform', 'win_amd64', '--python-version', '3.13', '--implementation', 'cp', '--target', '.build-tools/python/libs', '-r', 'tools/backend-requirements.txt')
Invoke-Checked $Python @('tools/prepare_backend.py')
Invoke-Checked '.\.build-tools\python\python.exe' @('tools/verify_backend.py')
$dotnet = Join-Path $projectRoot '.build-tools/dotnet/dotnet.exe'
Invoke-Checked $dotnet @('restore', 'winui/REmmanager.csproj', '-p:Platform=x64', '--source', 'https://api.nuget.org/v3/index.json', '--packages', '.build-tools/nuget')
Invoke-Checked $dotnet @('publish', 'winui/REmmanager.csproj', '-c', 'Release', '-p:Platform=x64', '--no-restore', '-o', 'dist')
if (-not (Test-Path -LiteralPath 'dist/REmmanager.exe')) { throw 'Published executable missing.' }
Write-Host 'Ready: dist/REmmanager.exe (Python, .NET and Windows App SDK bundled)'
