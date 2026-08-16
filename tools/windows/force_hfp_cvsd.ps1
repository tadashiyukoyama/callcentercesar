[CmdletBinding()]
param(
    [string]$BackupDirectory = 'D:\Discador\backups\bluetooth'
)

$ErrorActionPreference = 'Stop'
$registryPath = 'HKLM:\SYSTEM\CurrentControlSet\Control\Bluetooth\Audio\Hfp\HandsFree'
$nativeRegistryPath = 'HKLM\SYSTEM\CurrentControlSet\Control\Bluetooth\Audio\Hfp\HandsFree'

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Execute este script em um PowerShell aberto como Administrador.'
}

New-Item -ItemType Directory -Path $BackupDirectory -Force | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backupPath = Join-Path $BackupDirectory "hfp-handsfree-before-cvsd-$stamp.reg"

& reg.exe export $nativeRegistryPath $backupPath /y | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao exportar o backup do Registro (código $LASTEXITCODE)."
}

$before = Get-ItemProperty -LiteralPath $registryPath
$brsfBefore = [int]$before.BrsfSupportedFeatures
$sdpBefore = [int]$before.SdpSupportedFeatures

# HFP HF +BRSF bit 7 anuncia negociação de codec. Sem ele, a sessão usa CVSD.
$brsfAfter = $brsfBefore -band (-bnot 0x80)
# HFP HF SDP SupportedFeatures bit 5 anuncia Wide Band Speech.
$sdpAfter = $sdpBefore -band (-bnot 0x20)

Set-ItemProperty -LiteralPath $registryPath -Name BrsfSupportedFeatures -Type DWord -Value $brsfAfter
Set-ItemProperty -LiteralPath $registryPath -Name SdpSupportedFeatures -Type DWord -Value $sdpAfter

Restart-Service -Name BTAGService -Force
(Get-Service -Name BTAGService).WaitForStatus('Running', [TimeSpan]::FromSeconds(20))

$after = Get-ItemProperty -LiteralPath $registryPath
[pscustomobject]@{
    Backup = $backupPath
    BrsfBefore = $brsfBefore
    BrsfAfter = [int]$after.BrsfSupportedFeatures
    SdpBefore = $sdpBefore
    SdpAfter = [int]$after.SdpSupportedFeatures
    BTAGService = (Get-Service -Name BTAGService).Status
} | Format-List

Write-Host 'Desconecte e reconecte o Bluetooth antes de repetir a chamada.'
