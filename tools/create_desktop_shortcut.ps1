$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$launcherPath = Join-Path $PSScriptRoot "launch_collection_app.ps1"
$iconPath = Join-Path $projectRoot "assets\pokemon-collection.ico"
$desktopPath = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktopPath "Pokemon Card Collection.lnk"
$powershellPath = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"

if (-not (Test-Path -LiteralPath $launcherPath)) {
    throw "The collection launcher could not be found at $launcherPath"
}
if (-not (Test-Path -LiteralPath $iconPath)) {
    throw "The collection icon could not be found at $iconPath"
}

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $powershellPath
$shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$launcherPath`""
$shortcut.WorkingDirectory = $projectRoot
$shortcut.IconLocation = "$iconPath,0"
$shortcut.Description = "Open the local Pokemon card collection"
$shortcut.Save()

Write-Output $shortcutPath
