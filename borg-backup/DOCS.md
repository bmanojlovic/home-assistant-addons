# Borg Backup

## Overview

Borg Backup is a secure and efficient backup solution for Home Assistant that uses the powerful BorgBackup tool to create encrypted, deduplicated, and compressed backups of your Home Assistant configuration and data.

## Features

- **Encryption**: Secure your backups with strong encryption
- **Deduplication**: Save space by only storing changes
- **Compression**: Reduce backup size with efficient compression
- **Remote Storage**: Store backups on remote servers via SSH
- **Automated Backups**: Schedule regular backups
- **Retention Policies**: Automatically manage old backups

## Installation

1. Add the repository to your Home Assistant instance:
   ```
   https://github.com/bmanojlovic/home-assistant-addons
   ```
2. Install the Borg Backup addon
3. Configure the addon as described below
4. Start the addon

## Configuration

### Basic Configuration

```yaml
# Required: Either use borg_repo_url OR (borg_host + borg_reponame)
borg_repo_url: "user@host:path/to/repo"  # Complete repository URL
# OR
borg_host: "backup-server"  # Hostname of your backup server
borg_user: "backupuser"     # SSH username
borg_reponame: "homeassistant-backup"  # Repository name/path

# Strongly recommended
borg_passphrase: "your-secure-passphrase"  # Encryption passphrase
```

### Advanced Options

```yaml
# SSH connection parameters
borg_ssh_params: "-p 2222 -o ConnectTimeout=10"  # Custom SSH parameters

# Backup settings
borg_compression: "zstd"  # Compression algorithm (zstd, lz4, zlib, etc.)
borg_backup_keep_snapshots: 5  # Number of backups to keep
borg_exclude_logs: true  # Exclude log files from backups
borg_custom_excludes: "*.cache,*/temp/*,*/downloads/*"  # Custom exclusion patterns
borg_backup_debug: false  # Enable debug logging
```

## SSH Key Setup

When first run, the addon will generate an SSH key and display it in the logs. You need to add this key to the `authorized_keys` file on your backup server.


Example log output:
```
[INFO] Your ssh key to use for borg backup host
[INFO] ************ SNIP **********************
ssh-rsa AAAAB3N... root@local-borg-backup
[INFO] ************ SNIP **********************
```

## System Optimization

The addon automatically detects your system capabilities and optimizes the backup process:

- Detects available CPU cores and memory
- Uses parallel compression on multi-core systems with sufficient memory
- Detects storage type (SSD vs HDD) and adjusts accordingly
- Automatically unpacks and processes nested archives

These optimizations happen automatically without any configuration needed.

## Home Assistant Integration

Borg Backup integrates with Home Assistant by providing several entities that show backup status and information:

### Available Entities

- **sensor.borg_backup_status**: Shows the current status of the backup process
- **sensor.borg_backup_last**: Timestamp of the last successful backup
- **sensor.borg_backup_repository**: Information about the Borg repository size and statistics
- **binary_sensor.borg_backup_available**: Indicates if the Borg repository is accessible
- **sensor.borg_available_backups**: Shows the number and list of available backups (in restore mode)

### Dashboard Integration

You can add these entities to your Home Assistant dashboard using standard Lovelace cards:

```yaml
# Entities card
type: entities
title: Borg Backup
entities:
  - sensor.borg_backup_status
  - sensor.borg_backup_last
  - sensor.borg_backup_repository
  - binary_sensor.borg_backup_available
```

### Backup Button Card

```yaml
# Button card for manual backup
type: button
name: Create Backup Now
icon: mdi:backup-restore
tap_action:
  action: call-service
  service: hassio.addon_start
  service_data:
    addon: local_borg-backup
```

### Restore Button Card

```yaml
# Conditional card for restore
type: conditional
conditions:
  - entity: binary_sensor.borg_backup_available
    state: "on"
card:
  type: button
  name: Restore Latest Backup
  icon: mdi:restore
  tap_action:
    action: call-service
    service: hassio.addon_start
    service_data:
      addon: local_borg-backup
      options:
        RESTORE_MODE: "true"
```

## Automation

To schedule automatic backups, create an automation in Home Assistant:

### Using the Home Assistant UI:
1. Go to **Settings** → **Automations & Scenes** → **Automations**
2. Click the **+ CREATE AUTOMATION** button
3. Click **Start with an empty automation**
4. Add a name: `Automatic Borg Backup`
5. In the **Triggers** section:
   - Click **+ ADD TRIGGER**
   - Select **Time** as trigger type
   - Set the time when you want backups to run (e.g., `02:02:00`)
6. In the **Actions** section:
   - Click **+ ADD ACTION**
   - Select **Call service**
   - For **Service**, choose `Home Assistant Supervisor: Start add-on`
   - In **Targets**, select your Borg Backup addon (usually `local_borg-backup`)
7. Click **SAVE**

### Using YAML configuration:
Add this to your `configuration.yaml` or create a new automation file:

```yaml
automation:
  - alias: "Daily Borg Backup"
    description: "Run Borg backup daily at 2 AM"
    trigger:
      platform: time
      at: "02:00:00"
    action:
      service: hassio.addon_start
      data:
        addon: local_borg-backup
```

**Note**: Replace `local_borg-backup` with your actual addon slug if different. You can find the exact name in the addon URL when viewing it in the Supervisor dashboard.

### Notification Automation

You can also create an automation to notify you when backups complete or fail:

```yaml
automation:
  - alias: "Borg Backup Status Notification"
    description: "Send notification when backup completes or fails"
    trigger:
      platform: state
      entity_id: sensor.borg_backup_status
      to: 
        - "completed"
        - "error"
    action:
      - service: notify.mobile_app
        data:
          title: "Borg Backup {{ trigger.to_state.state }}"
          message: >
            {% if trigger.to_state.state == 'completed' %}
              Backup completed successfully at {{ trigger.to_state.attributes.last_completed }}
            {% else %}
              Backup failed: {{ trigger.to_state.attributes.error_message }}
            {% endif %}
```

## Troubleshooting

### Common Issues

1. **SSH Connection Failures**:
   - Verify the SSH key is properly added to the remote server
   - Check network connectivity and firewall settings
   - Try using the `borg_ssh_params` option to add debugging: `-v`

2. **Permission Errors**:
   - Ensure the remote user has write permissions to the repository path
   - Check that the addon has access to the required directories

3. **Encryption Issues**:
   - If you forget your passphrase, you cannot recover your backups
   - Store your passphrase securely outside of Home Assistant

## Support

For issues, feature requests, or questions, please use the [GitHub issue tracker](https://github.com/bmanojlovic/home-assistant-addons/issues).
# Borg Backup

This is a symlink to [DOCS.md](DOCS.md) for GitHub repository browsing.

Please see the [DOCS.md](DOCS.md) file for complete documentation.
