# Borg Backup for Home Assistant

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

## Automation

To schedule regular backups, create an automation in Home Assistant:

```yaml
automation:
  - alias: "Daily Borg Backup"
    trigger:
      platform: time
      at: "02:00:00"
    action:
      service: hassio.addon_start
      data:
        addon: local_borg-backup
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

For issues, feature requests, or questions, please use the [GitHub issue tracker](https://github.com/bmanojlovic/home-assistant-borg-backup/issues).
