[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$BackupPath
)

$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Execute este script em um PowerShell aberto como Administrador.'
}
if (-not (Test-Path -LiteralPath $BackupPath -PathType Leaf)) {
    throw "Backup não encontrado: $BackupPath"
}

& reg.exe import $BackupPath | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao importar o backup do Registro (código $LASTEXITCODE)."
}

Restart-Service -Name BTAGService -Force
(Get-Service -Name BTAGService).WaitForStatus('Running', [TimeSpan]::FromSeconds(20))
Write-Host 'Configuração HFP restaurada. Desconecte e reconecte o Bluetooth.'
