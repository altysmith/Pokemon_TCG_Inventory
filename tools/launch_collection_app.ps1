param(
    [int]$Port = 8766
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$appPath = Join-Path $projectRoot "app.py"
$requirementsPath = Join-Path $projectRoot "requirements.txt"
$dependencyHelper = Join-Path $PSScriptRoot "_ensure_dependencies.bat"
$runtimeDir = Join-Path $projectRoot "user_data\runtime"
$browserProfile = Join-Path $runtimeDir ("desktop-browser-" + [Guid]::NewGuid().ToString("N"))
$url = "http://127.0.0.1:$Port/"
$serverProcess = $null
$browserProcess = $null
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

function Get-AppBrowser {
    $candidates = @(
        (Join-Path ${env:ProgramFiles(x86)} "Microsoft\Edge\Application\msedge.exe"),
        (Join-Path $env:ProgramFiles "Microsoft\Edge\Application\msedge.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Google\Chrome\Application\chrome.exe"),
        (Join-Path $env:ProgramFiles "Google\Chrome\Application\chrome.exe"),
        (Join-Path $env:LOCALAPPDATA "Google\Chrome\Application\chrome.exe")
    )

    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            return $candidate
        }
    }

    throw "Microsoft Edge or Google Chrome is required for the app-style collection window."
}

function Test-CollectionServer {
    try {
        $health = Invoke-RestMethod -Uri ($url + "health") -TimeoutSec 2
        return ($health.ok -eq $true -and $health.server_api_version -eq 3)
    }
    catch {
        return $false
    }
}

try {
    $launcherMutex = [System.Threading.Mutex]::new($false, "Local\PokemonCardCollectionDesktopLauncher")
    if (-not $launcherMutex.WaitOne(0, $false)) {
        Show-LauncherMessage "Pokemon Card Collection is already open."
        exit 0
    }

    New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
    New-Item -ItemType Directory -Path $browserProfile -Force | Out-Null

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
        throw "A collection server is already running outside this desktop launcher. Close it, then click the collection icon again."
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

    $browserExecutable = Get-AppBrowser
    $browserArguments = @(
        "--app=$url",
        "--user-data-dir=`"$browserProfile`"",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-mode",
        "--disable-default-apps",
        "--disable-extensions",
        "--disable-component-extensions-with-background-pages",
        "--disable-features=msEdgeFirstRunExperience"
    )
    $browserProcess = Start-Process -FilePath $browserExecutable `
        -ArgumentList $browserArguments `
        -WorkingDirectory $projectRoot `
        -PassThru

    # Chromium may hand the app window to a second process and let the process
    # returned by Start-Process exit. Locate the real browser process by the
    # unique profile created for this launch, then watch its window directly.
    $browserProcessName = [IO.Path]::GetFileName($browserExecutable)
    $appBrowserProcess = $null
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        $appBrowserProcess = Get-CimInstance Win32_Process -Filter "Name = '$browserProcessName'" `
            -ErrorAction SilentlyContinue |
            Where-Object {
                $_.CommandLine -and
                $_.CommandLine.Contains($browserProfile) -and
                $_.CommandLine -notmatch "\s--type="
            } |
            Select-Object -First 1
        if ($appBrowserProcess) {
            break
        }
        Start-Sleep -Milliseconds 250
    }
    if (-not $appBrowserProcess) {
        throw "The collection browser window could not be tracked after it opened."
    }

    $windowAppeared = $false
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        $trackedProcess = Get-Process -Id $appBrowserProcess.ProcessId -ErrorAction SilentlyContinue
        if (-not $trackedProcess) {
            break
        }
        if ($trackedProcess.MainWindowHandle -ne 0) {
            $windowAppeared = $true
            break
        }
        Start-Sleep -Milliseconds 250
    }
    if (-not $windowAppeared) {
        throw "The collection browser process started, but its app window did not appear."
    }

    while ($true) {
        $trackedProcess = Get-Process -Id $appBrowserProcess.ProcessId -ErrorAction SilentlyContinue
        if (-not $trackedProcess -or $trackedProcess.MainWindowHandle -eq 0) {
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
    if ($browserProfile) {
        $profileBrowserProcesses = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -and $_.CommandLine.Contains($browserProfile) }
        foreach ($profileBrowserProcess in $profileBrowserProcesses) {
            Stop-Process -Id $profileBrowserProcess.ProcessId -Force -ErrorAction SilentlyContinue
        }
        if ($profileBrowserProcesses) {
            Start-Sleep -Milliseconds 250
        }
    }
    if ((Test-Path -LiteralPath $browserProfile) -and
        $browserProfile.StartsWith($runtimeDir, [StringComparison]::OrdinalIgnoreCase) -and
        (Split-Path -Leaf $browserProfile).StartsWith("desktop-browser-")) {
        Remove-Item -LiteralPath $browserProfile -Recurse -Force -ErrorAction SilentlyContinue
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
