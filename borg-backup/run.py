#!/usr/bin/env python3

import os
import sys
import json
import shutil
import logging
import subprocess
import requests
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Dict, Any
import multiprocessing
import psutil


@dataclass
class SystemCapabilities:
    cpu_cores: int
    available_memory_mb: int
    is_slow_storage: bool
    use_parallel: bool
    compression_threads: int


@dataclass
class BorgConfig:
    base_dir: str = "/homeassistant/borg"
    cache_dir: str = "/homeassistant/borg/cache"
    backup_dir: str = "/backup/borg_unpacked"
    ssh_known_hosts: str = "/homeassistant/borg/known_hosts"
    ssh_key: str = "/homeassistant/borg/keys/borg_backup"

    # These will be loaded from Home Assistant config
    passphrase: Optional[str] = None
    repo_url: Optional[str] = None
    user: Optional[str] = None
    host: Optional[str] = None
    reponame: Optional[str] = None
    compression: str = "zstd"
    debug: bool = False
    keep_snapshots: int = 5
    ssh_params: str = ""
    exclude_logs: bool = True
    custom_excludes: str = ""


class BorgBackup:
    def __init__(self):
        self.logger = self._setup_logging()
        self.config = self._load_config()
        self.capabilities = self._detect_system_capabilities()
        self._setup_environment()

    def _setup_logging(self) -> logging.Logger:
        logger = logging.getLogger("borg_backup")
        logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger

    def _detect_system_capabilities(self) -> SystemCapabilities:
        cpu_cores = multiprocessing.cpu_count()
        available_memory = psutil.virtual_memory().available // (
            1024 * 1024
        )  # Convert to MB

        # Check for slow storage
        root_device = Path("/").resolve()
        is_slow_storage = False

        try:
            if "mmcblk" in str(root_device) or self._is_rotational_disk(
                str(root_device)
            ):
                is_slow_storage = True
        except Exception:
            self.logger.warning(
                "Could not determine storage type, assuming slow storage"
            )
            is_slow_storage = True

        use_parallel = cpu_cores > 1 and available_memory > 1024 and not is_slow_storage

        compression_threads = (cpu_cores - 1) if use_parallel else 1

        return SystemCapabilities(
            cpu_cores=cpu_cores,
            available_memory_mb=available_memory,
            is_slow_storage=is_slow_storage,
            use_parallel=use_parallel,
            compression_threads=compression_threads,
        )

    def _is_rotational_disk(self, device_path: str) -> bool:
        try:
            device = os.path.realpath(device_path)
            sys_path = f"/sys/block/{device.split('/')[-1]}/queue/rotational"
            with open(sys_path, "r") as f:
                return f.read().strip() == "1"
        except Exception:
            return True

    def _load_config(self) -> BorgConfig:
        try:
            # Read configuration from the standard add-on options file
            with open("/data/options.json", "r") as f:
                options = json.load(f)

            config = BorgConfig()
            config.passphrase = options.get("borg_passphrase")
            config.repo_url = options.get("borg_repo_url")
            config.user = options.get("borg_user")
            config.host = options.get("borg_host")
            config.reponame = options.get("borg_reponame")
            config.compression = options.get("borg_compression", "zstd")
            config.debug = options.get("borg_backup_debug", False)
            config.keep_snapshots = int(options.get("borg_backup_keep_snapshots", 5))
            config.ssh_params = options.get("borg_ssh_params", "")
            config.exclude_logs = options.get("borg_exclude_logs", True)
            config.custom_excludes = options.get("borg_custom_excludes", "")

            self._validate_config(config)
            return config

        except FileNotFoundError:
            self.logger.error("Configuration file /data/options.json not found")
            sys.exit(1)
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse configuration JSON: {e}")
            sys.exit(1)
        except Exception as e:
            self.logger.error(f"Unexpected error loading config: {e}")
            sys.exit(1)

    def _validate_config(self, config: BorgConfig):
        if not config.repo_url and not config.host:
            raise ValueError("Either 'borg_repo_url' or 'borg_host' must be defined")
        if config.repo_url and config.host:
            raise ValueError("Cannot define both 'borg_repo_url' and 'borg_host'")
        if config.host and not config.reponame:
            raise ValueError("When using borg_host, borg_reponame must be defined")

        # Construct repository URL if using host+reponame format
        if config.host and not config.repo_url:
            user_prefix = f"{config.user}@" if config.user else ""
            config.repo_url = f"{user_prefix}{config.host}:{config.reponame}"

    def _ensure_ssh_key(self):
        """Generate and display SSH key if it doesn't exist."""
        key_path = Path(self.config.ssh_key)
        if not key_path.exists():
            key_path.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                [
                    "ssh-keygen",
                    "-t",
                    "rsa",
                    "-b",
                    "4096",
                    "-f",
                    str(key_path),
                    "-N",
                    "",
                    "-C",
                    "root@local-borg-backup",
                ],
                check=True,
            )

            # Display the public key
            pub_key = key_path.with_suffix(".pub").read_text().strip()
            self.logger.info("Your ssh key to use for borg backup host")
            self.logger.info("************ SNIP **********************")
            self.logger.info(pub_key)
            self.logger.info("************ SNIP **********************")
        else:
            # Key exists, show thumbprint for verification
            try:
                result = subprocess.run(
                    ["ssh-keygen", "-lf", str(key_path.with_suffix(".pub"))],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                thumbprint = result.stdout.strip()
                self.logger.info(
                    f"Using existing SSH key with thumbprint: {thumbprint}"
                )
            except subprocess.CalledProcessError as e:
                self.logger.warning(
                    f"Could not generate thumbprint for existing key: {e}"
                )

    def _setup_environment(self):
        """Setup environment variables for Borg including encryption settings."""
        os.environ["BORG_BASE_DIR"] = self.config.base_dir
        os.environ["BORG_CACHE_DIR"] = self.config.cache_dir

        # Handle encryption settings
        if self.config.passphrase:
            os.environ["BORG_PASSPHRASE"] = self.config.passphrase
            # Remove any previous unencrypted access setting
            os.environ.pop("BORG_UNKNOWN_UNENCRYPTED_REPO_ACCESS_IS_OK", None)
        else:
            self.logger.warning(
                "No passphrase set - repository will be initialized without encryption!"
            )
            os.environ["BORG_UNKNOWN_UNENCRYPTED_REPO_ACCESS_IS_OK"] = "yes"
            os.environ.pop("BORG_PASSPHRASE", None)

        # Set up SSH configuration with additional parameters
        ssh_cmd = f"ssh -o UserKnownHostsFile={self.config.ssh_known_hosts} -i {self.config.ssh_key}"
        if self.config.ssh_params:
            ssh_cmd = f"{ssh_cmd} {self.config.ssh_params}"
        os.environ["BORG_RSH"] = ssh_cmd

        # Create required directories
        Path(self.config.base_dir).mkdir(parents=True, exist_ok=True)
        Path(self.config.cache_dir).mkdir(parents=True, exist_ok=True)
        Path(self.config.backup_dir).mkdir(parents=True, exist_ok=True)

        # Ensure SSH key exists
        self._ensure_ssh_key()

    def unpack_backup(self, snap_slug: str):
        target_dir = Path(self.config.backup_dir) / snap_slug
        target_dir.mkdir(parents=True, exist_ok=True)

        self.logger.info(f"Unpacking backup {snap_slug}")

        tar_cmd = ["tar"]
        if self.capabilities.use_parallel and shutil.which("pigz"):
            self.logger.info(
                f"Using parallel decompression with {self.capabilities.compression_threads} threads"
            )
            tar_cmd.extend(
                [
                    "--use-compress-program",
                    f"pigz -p {self.capabilities.compression_threads}",
                ]
            )

        tar_cmd.extend(["-xf", f"/backup/{snap_slug}.tar", "-C", str(target_dir)])

        try:
            subprocess.run(tar_cmd, check=True)
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to unpack backup: {e}")
            raise

        # Handle nested archives
        for targz in target_dir.rglob("*.tar.gz"):
            extract_dir = targz.with_suffix("").with_suffix("")
            extract_dir.mkdir(parents=True, exist_ok=True)

            try:
                self._extract_nested_archive(targz, extract_dir)
                targz.unlink()
            except Exception as e:
                self.logger.error(f"Failed to extract nested archive {targz}: {e}")
                raise

    def _extract_nested_archive(self, archive_path: Path, extract_dir: Path):
        tar_cmd = ["tar"]
        if self.capabilities.use_parallel and shutil.which("pigz"):
            tar_cmd.extend(
                [
                    "--use-compress-program",
                    f"pigz -p {self.capabilities.compression_threads}",
                ]
            )
        tar_cmd.extend(["-xf", str(archive_path), "-C", str(extract_dir)])

        subprocess.run(tar_cmd, check=True)

    def init_borg_repo(self):
        """Initialize Borg repository with encryption if it doesn't exist."""
        config_path = Path(self.config.base_dir) / ".config/borg/security"

        if not config_path.exists():
            self.logger.info("Initializing backup repository with encryption")
            cmd = ["borg", "init", "--encryption=repokey-blake2"]

            if self.config.debug:
                cmd.append("--debug")

            try:
                subprocess.run(cmd, check=True, env=os.environ)
                self.logger.info("Repository initialized successfully with encryption")
            except subprocess.CalledProcessError as e:
                self.logger.error(f"Failed to initialize repository: {e}")
                raise

    def create_backup(self):
        """Create a new backup with encryption."""
        try:
            # Ensure repository is initialized with encryption
            self.init_borg_repo()

            backup_time = (
                subprocess.check_output(["date", "+%Y-%m-%d-%H:%M"]).decode().strip()
            )

            self.logger.info("Creating Home Assistant backup")
            result = self._create_ha_backup(backup_time)

            if result:
                snap_slug = result["slug"]
                self.unpack_backup(snap_slug)

                self.logger.info("Creating encrypted Borg backup")
                self._create_borg_backup(backup_time, snap_slug)

                self._cleanup_old_backups()
        except Exception as e:
            self.logger.error(f"Backup creation failed: {e}")
            sys.exit(1)
        finally:
            self._cleanup_temp_files()

    def _create_ha_backup(self, backup_time: str) -> Dict[str, Any]:
        try:
            # Try using the Supervisor API directly
            supervisor_token = os.environ.get("SUPERVISOR_TOKEN")

            if supervisor_token:
                # Use direct API call to Supervisor
                headers = {
                    "Authorization": f"Bearer {supervisor_token}",
                    "Content-Type": "application/json",
                }

                backup_data = {"name": f"borg-{backup_time}", "compressed": True}

                response = requests.post(
                    "http://supervisor/backups/new/full",
                    headers=headers,
                    json=backup_data,
                    timeout=300,
                )

                if response.status_code == 200:
                    data = response.json()
                    if data["result"] == "ok":
                        return data["data"]
                    else:
                        raise RuntimeError(f"API returned error: {data}")
                else:
                    raise RuntimeError(
                        f"API request failed with status {response.status_code}: {response.text}"
                    )

            else:
                # Fallback to ha command without token
                self.logger.warning(
                    "SUPERVISOR_TOKEN not available, trying ha command without explicit token"
                )
                result = subprocess.run(
                    [
                        "ha",
                        "backup",
                        "new",
                        "--name",
                        f"borg-{backup_time}",
                        "--raw-json",
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                data = json.loads(result.stdout)

                if data["result"] != "ok":
                    raise RuntimeError("Failed to create Home Assistant backup")

                return data["data"]

        except requests.RequestException as e:
            self.logger.error(f"Failed to create backup via API: {e}")
            raise
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to create Home Assistant backup: {e}")
            if e.stderr:
                self.logger.error(f"Error output: {e.stderr}")
            self.logger.debug(
                f"Available environment variables: {list(os.environ.keys())}"
            )
            raise
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse backup creation response: {e}")
            raise

    def _create_borg_backup(self, backup_time: str, snap_slug: str):
        cmd = [
            "borg",
            "create",
            "--compression",
            f"{self.config.compression},9",
            "--stats",
        ]

        # Add standard exclusions
        standard_excludes = [
            "*.pyc",
            "__pycache__",
            "*.tmp",
            ".*.swp",
            ".*.swo",
            ".*.swn",
        ]

        # Add log exclusions if enabled
        if self.config.exclude_logs:
            log_excludes = [
                "*/home-assistant.log*",
                "*/homeassistant.log*",
                "*/.homeassistant/home-assistant.log*",
                "*/logs/*",
                "*/log/*",
                "*/*.log",
                "*/*.log.*",
                "*/supervisor/logs/*",
                "*/addons/*/logs/*",
            ]
            standard_excludes.extend(log_excludes)

        # Add custom exclusions
        if self.config.custom_excludes:
            custom_patterns = [
                p.strip() for p in self.config.custom_excludes.split(",") if p.strip()
            ]
            standard_excludes.extend(custom_patterns)

        # Add all exclusions to command
        for pattern in standard_excludes:
            cmd.extend(["--exclude", pattern])

        cmd.extend([f"::{backup_time}", f"{self.config.backup_dir}/{snap_slug}"])

        if self.config.debug:
            cmd.insert(1, "--debug")

        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Borg backup creation failed: {e}")
            raise

    def _cleanup_old_backups(self):
        try:
            supervisor_token = os.environ.get("SUPERVISOR_TOKEN")

            if supervisor_token:
                # Use direct API calls
                headers = {
                    "Authorization": f"Bearer {supervisor_token}",
                    "Content-Type": "application/json",
                }

                # Get list of backups
                response = requests.get("http://supervisor/backups", headers=headers)
                if response.status_code != 200:
                    raise RuntimeError(
                        f"Failed to get backup list: {response.status_code}"
                    )

                data = response.json()
                backups = data["data"]["backups"]

                # Sort backups by date and get ones to remove
                backups.sort(key=lambda x: x["date"])
                to_remove = (
                    backups[: -self.config.keep_snapshots]
                    if len(backups) > self.config.keep_snapshots
                    else []
                )

                # Remove old backups
                for backup in to_remove:
                    self.logger.info(
                        f"Removing backup {backup['name']} ({backup['slug']})"
                    )
                    response = requests.delete(
                        f"http://supervisor/backups/{backup['slug']}", headers=headers
                    )
                    if response.status_code != 200:
                        self.logger.error(
                            f"Failed to remove backup {backup['slug']}: {response.status_code}"
                        )

            else:
                # Fallback to ha commands
                self.logger.warning(
                    "SUPERVISOR_TOKEN not available, using ha command fallback"
                )
                subprocess.run(["ha", "backup", "reload"], check=True)

                result = subprocess.run(
                    ["ha", "backup", "--raw-json"],
                    capture_output=True,
                    text=True,
                    check=True,
                )

                data = json.loads(result.stdout)
                backups = data["data"]["backups"]

                # Sort backups by date and get ones to remove
                backups.sort(key=lambda x: x["date"])
                to_remove = (
                    backups[: -self.config.keep_snapshots]
                    if len(backups) > self.config.keep_snapshots
                    else []
                )

                # Remove old backups
                for backup in to_remove:
                    self.logger.info(
                        f"Removing backup {backup['name']} ({backup['slug']})"
                    )
                    subprocess.run(
                        ["ha", "backup", "remove", backup["slug"]], check=True
                    )

        except Exception as e:
            self.logger.error(f"Failed to cleanup old backups: {e}")
            raise

    def _cleanup_temp_files(self):
        try:
            if Path(self.config.backup_dir).exists():
                shutil.rmtree(self.config.backup_dir)
        except Exception as e:
            self.logger.error(f"Failed to cleanup temporary files: {e}")


def main():
    backup = BorgBackup()
    backup.create_backup()


if __name__ == "__main__":
    main()
# 1
