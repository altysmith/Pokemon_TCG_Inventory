param(
    [int]$Port = 8766
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$appPath = Join-Path $projectRoot "app.py"
$requirementsPath = Join-Path $projectRoot "requirements.txt"
$dependencyHelper = Join-Path $PSScriptRoot "_ensure_dependencies.bat"
$runtimeDir = Join-Path $projectRoot "user_data\runtime"
$sessionToken = [Guid]::NewGuid().ToString("N")
$baseUrl = "http://127.0.0.1:$Port/"
$url = $baseUrl + "?desktop_session=$sessionToken"
$serverProcess = $null
$launcherMutex = $null

function Show-LauncherMessage {
    param(
        [string]$Message,
        [string]$Title = "Pokemon Card Collection"
    )

    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show(
        $Message,
        $Title,
        [System.Windows.MessageBoxButton]::OK,
        [System.Windows.MessageBoxImage]::Information
    ) | Out-Null
}

function Get-PythonExecutable {
    $bundledPython = "C:\Users\erica\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
    if (Test-Path -LiteralPath $bundledPython) {
        return $bundledPython
    }

    foreach ($candidate in @("py.exe", "python.exe")) {
        $command = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($command) {
            return $command.Source
        }
    }

    throw "Python could not be found. Open this project in Codex once to restore its bundled runtime."
}

function Test-CollectionServer {
    try {
        $health = Invoke-RestMethod -Uri ($baseUrl + "health") -TimeoutSec 2
        return ($health.ok -eq $true -and $health.server_api_version -eq 4)
    }
    catch {
        return $false
    }
}

function Get-DesktopSessionStatus {
    try {
        return Invoke-RestMethod `
            -Uri ($baseUrl + "desktop-session/status?token=$sessionToken") `
            -TimeoutSec 2
    }
    catch {
        return $null
    }
}

try {
    $launcherMutex = [System.Threading.Mutex]::new($false, "Local\PokemonCardCollectionDesktopLauncher")
    if (-not $launcherMutex.WaitOne(0, $false)) {
        Show-LauncherMessage "Pokemon Card Collection is already open."
        exit 0
    }

    New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null

    $pythonExecutable = Get-PythonExecutable
    $dependencyCheck = Start-Process -FilePath $dependencyHelper `
        -ArgumentList @("`"$pythonExecutable`"", "`"$requirementsPath`"") `
        -WorkingDirectory $projectRoot `
        -WindowStyle Hidden `
        -Wait `
        -PassThru
    if ($dependencyCheck.ExitCode -ne 0) {
        throw "The required Python packages could not be prepared. Check your internet connection and try again."
    }

    if (Test-CollectionServer) {
        throw "A collection server is already running outside this desktop launcher. Close its browser or command window, then click the collection icon again."
    }

    $serverProcess = Start-Process -FilePath $pythonExecutable `
        -ArgumentList @("`"$appPath`"", "--no-browser", "--port", $Port) `
        -WorkingDirectory $projectRoot `
        -WindowStyle Hidden `
        -PassThru

    $ready = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        if ($serverProcess.HasExited) {
            throw "The collection server stopped before it was ready."
        }
        if (Test-CollectionServer) {
            $ready = $true
            break
        }
        Start-Sleep -Milliseconds 250
    }
    if (-not $ready) {
        throw "The collection server did not become ready within 15 seconds."
    }

    Start-Process -FilePath $url | Out-Null

    $sessionConnected = $false
    for ($attempt = 0; $attempt -lt 80; $attempt++) {
        if ($serverProcess.HasExited) {
            throw "The collection server stopped before the browser connected."
        }
        $sessionStatus = Get-DesktopSessionStatus
        if ($sessionStatus -and $sessionStatus.connected) {
            $sessionConnected = $true
            break
        }
        Start-Sleep -Milliseconds 250
    }
    if (-not $sessionConnected) {
        throw "The default browser opened, but the collection tab did not connect within 20 seconds."
    }

    while ($true) {
        if ($serverProcess.HasExited) {
            throw "The collection server stopped unexpectedly."
        }
        $sessionStatus = Get-DesktopSessionStatus
        if ($sessionStatus -and -not $sessionStatus.connected -and
            $null -ne $sessionStatus.seconds_since_disconnect -and
            [double]$sessionStatus.seconds_since_disconnect -ge 4.0) {
            break
        }
        Start-Sleep -Milliseconds 500
    }
}
catch {
    Show-LauncherMessage $_.Exception.Message
}
finally {
    if ($serverProcess -and -not $serverProcess.HasExited) {
        Stop-Process -Id $serverProcess.Id -Force -ErrorAction SilentlyContinue
        $serverProcess.WaitForExit(5000) | Out-Null
    }
    if ($launcherMutex) {
        try {
            $launcherMutex.ReleaseMutex()
        }
        catch {
            # The mutex was not acquired, so there is nothing to release.
        }
        $launcherMutex.Dispose()
    }
}
