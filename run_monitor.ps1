# PowerShell script to set environment variables and run the Arise Opportunity Monitor
# Usage: .\run_monitor.ps1
#
# Before running, set your environment variables using one of these methods:
# 1. Run: . .\set_env_vars.ps1 (interactive prompts)
# 2. Edit and run: . .\set_env_vars_local.ps1 (hardcoded credentials)
# 3. Set them manually in PowerShell before running this script
#
# Set your credentials here (or use environment variables that are already set)
# If these are already set in your system, you can comment these out

# Arise Portal Credentials
if (-not $env:ARISE_USERNAME) {
    Write-Host "Please set ARISE_USERNAME environment variable or edit this script" -ForegroundColor Yellow
    # $env:ARISE_USERNAME = "your_username_here"
}

if (-not $env:ARISE_PASSWORD) {
    Write-Host "Please set ARISE_PASSWORD environment variable or edit this script" -ForegroundColor Yellow
    # $env:ARISE_PASSWORD = "your_password_here"
}

# Gmail Credentials for Notifications
if (-not $env:GMAIL_ADDRESS) {
    Write-Host "Please set GMAIL_ADDRESS environment variable or edit this script" -ForegroundColor Yellow
    # $env:GMAIL_ADDRESS = "your_email@gmail.com"
}

if (-not $env:GMAIL_APP_PASSWORD) {
    Write-Host "Please set GMAIL_APP_PASSWORD environment variable or edit this script" -ForegroundColor Yellow
    # $env:GMAIL_APP_PASSWORD = "your_app_password_here"
}

# Check if all required variables are set
$required_vars = @('ARISE_USERNAME', 'ARISE_PASSWORD', 'GMAIL_ADDRESS', 'GMAIL_APP_PASSWORD')
$missing_vars = @()

foreach ($var in $required_vars) {
    if (-not $env:$var) {
        $missing_vars += $var
    }
}

if ($missing_vars.Count -gt 0) {
    Write-Host "`n❌ Error: Missing required environment variables:" -ForegroundColor Red
    Write-Host "   $($missing_vars -join ', ')" -ForegroundColor Red
    Write-Host "`nTo set them in PowerShell, use:" -ForegroundColor Yellow
    Write-Host "   `$env:ARISE_USERNAME = 'your_username'" -ForegroundColor Cyan
    Write-Host "   `$env:ARISE_PASSWORD = 'your_password'" -ForegroundColor Cyan
    Write-Host "   `$env:GMAIL_ADDRESS = 'your_email@gmail.com'" -ForegroundColor Cyan
    Write-Host "   `$env:GMAIL_APP_PASSWORD = 'your_app_password'" -ForegroundColor Cyan
    Write-Host "`nOr use one of these methods:" -ForegroundColor Yellow
    Write-Host "   1. Run: . .\set_env_vars.ps1 (interactive)" -ForegroundColor Cyan
    Write-Host "   2. Edit and run: . .\set_env_vars_local.ps1 (hardcoded)" -ForegroundColor Cyan
    Write-Host "   3. Edit this script and uncomment the lines above" -ForegroundColor Cyan
    exit 1
}

# Run the monitor
Write-Host "`n🚀 Starting Arise Opportunity Monitor...`n" -ForegroundColor Green
py monitor.py

