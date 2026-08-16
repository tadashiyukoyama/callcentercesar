$discadorRoot = 'D:\Discador'
$appPath = Join-Path $discadorRoot 'app.py'

if (-not (Test-Path -LiteralPath $appPath)) {
    throw "Aplicação não encontrada em $appPath"
}

Set-Location -LiteralPath $discadorRoot
Write-Host 'Discador: http://127.0.0.1:8765'
Write-Host 'Dados: D:\Discador\data'
Write-Host 'Pressione Ctrl+C para encerrar.'
python $appPath
