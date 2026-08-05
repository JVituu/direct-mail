param(
    [string]$AppDir = "",
    [string]$ShortcutName = "Mala Direta - Atalho"
)

$ErrorActionPreference = "Stop"

function Resolve-AppDir {
    param([string]$InputDir)

    if (-not [string]::IsNullOrWhiteSpace($InputDir)) {
        return (Resolve-Path -LiteralPath $InputDir).Path
    }

    if (Test-Path -LiteralPath (Join-Path $PSScriptRoot "Mala Direta.exe")) {
        return (Resolve-Path -LiteralPath $PSScriptRoot).Path
    }

    $projectRoot = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
    return (Resolve-Path -LiteralPath (Join-Path $projectRoot "dist\MalaDireta")).Path
}

$resolvedAppDir = Resolve-AppDir -InputDir $AppDir
$exePath = Join-Path $resolvedAppDir "Mala Direta.exe"

if (-not (Test-Path -LiteralPath $exePath)) {
    throw "Executavel nao encontrado em: $exePath"
}

$iconCandidates = @(
    (Join-Path $resolvedAppDir "_internal\assets\mala_direta_rb_oficial.ico"),
    (Join-Path $resolvedAppDir "_internal\assets\mala_direta_logo.ico"),
    $exePath
)

$iconPath = $null
foreach ($candidate in $iconCandidates) {
    if (Test-Path -LiteralPath $candidate) {
        $iconPath = (Resolve-Path -LiteralPath $candidate).Path
        break
    }
}

if ($null -eq $iconPath) {
    throw "Icone do aplicativo nao encontrado."
}

$shell = New-Object -ComObject WScript.Shell
$desktopPath = $shell.SpecialFolders.Item("Desktop")
$shortcutPath = Join-Path $desktopPath "$ShortcutName.lnk"

if (Test-Path -LiteralPath $shortcutPath) {
    Remove-Item -LiteralPath $shortcutPath -Force
}

$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = (Resolve-Path -LiteralPath $exePath).Path
$shortcut.WorkingDirectory = $resolvedAppDir
$shortcut.IconLocation = "$iconPath,0"
$shortcut.Description = "Mala Direta"
$shortcut.WindowStyle = 1
$shortcut.Save()

Write-Host "Atalho criado:"
Write-Host $shortcutPath
Write-Host ""
Write-Host "Destino:"
Write-Host $exePath
Write-Host ""
Write-Host "Iniciar em:"
Write-Host $resolvedAppDir
Write-Host ""
Write-Host "Icone:"
Write-Host $iconPath
