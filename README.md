# Arise Opportunity Monitor

Automated monitoring system for Arise portal opportunities. Sends email notifications when new job/training opportunities become available.

## Setup

### 1. Install Dependencies

```powershell
py -m pip install -r requirements.txt
```

### 2. Set Environment Variables

You need to set the following environment variables:

#### Option A: Set in PowerShell Session (Temporary)

```powershell
$env:ARISE_USERNAME = "your_arise_username"
$env:ARISE_PASSWORD = "your_arise_password"
$env:GMAIL_ADDRESS = "your_email@gmail.com"
$env:GMAIL_APP_PASSWORD = "your_gmail_app_password"
```

**Note:** These will only last for the current PowerShell session.

#### Option B: Set System-Wide (Permanent)

1. Open System Properties → Environment Variables
2. Add the variables to User variables or System variables
3. Restart your terminal

#### Option C: Use the Local Scripts (Recommended)

**Interactive Script** (prompts for credentials):
```powershell
. .\set_env_vars.ps1
py monitor.py
```

**Local Script** (edit file with your credentials):
1. Edit `set_env_vars_local.ps1` and replace the placeholder values
2. Run:
```powershell
. .\set_env_vars_local.ps1
py monitor.py
```

**Note:** The dot (`.`) before the script name is important - it sources the script so variables persist in your session.

#### Option D: Use the Run Script

Edit `run_monitor.ps1` and uncomment the lines to set your credentials, then run:

```powershell
.\run_monitor.ps1
```

### 3. Gmail App Password

For Gmail notifications, you need to create an App Password (not your regular password):

1. Go to your Google Account settings
2. Enable 2-Step Verification (if not already enabled)
3. Go to App Passwords: https://support.google.com/accounts/answer/185833
4. Generate a new app password for "Mail"
5. Use this 16-character password as `GMAIL_APP_PASSWORD`

## Usage

### Run the Monitor

```powershell
py monitor.py
```

Or use the helper script:

```powershell
.\run_monitor.ps1
```

### How It Works

1. Logs into the Arise portal using OAuth
2. Navigates to the Reference page
3. Checks the "Program Announcement" widget for opportunities
4. Compares with previous state
5. Sends email notification if new opportunities are detected

### What Gets Monitored

- **New Opportunities**: When opportunities appear (changes from "No Data" to showing opportunities)
- **Removed Opportunities**: When all opportunities are removed
- **Updated Opportunities**: When existing opportunities change

## Troubleshooting

### Widget Not Found

If you see "📭 Opportunity widget not found", the page content may be loaded dynamically via JavaScript. Check the `debug_page.html` file that gets created to see what HTML is being received.

### Authentication Issues

- Verify your Arise credentials are correct
- Check if the portal requires additional authentication steps
- Review the logs for specific error messages

### Email Not Sending

- Verify Gmail App Password is correct (not your regular password)
- Check that 2-Step Verification is enabled on your Google Account
- Ensure your firewall/antivirus isn't blocking SMTP connections

## Files

- `monitor.py` - Main monitoring script
- `run_monitor.ps1` - PowerShell helper script to set env vars and run
- `debug_page.html` - Saved page content for debugging (created on each run)
- `previous_state.txt` - Tracks the last known state of opportunities

## Notes

- The script saves state to `previous_state.txt` - don't delete this file
- First run will establish baseline and won't send notifications
- Subsequent runs will compare against the baseline and notify on changes
