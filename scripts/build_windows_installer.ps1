$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
$setupBat = Join-Path $root "Setup Auto SI Generator.bat"

if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host "Local .venv was not found. Running setup first..."
    & $setupBat
}
if (-not (Test-Path -LiteralPath $venvPython)) {
    throw "Python virtual environment was not created. Run Setup Auto SI Generator.bat manually and try again."
}

Write-Host "Installing PyInstaller..."
& $venvPython -m pip install --upgrade pyinstaller

$distDir = Join-Path $root "dist"
$buildDir = Join-Path $root "build\pyinstaller"
$setupBuildDir = Join-Path $root "build\pyinstaller-setup"
$specDir = Join-Path $root "build\pyinstaller-spec"
$entryPoint = Join-Path $root "scripts\auto_support_generator_app.py"
$installerEntryPoint = Join-Path $root "scripts\auto_support_generator_installer.py"
$mnovaScript = Join-Path $root "scripts\extract_nmr_report.qs"
$setupExe = Join-Path $distDir "AutoSupportGeneratorSetup.exe"
$sedPath = Join-Path $distDir "AutoSupportGeneratorSetup.sed"

foreach ($oldFile in @($setupExe, $sedPath)) {
    if (Test-Path -LiteralPath $oldFile) {
        Remove-Item -LiteralPath $oldFile -Force
    }
}

Write-Host "Building AutoSupportGenerator.exe..."
& $venvPython -m PyInstaller `
    --noconfirm `
    --clean `
    --log-level=WARN `
    --onefile `
    --windowed `
    --name AutoSupportGenerator `
    --paths (Join-Path $root "src") `
    --add-data "$mnovaScript;scripts" `
    --distpath $distDir `
    --workpath $buildDir `
    --specpath $specDir `
    $entryPoint

$appExe = Join-Path $distDir "AutoSupportGenerator.exe"
if (-not (Test-Path -LiteralPath $appExe)) {
    throw "PyInstaller did not create $appExe"
}

$payloadDir = Join-Path $distDir "installer_payload"
if (Test-Path -LiteralPath $payloadDir) {
    Remove-Item -LiteralPath $payloadDir -Recurse -Force
}
New-Item -ItemType Directory -Path $payloadDir | Out-Null
$payloadExamplesDir = Join-Path $payloadDir "examples"
New-Item -ItemType Directory -Path $payloadExamplesDir | Out-Null

Copy-Item -LiteralPath $appExe -Destination (Join-Path $payloadDir "AutoSupportGenerator.exe")
Copy-Item -LiteralPath (Join-Path $root "style_config.example.yml") -Destination (Join-Path $payloadDir "style_config.example.yml")
Copy-Item -LiteralPath (Join-Path $root "README.md") -Destination (Join-Path $payloadDir "README.md")
Copy-Item -LiteralPath (Join-Path $root "INSTALL_RU.md") -Destination (Join-Path $payloadDir "INSTALL_RU.md")
Copy-Item -LiteralPath (Join-Path $root "examples\sample_compounds.csv") -Destination (Join-Path $payloadExamplesDir "sample_compounds.csv")
Copy-Item -LiteralPath (Join-Path $root "examples\generated_support_example.docx") -Destination (Join-Path $payloadExamplesDir "generated_support_example.docx")
Copy-Item -LiteralPath (Join-Path $root "examples\word_workflow") -Destination (Join-Path $payloadExamplesDir "word_workflow") -Recurse

Write-Host "Building AutoSupportGeneratorSetup.exe..."
& $venvPython -m PyInstaller `
    --noconfirm `
    --clean `
    --log-level=WARN `
    --onefile `
    --windowed `
    --name AutoSupportGeneratorSetup `
    --add-data "$payloadDir;payload" `
    --distpath $distDir `
    --workpath $setupBuildDir `
    --specpath $specDir `
    $installerEntryPoint

if (-not (Test-Path -LiteralPath $setupExe)) {
    throw "PyInstaller did not create $setupExe"
}

Write-Host ""
Write-Host "Build finished:"
Write-Host "  $appExe"
Write-Host "  $setupExe"
