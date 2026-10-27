[CmdletBinding()]
param(
    [switch]$SkipTests,
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ($env:OS -ne "Windows_NT") {
    throw "Este script deve ser executado no Windows para gerar o executável e o instalador .exe."
}

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$VersionFile = Join-Path $Root "app\version.py"

if (-not (Test-Path $VersionFile)) {
    throw "Arquivo de versão não encontrado: $VersionFile"
}

$VersionContent = Get-Content $VersionFile -Raw

if ($VersionContent -match '__version__\s*=\s*["'']([^"'']+)["'']') {
    $Version = $Matches[1]
}
else {
    throw "Não foi possível identificar __version__ em app\version.py"
}

if ([string]::IsNullOrWhiteSpace($Version)) {
    throw "A versão encontrada em app\version.py está vazia."
}

Write-Host ""
Write-Host "==============================================" -ForegroundColor DarkGray
Write-Host " The Reader Codex - Build Windows" -ForegroundColor White
Write-Host " Versão detectada: $Version" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor DarkGray
Write-Host ""

function Resolve-BasePython {

    $py = Get-Command py.exe -ErrorAction SilentlyContinue

    if ($py) {
        return @{
            Exe  = $py.Source
            Args = @("-3")
        }
    }

    $python = Get-Command python.exe -ErrorAction SilentlyContinue

    if ($python) {
        return @{
            Exe  = $python.Source
            Args = @()
        }
    }

    throw @"
Python 3.10+ não foi encontrado.

Instale uma versão 64-bit do Python para Windows e execute novamente.

Download:
https://www.python.org/downloads/windows/
"@
}

function Find-InnoSetupCompiler {

    # Primeiro procura no PATH
    $command = Get-Command ISCC.exe -ErrorAction SilentlyContinue

    if ($command) {
        return $command.Source
    }

    # Depois verifica locais conhecidos
    $candidates = @(
        "$env:LOCALAPPDATA\Programs\Inno Setup 7\ISCC.exe",
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",

        "$env:ProgramFiles\Inno Setup 7\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe",

        "${env:ProgramFiles(x86)}\Inno Setup 7\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
    )

    foreach ($candidate in $candidates) {

        if (
            $candidate -and
            (Test-Path $candidate)
        ) {
            return $candidate
        }
    }

    return $null
}

$BasePython = Resolve-BasePython

$VenvDir = Join-Path $Root ".venv-build"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

$SpecFile = Join-Path $Root "TheReaderCodex.spec"

$BuildWork = Join-Path $Root "build\TheReaderCodex"
$DistDir = Join-Path $Root "dist"
$ExePath = Join-Path $DistDir "TheReaderCodex\TheReaderCodex.exe"

$InstallerOutput = Join-Path $Root "installer-output"
$InnoScript = Join-Path $Root "installer\TheReaderCodex.iss"

$SetupFileName = "TheReaderCodex-Setup-$Version.exe"
$SetupPath = Join-Path $InstallerOutput $SetupFileName

Write-Host "[1/6] Preparando ambiente de build..." -ForegroundColor Cyan

if (-not (Test-Path $VenvPython)) {

    Write-Host "Criando ambiente virtual em:"
    Write-Host $VenvDir -ForegroundColor DarkGray

    $LauncherArgs = @($BasePython.Args) + @(
        "-m",
        "venv",
        $VenvDir
    )

    & $BasePython.Exe @LauncherArgs

    if ($LASTEXITCODE -ne 0) {
        throw "Falha ao criar o ambiente virtual de build."
    }
}

if (-not (Test-Path $VenvPython)) {
    throw "O Python do ambiente virtual não foi criado: $VenvPython"
}

$PythonVersionOk = & $VenvPython -c @"
import sys
print(1 if sys.version_info >= (3, 10) else 0)
"@

if ($PythonVersionOk.Trim() -ne "1") {
    throw "Use Python 3.10 ou superior para gerar o instalador."
}

$PythonBits = & $VenvPython -c @"
import struct
print(struct.calcsize('P') * 8)
"@

if ($PythonBits.Trim() -ne "64") {
    throw "Use Python 64-bit. O instalador do The Reader Codex é destinado ao Windows x64."
}

$PythonFullVersion = & $VenvPython -c "import sys; print(sys.version.split()[0])"

Write-Host "Python: $PythonFullVersion - $PythonBits bits" -ForegroundColor DarkGray

Write-Host ""
Write-Host "[2/6] Instalando/atualizando dependências..." -ForegroundColor Cyan

& $VenvPython -m pip install --upgrade pip

if ($LASTEXITCODE -ne 0) {
    throw "Falha ao atualizar pip."
}

$Requirements = Join-Path $Root "requirements.txt"
$BuildRequirements = Join-Path $Root "requirements-build.txt"

if (-not (Test-Path $Requirements)) {
    throw "Arquivo não encontrado: $Requirements"
}

if (-not (Test-Path $BuildRequirements)) {
    throw "Arquivo não encontrado: $BuildRequirements"
}

& $VenvPython -m pip install `
    -r $Requirements `
    -r $BuildRequirements

if ($LASTEXITCODE -ne 0) {
    throw "Falha ao instalar dependências."
}

if (-not $SkipTests) {

    Write-Host ""
    Write-Host "[3/6] Executando testes..." -ForegroundColor Cyan

    & $VenvPython `
        -W error::ResourceWarning `
        -m unittest discover `
        -s tests `
        -v

    if ($LASTEXITCODE -ne 0) {
        throw "Os testes falharam. O build foi interrompido."
    }

    Write-Host "Testes concluídos com sucesso." -ForegroundColor Green
}
else {

    Write-Host ""
    Write-Host "[3/6] Testes ignorados por parâmetro." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "[4/6] Gerando aplicativo Windows com PyInstaller..." -ForegroundColor Cyan

if (-not (Test-Path $SpecFile)) {
    throw "Arquivo PyInstaller não encontrado: $SpecFile"
}

# Remove artefatos antigos
foreach ($path in @(
    $BuildWork,
    $DistDir,
    $InstallerOutput
)) {

    if (Test-Path $path) {

        Write-Host "Removendo build anterior: $path" -ForegroundColor DarkGray

        Remove-Item `
            $path `
            -Recurse `
            -Force
    }
}

# Garante diretório do instalador
New-Item `
    -ItemType Directory `
    -Path $InstallerOutput `
    -Force |
    Out-Null

# Executar PyInstaller
& $VenvPython `
    -m PyInstaller `
    --noconfirm `
    --clean `
    $SpecFile

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller falhou."
}

if (-not (Test-Path $ExePath)) {
    throw "Executável esperado não foi criado: $ExePath"
}

Write-Host ""
Write-Host "[5/6] Aplicativo gerado com sucesso." -ForegroundColor Green
Write-Host "Executável:" -ForegroundColor DarkGray
Write-Host $ExePath

if ($SkipInstaller) {

    Write-Host ""
    Write-Host "[6/6] Instalador ignorado por parâmetro." -ForegroundColor Yellow

    Write-Host ""
    Write-Host "==============================================" -ForegroundColor Green
    Write-Host " BUILD CONCLUÍDO" -ForegroundColor Green
    Write-Host "==============================================" -ForegroundColor Green

    Write-Host "Versão:     $Version"
    Write-Host "Aplicativo: $ExePath"

    exit 0
}

$Iscc = Find-InnoSetupCompiler

if (-not $Iscc) {

    throw @"
Inno Setup não foi encontrado.

Instale o Inno Setup 6 ou 7 e execute novamente.

Com winget:

winget install --id JRSoftware.InnoSetup -e

O aplicativo já foi criado em:

$ExePath
"@
}

Write-Host ""
Write-Host "Inno Setup encontrado:" -ForegroundColor DarkGray
Write-Host $Iscc -ForegroundColor DarkGray

if (-not (Test-Path $InnoScript)) {
    throw "Script do Inno Setup não encontrado: $InnoScript"
}

Write-Host ""
Write-Host "[6/6] Gerando Setup.exe com Inno Setup..." -ForegroundColor Cyan

# Passa a versão de app\version.py para o Inno Setup
$VersionArgument = "/DMyAppVersion=$Version"

& $Iscc `
    $VersionArgument `
    $InnoScript

if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup falhou."
}

if (-not (Test-Path $SetupPath)) {

    Write-Host ""
    Write-Host "Arquivos encontrados em installer-output:" -ForegroundColor Yellow

    if (Test-Path $InstallerOutput) {

        Get-ChildItem $InstallerOutput |
            ForEach-Object {
                Write-Host " - $($_.Name)"
            }
    }

    throw "Instalador esperado não foi criado: $SetupPath"
}

$ExeSize = [math]::Round(
    (Get-Item $ExePath).Length / 1MB,
    2
)

$SetupSize = [math]::Round(
    (Get-Item $SetupPath).Length / 1MB,
    2
)

Write-Host ""
Write-Host "==============================================" -ForegroundColor Green
Write-Host " BUILD CONCLUÍDO COM SUCESSO" -ForegroundColor Green
Write-Host "==============================================" -ForegroundColor Green
Write-Host ""

Write-Host "Versão:     $Version"
Write-Host "Python:     $PythonFullVersion / $PythonBits-bit"
Write-Host ""
Write-Host "Aplicativo:"
Write-Host "  $ExePath"
Write-Host "  Tamanho: $ExeSize MB"
Write-Host ""
Write-Host "Instalador:"
Write-Host "  $SetupPath"
Write-Host "  Tamanho: $SetupSize MB"
Write-Host ""