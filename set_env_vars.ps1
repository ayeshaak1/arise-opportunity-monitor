# PowerShell script to set environment variables for Arise Opportunity Monitor
# Usage: . .\set_env_vars.ps1

Write-Host '🔐 Setting Environment Variables for Arise Opportunity Monitor' -ForegroundColor Cyan
Write-Host ''

# Set variables directly in this script
$env:ARISE_USERNAME = 'ayeshaa__k'
$env:ARISE_PASSWORD = 'Ar!seIsStupid1'
$env:GMAIL_ADDRESS = 'vortixanalyticsinc@gmail.com'
$appPassword = 'nfgn ybda zfyh foaz'
$env:GMAIL_APP_PASSWORD = $appPassword -replace '\s',''

Write-Host '✅ Environment variables set!' -ForegroundColor Green
Write-Host ''
Write-Host 'Variables set:' -ForegroundColor Cyan
Write-Host "  ARISE_USERNAME: $($env:ARISE_USERNAME)" -ForegroundColor Gray
Write-Host '  ARISE_PASSWORD: [HIDDEN]' -ForegroundColor Gray
Write-Host "  GMAIL_ADDRESS: $($env:GMAIL_ADDRESS)" -ForegroundColor Gray
Write-Host '  GMAIL_APP_PASSWORD: [HIDDEN]' -ForegroundColor Gray
Write-Host ''
Write-Host 'Now you can run: py monitor.py' -ForegroundColor Green
