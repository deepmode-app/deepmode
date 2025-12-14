# Cron Jobs for Email Digests

This document describes how to configure and run the scheduled email digest jobs for Deepmode.

## Required Environment Variables

- **BASE_URL or APP_BASE_URL**: The base URL of your application (either one must be set)
  - Scripts prefer `BASE_URL` if set, otherwise fall back to `APP_BASE_URL`
  - Dev: `https://deepmode.onrender.com`
  - Prod: `https://deepmode.app`
  - Render typically uses `APP_BASE_URL` for web services

- **JOBS_SECRET**: A secret token used to authenticate cron job requests (required)
  - Must be set in both dev and prod environments
  - Should be different values per environment
  - Never expose this value publicly
  - Never logged or printed in scripts

## Render Cron Job Configuration

Configure these cron jobs in Render. **All schedules use UTC timezone.**

### Daily Streak Digest
- **Command**: `bash scripts/run_daily_digest.sh`
- **Schedule**: `0 9 * * *` (Daily at 9:00 AM UTC)

### Weekly Summary Digest
- **Command**: `bash scripts/run_weekly_digest.sh`
- **Schedule**: `0 10 * * 1` (Every Monday at 10:00 AM UTC)

## Example Schedules (All Times in UTC)

### Daily Digest
- Every day at 9:00 AM UTC: `0 9 * * *`
- Every day at 6:00 AM UTC: `0 6 * * *`

### Weekly Digest
- Every Monday at 10:00 AM UTC: `0 10 * * 1`
- Every Sunday at 9:00 AM UTC: `0 9 * * 0`

**Note:** Render cron jobs run in UTC timezone. Adjust schedules based on your user timezones.

## Manual Testing

To test the scripts manually from your local terminal:

### 1. Export Environment Variables

```bash
# Either BASE_URL or APP_BASE_URL must be set
export BASE_URL="https://deepmode.onrender.com"  # or https://deepmode.app for prod
# OR
export APP_BASE_URL="https://deepmode.onrender.com"  # Render typically uses this

export JOBS_SECRET="your-secret-value-here"
```

### 2. Run the Scripts

```bash
# Test daily digest
bash scripts/run_daily_digest.sh

# Test weekly digest
bash scripts/run_weekly_digest.sh
```

### 3. Verify Output

You should see:
- Success: `OK: daily digest triggered` or `OK: weekly digest triggered`
- Error: Script will exit with non-zero code and show error message if env vars are missing

## Security Notes

- **Never commit JOBS_SECRET to version control**
- The endpoints are protected and will return `403 Forbidden` if:
  - The `X-JOBS-SECRET` header is missing
  - The `X-JOBS-SECRET` header value doesn't match `JOBS_SECRET`
- The scripts validate that environment variables exist before making requests
- Failed requests will not expose the secret value

## Troubleshooting

### Script fails with "Either BASE_URL or APP_BASE_URL must be set"
- Ensure either `BASE_URL` or `APP_BASE_URL` is exported in your environment
- Check that Render has `APP_BASE_URL` configured (Render typically uses this for web services)
- Scripts prefer `BASE_URL` if set, otherwise use `APP_BASE_URL`

### Script fails with "JOBS_SECRET not set"
- Ensure `JOBS_SECRET` is exported in your environment
- Check that Render has `JOBS_SECRET` configured in environment variables

### Endpoint returns 403 Forbidden
- Verify that `JOBS_SECRET` in Render matches the value being sent
- Check that the `X-JOBS-SECRET` header is being sent correctly
- Ensure there are no extra spaces or newlines in the secret value

### Endpoint returns 500 Internal Server Error
- Check application logs for errors
- Verify that `JOBS_SECRET` is configured in the application environment

