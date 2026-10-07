param(
    [switch]$NoPause
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$venv = Join-Path $root ".venv"
$venvPython = Join-Path $venv "Scripts\python.exe"

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$Program,
        [Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments
    )
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Program failed with exit code $LASTEXITCODE."
    }
}

try {
    if (-not (Test-Path -LiteralPath $venvPython)) {
        $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
        if ($launcher) {
            Invoke-Checked -Program $launcher.Source -Arguments @("-3", "-m", "venv", $venv)
        } else {
            $python = Get-Command python.exe -ErrorAction SilentlyContinue
            if (-not $python) {
                throw "Python 3.10 or newer was not found. Install Python 3.12 and retry."
            }
            Invoke-Checked -Program $python.Source -Arguments @("-m", "venv", $venv)
        }
    }

    Invoke-Checked -Program $venvPython -Arguments @("-m", "pip", "install", "--upgrade", "pip")
    Invoke-Checked -Program $venvPython -Arguments @("-m", "pip", "install", "--prefer-binary", "-e", "${root}[build]")
    Invoke-Checked -Program $venvPython -Arguments @("-c", "import si_generator; print('Auto Support Generator', si_generator.__version__)")
    Write-Host "Setup completed. Run 'Run Auto SI Generator.bat' to start the application."
    exit 0
} catch {
    Write-Error $_
    if (-not $NoPause) {
        Read-Host "Press Enter to close"
    }
    exit 1
}
