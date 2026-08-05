param(
    [switch]$Clean,
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$Python = Join-Path $ProjectRoot "ambiente_config\Scripts\python.exe"
$PyInstaller = Join-Path $ProjectRoot "ambiente_config\Scripts\pyinstaller.exe"
$SpecFile = Join-Path $ProjectRoot "MalaDireta.spec"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python do ambiente virtual nao encontrado em: $Python"
}

if (-not (Test-Path -LiteralPath $PyInstaller)) {
    throw "PyInstaller nao encontrado em: $PyInstaller"
}

Set-Location $ProjectRoot

if ($Clean) {
    $allowedRoot = (Resolve-Path $ProjectRoot).Path
    foreach ($target in @("build", "dist")) {
        $targetPath = Join-Path $ProjectRoot $target
        if (-not (Test-Path -LiteralPath $targetPath)) {
            continue
        }

        $resolvedTarget = (Resolve-Path $targetPath).Path
        if (-not $resolvedTarget.StartsWith($allowedRoot)) {
            throw "Caminho de limpeza fora do projeto: $resolvedTarget"
        }

        Remove-Item -LiteralPath $resolvedTarget -Recurse -Force
    }
}

if (-not $SkipTests) {
    & $Python -m unittest
}

& $PyInstaller --noconfirm $SpecFile

$DistAppDir = Join-Path $ProjectRoot "dist\MalaDireta"
Copy-Item -LiteralPath (Join-Path $ProjectRoot "scripts\create_desktop_shortcut.ps1") -Destination (Join-Path $DistAppDir "Create-DesktopShortcut.ps1") -Force
Copy-Item -LiteralPath (Join-Path $ProjectRoot "scripts\Criar atalho Mala Direta.cmd") -Destination (Join-Path $DistAppDir "Criar atalho Mala Direta.cmd") -Force

Write-Host ""
Write-Host "Build finalizado."
Write-Host "Executavel: $DistAppDir\Mala Direta.exe"
Write-Host "Criador de atalho: $DistAppDir\Criar atalho Mala Direta.cmd"
Write-Host "Banco no app instalado: %LOCALAPPDATA%\MalaDireta\mala_direta.sqlite3"
