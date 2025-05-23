# borg based backup for home assistant

## About
Home assistant is very nice system, but every system can crash or disks it resides on can stop spinning eventually, so we need to keep configuration and
data safe with some kind of backup, this addon provides exactly that. More about borgbackup could be found at [borgbackup](https://www.borgbackup.org/) website

Few things this addon provides to you are:
- automation of backups
- compression of backups
- deduplication of backups

first part is done by home assistant but last two are benefits that [borgbackup](https://www.borgbackup.org/) provides.

## Install
1) Add https://github.com/bmanojlovic/home-assistant-addons into supervisor addons-store
2) Install Borg-Backup addon
3) configure system and addon for backups

**Note**: Container images are hosted on GitHub Container Registry (ghcr.io).

## Configuration

there are two ways to configure borg repository path, using borg repository uri, or using "manual" way of setting it up using **borg_hostname** **borg_user** and **borg_reponame** parameters.
it could look to something like
```yaml
borg_host: host
borg_user: user
borg_reponame: path/to/repo
```
or 

set **borg_repo_url** to something like 
```yaml
borg_repo_url: user@host:path/to/repo
```

Please be aware that you are supposed to use only one way of doing it, as if both are used addon will exit with error.

### Encryption

By default, the addon will encrypt your backups using Borg's `repokey-blake2` encryption method. You should set a passphrase:

```yaml
borg_passphrase: "your-secure-passphrase"
```

If no passphrase is provided, the addon will warn you and initialize the repository without encryption, which is not recommended for sensitive data.

### Compression and Retention

You can configure the compression algorithm used for backups:

```yaml
borg_compression: "zstd"  # Default is "zstd", other options include "lz4", "zlib", etc.
```

Control how many backups to keep:

```yaml
borg_backup_keep_snapshots: 5  # Default is 5
```

### SSH Parameters

You can customize the SSH connection using the `borg_ssh_params` option. This allows you to pass additional SSH parameters like:

```yaml
borg_ssh_params: "-p 2222 -o ConnectTimeout=10"
```

Common use cases include:
- Changing the SSH port: `-p PORT`
- Setting connection timeouts: `-o ConnectTimeout=SECONDS`
- Using different key types: `-o IdentityAgent=none`
- Setting compression: `-C`

The SSH parameters will be added to the base SSH command that includes the identity file and known hosts configuration.

When first run addon will provide in its logs information of ssh key that you should set on borg backup server. Example key how it should look like is shown bellow.
```
[00:01:07] INFO: Your ssh key to use for borg backup host
[00:01:07] INFO: ************ SNIP **********************
ssh-rsa AAAAB3N... root@local-borg-backup
[00:01:07] INFO: ************ SNIP **********************

```

## System Optimization

The addon automatically detects your system capabilities and optimizes the backup process:

- Detects available CPU cores and memory
- Uses parallel compression on multi-core systems with sufficient memory
- Detects storage type (SSD vs HDD) and adjusts accordingly
- Automatically unpacks and processes nested archives

These optimizations happen automatically without any configuration needed.

## Log File Handling

By default, log files are excluded from backups to reduce size and improve performance:

```yaml
borg_exclude_logs: true  # Default: true
```

You can also add custom exclusion patterns:

```yaml
borg_custom_excludes: "*.cache,*/temp/*,*/downloads/*"
```

**Note**: Log files are typically not needed for disaster recovery and can significantly increase backup size and time.

## Automation
In Automation add something like this in Configuration -> Automations
1) click + symbol
2) skip Almond if you have it
3) add Name `Automatic borg backup`
4) in trigger section set "trigger type" to `Time`
5) on line stating "At" set time at which you would like backup to be done
```
02:02:02
```
6) in actions set `call service` if not already set
7) for service set `hassio.start_addon`
8) in "Service data" add above installed addon. Exact name of "`xxxx_borg-backup`" in configuration
  should be provided to you by system when you open from "supervisor dashboard" and going to addon page (look at URL of borg-backup )
```
addon: xxxx_borg-backup
```
9) save, sit and relax as it should work now :)


# Contact and issues

Use [issue tracker](https://github.com/bmanojlovic/home-assistant-addons/issues) on github for any issue with this addon.
