#!/usr/bin/env python3

import os
import sys
import json
import logging
import subprocess
import multiprocessing
import psutil
import requests
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime


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


class BorgCommon:
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
        """Detect system capabilities for optimizing backup performance."""
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
        # Validate repository configuration
        if not config.repo_url and not config.host:
            raise ValueError("Either 'borg_repo_url' or 'borg_host' must be defined")
        if config.repo_url and config.host:
            raise ValueError("Cannot define both 'borg_repo_url' and 'borg_host'")
        if config.host and not config.reponame:
            raise ValueError("When using borg_host, borg_reponame must be defined")

        # Validate compression algorithm
        valid_compressions = ["none", "lz4", "zstd", "zlib", "lzma"]
        if config.compression and config.compression not in valid_compressions:
            self.logger.warning(
                f"Invalid compression algorithm '{config.compression}'. "
                f"Using default 'zstd'. Valid options are: {', '.join(valid_compressions)}"
            )
            config.compression = "zstd"

        # Validate keep_snapshots range
        if config.keep_snapshots < 1:
            self.logger.warning(
                f"Invalid keep_snapshots value: {config.keep_snapshots}. "
                "Setting to minimum value of 1."
            )
            config.keep_snapshots = 1

        # Construct repository URL if using host+reponame format
        if config.host and not config.repo_url:
            user_prefix = f"{config.user}@" if config.user else ""
            config.repo_url = f"{user_prefix}{config.host}:{config.reponame}"

        # Warn about security implications
        if not config.passphrase:
            self.logger.warning(
                "No passphrase configured! Your backups will NOT be encrypted. "
                "This is a security risk. Please set 'borg_passphrase' in your configuration."
            )

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

    def init_borg_repo(self):
        """Initialize Borg repository with encryption if it doesn't exist."""
        # First, try to check if repository exists and is accessible
        if self._check_repo_exists():
            return

        # Initialize new repository
        self._initialize_new_repo()

    def _check_repo_exists(self) -> bool:
        """Check if repository exists and is accessible."""
        try:
            cmd = ["borg", "info"]
            if self.config.debug:
                cmd.append("--debug")
            cmd.append(self.config.repo_url)

            result = subprocess.run(cmd, capture_output=True, text=True, env=os.environ)

            if result.returncode == 0:
                self.logger.info("Repository exists and is accessible")
                return True
            elif (
                "passphrase" in result.stderr.lower()
                or "authentication" in result.stderr.lower()
            ):
                if not self.config.passphrase:
                    raise ValueError(
                        "Repository exists but requires a passphrase. "
                        "Please set 'borg_passphrase' in your addon configuration."
                    )
                else:
                    raise ValueError(
                        "Repository exists but passphrase authentication failed. "
                        "Please check your 'borg_passphrase' configuration."
                    )
            elif "does not exist" in result.stderr.lower() or result.returncode == 2:
                # Repository doesn't exist, we can initialize it
                self.logger.info("Repository does not exist, will initialize")
                return False
            else:
                # Some other error
                self.logger.warning(f"Repository check failed: {result.stderr}")
                return False

        except subprocess.CalledProcessError as e:
            self.logger.warning(f"Could not check repository status: {e}")
            return False

    def _initialize_new_repo(self):
        """Initialize a new Borg repository."""
        config_path = Path(self.config.base_dir) / ".config/borg/security"

        if not config_path.exists():
            if self.config.passphrase:
                self.logger.info("Initializing backup repository with encryption")
                cmd = ["borg", "init", "--encryption=repokey-blake2"]
            else:
                self.logger.warning(
                    "Initializing backup repository WITHOUT encryption (not recommended)"
                )
                cmd = ["borg", "init", "--encryption=none"]

            if self.config.debug:
                cmd.append("--debug")

            cmd.append(self.config.repo_url)

            try:
                subprocess.run(cmd, check=True, env=os.environ)
                if self.config.passphrase:
                    self.logger.info(
                        "Repository initialized successfully with encryption"
                    )
                else:
                    self.logger.warning("Repository initialized without encryption")
            except subprocess.CalledProcessError as e:
                self.logger.error(f"Failed to initialize repository: {e}")
                raise

    def repair_repository(self):
        """Attempt to repair a corrupted repository."""
        self.logger.warning("Attempting to repair repository...")

        try:
            cmd = ["borg", "check", "--repair"]
            if self.config.debug:
                cmd.append("--debug")
            cmd.append(self.config.repo_url)

            subprocess.run(cmd, check=True, env=os.environ)
            self.logger.info("Repository repair completed successfully")

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Repository repair failed: {e}")
            raise

    def _get_auth_token(self) -> tuple:
        """Get authentication token for Home Assistant API."""
        supervisor_token = os.environ.get("SUPERVISOR_TOKEN")
        hassio_token = os.environ.get("HASSIO_TOKEN")

        self.logger.debug(f"SUPERVISOR_TOKEN available: {bool(supervisor_token)}")
        self.logger.debug(f"HASSIO_TOKEN available: {bool(hassio_token)}")

        if supervisor_token:
            return "SUPERVISOR_TOKEN", supervisor_token
        elif hassio_token:
            return "HASSIO_TOKEN", hassio_token
        else:
            self.logger.warning("No authentication tokens available")
            return None, None

    def publish_entity(self, entity_id: str, state: str, attributes: dict = None):
        """Publish entity state to Home Assistant."""
        # Skip if entity publishing is disabled
        if os.environ.get("PUBLISH_ENTITIES", "true").lower() != "true":
            return False

        for token_name, token_value in [
            ("SUPERVISOR_TOKEN", os.environ.get("SUPERVISOR_TOKEN")),
            ("HASSIO_TOKEN", os.environ.get("HASSIO_TOKEN")),
        ]:
            if not token_value:
                continue

            try:
                headers = {
                    "Authorization": f"Bearer {token_value}",
                    "Content-Type": "application/json",
                }

                payload = {"state": state, "attributes": attributes or {}}

                response = requests.post(
                    f"http://supervisor/core/api/states/{entity_id}",
                    headers=headers,
                    json=payload,
                    timeout=10,
                )

                if response.status_code in [200, 201]:
                    self.logger.debug(f"Published entity {entity_id}: {state}")
                    return True

            except requests.RequestException as e:
                self.logger.warning(f"Failed to publish entity with {token_name}: {e}")

        return False

    def _get_repository_info(self) -> dict:
        """Get repository information for status entities."""
        try:
            cmd = ["borg", "info", "--json"]
            if self.config.debug:
                cmd.append("--debug")
            cmd.append(self.config.repo_url)

            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)

            # Calculate total size in GB
            total_size = data.get("cache", {}).get("stats", {}).get("total_size", 0)
            size_gb = round(total_size / (1024**3), 2)

            # Calculate compression ratio if possible
            original_size = (
                data.get("cache", {}).get("stats", {}).get("original_size", 0)
            )
            compressed_size = (
                data.get("cache", {}).get("stats", {}).get("compressed_size", 0)
            )
            compression_ratio = (
                round(original_size / compressed_size, 2)
                if compressed_size > 0
                else 1.0
            )

            return {
                "size_gb": size_gb,
                "archives": len(data.get("archives", [])),
                "last_modified": data.get("repository", {}).get("last_modified"),
                "compression_ratio": compression_ratio,
            }

        except Exception as e:
            self.logger.warning(f"Could not get repository info: {e}")
            return {}
