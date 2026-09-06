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
$expectedServerApiVersion = $null

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

function Get-ExpectedServerApiVersion {
    $match = Select-String -LiteralPath $appPath -Pattern '^SERVER_API_VERSION\s*=\s*(\d+)\s*$' |
        Select-Object -First 1
    if (-not $match) {
        throw "The collection app version could not be read from app.py."
    }
    return [int]$match.Matches[0].Groups[1].Value
}

function Get-DefaultBrowserExecutable {
    try {
        $choice = Get-ItemProperty `
            -LiteralPath "HKCU:\Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice" `
            -ErrorAction Stop
        $commandKey = Get-Item `
            -LiteralPath "Registry::HKEY_CLASSES_ROOT\$($choice.ProgId)\shell\open\command" `
            -ErrorAction Stop
        $command = [string]$commandKey.GetValue("")
        $match = [regex]::Match($command, '^\s*(?:"([^"]+\.exe)"|([^\s]+\.exe))', 'IgnoreCase')
        if ($match.Success) {
            $path = if ($match.Groups[1].Success) { $match.Groups[1].Value } else { $match.Groups[2].Value }
            if (Test-Path -LiteralPath $path) {
                return $path
            }
        }
    }
    catch {
        # Windows can still open the URL through its registered default handler.
    }
    return $null
}

function Open-CollectionWindow {
    param([string]$Url)

    $browserExecutable = Get-DefaultBrowserExecutable
    if (-not $browserExecutable) {
        Start-Process -FilePath $Url | Out-Null
        return
    }
    $browserName = [IO.Path]::GetFileName($browserExecutable).ToLowerInvariant()
    if ($browserName -eq "firefox.exe") {
        Start-Process -FilePath $browserExecutable -ArgumentList @("-new-window", $Url) | Out-Null
        return
    }
    if ($browserName -in @("chrome.exe", "msedge.exe", "brave.exe", "vivaldi.exe")) {
        Start-Process -FilePath $browserExecutable -ArgumentList @("--new-window", $Url) | Out-Null
        return
    }
    Start-Process -FilePath $Url | Out-Null
}

function Test-CollectionServer {
    try {
        $health = Invoke-RestMethod -Uri ($baseUrl + "health") -TimeoutSec 2
        return (
            $health.ok -eq $true -and
            [int]$health.server_api_version -eq $expectedServerApiVersion
        )
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

    $expectedServerApiVersion = Get-ExpectedServerApiVersion
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

    Open-CollectionWindow -Url $url

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
        $disconnectedTooLong = (
            $sessionStatus -and
            -not $sessionStatus.connected -and
            $null -ne $sessionStatus.seconds_since_disconnect -and
            [double]$sessionStatus.seconds_since_disconnect -ge 4.0
        )
        $heartbeatStopped = (
            $sessionStatus -and
            $sessionStatus.connected -and
            $null -ne $sessionStatus.seconds_since_heartbeat -and
            [double]$sessionStatus.seconds_since_heartbeat -ge 4.0
        )
        if ($disconnectedTooLong -or $heartbeatStopped) {
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
