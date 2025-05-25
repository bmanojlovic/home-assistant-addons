# Borg Backup: Complete Step-by-Step Guide

This guide provides detailed instructions for setting up, using, and restoring from Borg Backup.

## Part 1: Setting Up Backups

### Step 1: Install the Addon
1. In Home Assistant, go to **Settings** → **Add-ons** → **Add-on Store**
2. Click the **⋮** (three dots) in top right → **Repositories**
3. Add this URL: `https://github.com/bmanojlovic/home-assistant-addons`
4. Find "Borg Backup" in the store and click **Install**

### Step 2: Configure the Addon
1. After installation, click **Configuration** tab
2. Fill in these settings:
```yaml
borg_repo_url: "ssh://user@host/repo"
borg_passphrase: "your-secure-passphrase"
borg_compression: "zstd"
borg_backup_keep_snapshots: 5
borg_exclude_logs: true
```
3. Click **Save**

### Step 3: Get Your SSH Key
1. Click **Start** to run the addon once
2. Go to **Log** tab and look for this section:
```
[INFO] Your ssh key to use for borg backup host
[INFO] ************ SNIP **********************
ssh-rsa AAAAB3N... root@local-borg-backup
[INFO] ************ SNIP **********************
```
3. **Copy this entire ssh-rsa line**

### Step 4: Add SSH Key to Your Server
1. SSH into your backup server: `ssh user@host`
2. Add the key to authorized_keys:
```bash
echo "ssh-rsa AAAAB3N... root@local-borg-backup" >> ~/.ssh/authorized_keys
```
3. Set proper permissions:
```bash
chmod 600 ~/.ssh/authorized_keys
chmod 700 ~/.ssh
```

### Step 5: Test Your First Backup
1. In the addon, click **Start** again
2. Check the **Log** tab - you should see:
```
[INFO] Repository initialized successfully with encryption
[INFO] Creating Home Assistant backup
[INFO] Backup created successfully
```

### Step 6: Set Up Automatic Backups
1. Go to **Settings** → **Automations & Scenes** → **Automations**
2. Click **+ CREATE AUTOMATION** → **Start with an empty automation**
3. Set name: "Daily Borg Backup"
4. **Triggers**: Add **Time** trigger at `02:00:00`
5. **Actions**: Add **Call service** → `Home Assistant Supervisor: Start add-on`
6. Select your Borg Backup addon
7. Click **Save**

## Part 2: Restoring After System Reinstall

### Step 1: Fresh Home Assistant Installation
1. Install Home Assistant on your new system
2. Complete the initial setup (create user, etc.)

### Step 2: Reinstall Borg Backup Addon
1. Add the repository again: `https://github.com/bmanojlovic/home-assistant-addons`
2. Install "Borg Backup" addon
3. **Don't start it yet!**

### Step 3: Configure for Restore
1. Go to addon **Configuration** tab
2. Set the same repository settings:
```yaml
borg_repo_url: "ssh://user@host/repo"
borg_passphrase: "your-secure-passphrase"
```
3. **Important**: Add these environment variables:
```yaml
environment:
  RESTORE_MODE: "true"
```
4. Click **Save**

### Step 4: Set Up SSH Key Again
1. Click **Start** to run the addon
2. It will generate a new SSH key and show it in the logs
3. Copy the new SSH key from the logs
4. Add it to your server's `~/.ssh/authorized_keys` file

### Step 5: List Available Backups
1. Start the addon again (now with SSH access working)
2. Check the **Log** tab to see available backups:
```
[INFO] Found 5 backups:
[INFO] 1. 2024-01-15-14:30 (2024-01-15 14:30:00, 2.3 GB)
[INFO] 2. 2024-01-14-02:00 (2024-01-14 02:00:00, 2.1 GB)
[INFO] 3. 2024-01-13-02:00 (2024-01-13 02:00:00, 2.0 GB)
```

### Step 6: Restore Specific Backup (Optional)
If you want a specific backup instead of the latest:
1. Go to **Configuration** tab
2. Add the backup name to environment:
```yaml
environment:
  RESTORE_MODE: "true"
  BACKUP_NAME: "2024-01-15-14:30"
```
3. Click **Save**

### Step 7: Perform the Restore
1. Click **Start**
2. Watch the logs - you'll see:
```
[INFO] Using most recent backup: 2024-01-15-14:30
[INFO] Extracting backup from repository...
[INFO] Restore initiated successfully
[INFO] Home Assistant will now restart to complete the restore
```
3. **Home Assistant will restart automatically**
4. Wait 2-3 minutes for the system to come back online

### Step 8: Verify Restore
1. Log back into Home Assistant
2. Check that all your:
   - Automations are back
   - Integrations are working
   - Dashboard is restored
   - Settings are correct

### Step 9: Resume Normal Backups
1. Go back to the Borg Backup addon
2. Remove the restore environment variables:
```yaml
environment:
  RESTORE_MODE: "false"  # or remove this line entirely
```
3. Your automatic backup schedule will resume

## Quick Reference

**For Backup:**
- Repository: `ssh://user@host/repo`
- Passphrase: Your secure passphrase
- Just click **Start** or wait for automation

**For Restore:**
- Same repository settings
- Add `RESTORE_MODE: "true"` to environment
- Optionally add `BACKUP_NAME: "specific-backup-name"`
- Click **Start**
- Wait for automatic restart

**Important Notes:**
- Always keep your passphrase safe - without it, backups are unrecoverable
- The SSH key changes when you reinstall, so you need to add the new key to your server
- Restore will completely replace your current Home Assistant configuration
- The system will restart during restore - this is normal
