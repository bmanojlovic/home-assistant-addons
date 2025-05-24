#!/usr/bin/env python3

import os
import sys
import json
import shutil
import subprocess
import requests
from pathlib import Path
from typing import Dict, Any
from datetime import datetime

from common import BorgCommon


class BorgBackup(BorgCommon):
    def __init__(self):
        super().__init__()
        self._publish_initial_status()

    def _publish_initial_status(self):
        """Publish initial addon status entities."""
        # Main status sensor
        self.publish_entity(
            "sensor.borg_backup_status",
            "idle",
            {
                "friendly_name": "Borg Backup Status",
                "icon": "mdi:backup-restore",
                "device_class": "enum",
            },
        )

        # Last backup sensor
        self.publish_entity(
            "sensor.borg_backup_last",
            "unknown",
            {
                "friendly_name": "Last Borg Backup",
                "icon": "mdi:clock-outline",
                "device_class": "timestamp",
            },
        )

        # Repository info sensor
        self.publish_entity(
            "sensor.borg_backup_repository",
            "unknown",
            {
                "friendly_name": "Borg Repository Info",
                "icon": "mdi:database",
                "unit_of_measurement": "GB",
            },
        )

        # Binary sensor for backup availability
        self.publish_entity(
            "binary_sensor.borg_backup_available",
            "off",
            {
                "friendly_name": "Borg Backup Available",
                "icon": "mdi:check-circle",
                "device_class": "connectivity",
            },
        )

    def create_backup(self):
        """Create a new backup with encryption."""
        try:
            # Update status to running
            self.publish_entity(
                "sensor.borg_backup_status",
                "running",
                {"last_started": datetime.now().isoformat()},
            )

            # Ensure repository is initialized with encryption
            try:
                self.init_borg_repo()
                # Update availability status
                self.publish_entity(
                    "binary_sensor.borg_backup_available",
                    "on",
                    {"last_checked": datetime.now().isoformat()},
                )
            except ValueError as e:
                self.logger.error(str(e))
                self._publish_error_status(str(e))
                sys.exit(1)
            except Exception as e:
                self.logger.error(f"Repository initialization failed: {e}")
                # Try to repair if it's a corruption issue
                if "authentication" in str(e).lower() or "integrity" in str(e).lower():
                    self.publish_entity(
                        "sensor.borg_backup_status",
                        "repairing",
                        {"error_message": str(e)},
                    )
                    try:
                        self.repair_repository()
                        self.init_borg_repo()
                    except Exception as repair_error:
                        self.logger.error(f"Repository repair failed: {repair_error}")
                        self._publish_error_status(
                            f"Repository repair failed: {repair_error}"
                        )
                        sys.exit(1)
                else:
                    self._publish_error_status(str(e))
                    sys.exit(1)

            backup_time = (
                subprocess.check_output(["date", "+%Y-%m-%d-%H:%M"]).decode().strip()
            )

            # Update progress
            self.publish_entity(
                "sensor.borg_backup_status",
                "creating_ha_backup",
                {"progress": "Creating Home Assistant backup..."},
            )

            self.logger.info("Creating Home Assistant backup")
            result = self._create_ha_backup(backup_time)

            if result:
                snap_slug = result["slug"]

                self.publish_entity(
                    "sensor.borg_backup_status",
                    "unpacking",
                    {"progress": "Unpacking backup..."},
                )

                self.unpack_backup(snap_slug)

                self.publish_entity(
                    "sensor.borg_backup_status",
                    "creating_borg_backup",
                    {"progress": "Creating Borg archive..."},
                )

                self.logger.info("Creating encrypted Borg backup")
                self._create_borg_backup(backup_time, snap_slug)

                self.publish_entity(
                    "sensor.borg_backup_status",
                    "cleaning_up",
                    {"progress": "Cleaning up old backups..."},
                )

                self._cleanup_old_backups()

                # Success - update all entities
                self._publish_success_status(backup_time)

        except Exception as e:
            self.logger.error(f"Backup creation failed: {e}")
            self._publish_error_status(str(e))
            sys.exit(1)
        finally:
            self._cleanup_temp_files()

    def _publish_success_status(self, backup_time: str):
        """Publish successful backup status."""
        now = datetime.now().isoformat()

        self.publish_entity(
            "sensor.borg_backup_status",
            "completed",
            {"last_completed": now, "last_backup_name": backup_time},
        )

        self.publish_entity(
            "sensor.borg_backup_last",
            now,
            {"backup_name": backup_time, "status": "success"},
        )

        # Get repository info
        repo_info = self._get_repository_info()
        if repo_info:
            self.publish_entity(
                "sensor.borg_backup_repository",
                str(repo_info.get("size_gb", 0)),
                {
                    "total_archives": repo_info.get("archives", 0),
                    "last_modified": repo_info.get("last_modified"),
                    "compression_ratio": repo_info.get("compression_ratio"),
                },
            )

    def _publish_error_status(self, error_message: str):
        """Publish error status."""
        self.publish_entity(
            "sensor.borg_backup_status",
            "error",
            {"error_message": error_message, "last_error": datetime.now().isoformat()},
        )

        self.publish_entity(
            "binary_sensor.borg_backup_available", "off", {"last_error": error_message}
        )

    def _create_ha_backup(self, backup_time: str) -> Dict[str, Any]:
        """Create a Home Assistant backup using the Supervisor API."""
        try:
            backup_data = self._create_backup_via_api(backup_time)
            if not backup_data:
                raise RuntimeError("Failed to create Home Assistant backup via API")
            return backup_data
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse backup creation response: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error creating backup: {e}")
            raise

    def _create_backup_via_api(self, backup_time: str) -> Dict[str, Any]:
        """Create backup using the Supervisor API."""
        # Try both available tokens
        for token_name, token_value in [
            ("SUPERVISOR_TOKEN", os.environ.get("SUPERVISOR_TOKEN")),
            ("HASSIO_TOKEN", os.environ.get("HASSIO_TOKEN")),
        ]:
            if not token_value:
                continue

            self.logger.debug(f"Trying API call with {token_name}")
            try:
                headers = {
                    "Authorization": f"Bearer {token_value}",
                    "Content-Type": "application/json",
                }

                backup_data = {
                    "name": f"borg-{backup_time}",
                    "compressed": True,
                }

                response = requests.post(
                    "http://supervisor/backups/new/full",
                    headers=headers,
                    json=backup_data,
                    timeout=300,
                )

                self.logger.debug(f"API response status: {response.status_code}")

                if response.status_code == 200:
                    data = response.json()
                    if data["result"] == "ok":
                        self.logger.info(
                            f"Backup created successfully using {token_name}"
                        )
                        return data["data"]
                    else:
                        self.logger.error(
                            f"API returned error with {token_name}: {data}"
                        )
                else:
                    self.logger.warning(
                        f"API request failed with {token_name}, status {response.status_code}: {response.text}"
                    )
            except requests.RequestException as e:
                self.logger.warning(f"Request failed with {token_name}: {e}")

        raise RuntimeError("All API authentication methods failed")

    def unpack_backup(self, snap_slug: str) -> None:
        """Unpack a Home Assistant backup for processing by Borg."""
        target_dir = Path(self.config.backup_dir) / snap_slug
        target_dir.mkdir(parents=True, exist_ok=True)

        self.logger.info(f"Unpacking backup {snap_slug}")

        # Prepare tar command with parallel decompression if available
        tar_cmd = self._prepare_tar_command()
        tar_cmd.extend(["-xf", f"/backup/{snap_slug}.tar", "-C", str(target_dir)])

        try:
            subprocess.run(tar_cmd, check=True)
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to unpack backup: {e}")
            raise

        # Handle nested archives
        self._process_nested_archives(target_dir)

    def _prepare_tar_command(self) -> list:
        """Prepare tar command with appropriate compression options."""
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
        return tar_cmd

    def _process_nested_archives(self, target_dir: Path) -> None:
        """Process any nested archives found in the unpacked backup."""
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

        # Include repository URL in the archive specification
        cmd.extend(
            [
                f"{self.config.repo_url}::{backup_time}",
                f"{self.config.backup_dir}/{snap_slug}",
            ]
        )

        if self.config.debug:
            cmd.insert(1, "--debug")

        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Borg backup creation failed: {e}")
            raise

    def _cleanup_old_backups(self):
        """Remove old backups based on retention policy using the Supervisor API."""
        try:
            if not self._cleanup_via_api():
                raise RuntimeError("Failed to cleanup old backups via API")
        except Exception as e:
            self.logger.error(f"Failed to cleanup old backups: {e}")
            raise

    def _cleanup_via_api(self) -> bool:
        """Clean up old backups using the Supervisor API."""
        supervisor_token = os.environ.get("SUPERVISOR_TOKEN")
        hassio_token = os.environ.get("HASSIO_TOKEN")

        # Try both tokens for API access
        for token_name, token_value in [
            ("SUPERVISOR_TOKEN", supervisor_token),
            ("HASSIO_TOKEN", hassio_token),
        ]:
            if not token_value:
                continue

            try:
                headers = {
                    "Authorization": f"Bearer {token_value}",
                    "Content-Type": "application/json",
                }

                # Get list of backups
                response = requests.get("http://supervisor/backups", headers=headers)
                if response.status_code != 200:
                    self.logger.warning(
                        f"Failed to get backup list with {token_name}: {response.status_code}"
                    )
                    continue

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
                        f"http://supervisor/backups/{backup['slug']}",
                        headers=headers,
                    )
                    if response.status_code != 200:
                        self.logger.error(
                            f"Failed to remove backup {backup['slug']}: {response.status_code}"
                        )

                return True  # Success

            except requests.RequestException as e:
                self.logger.warning(f"Cleanup failed with {token_name}: {e}")

        raise RuntimeError("All API authentication methods failed for cleanup")

    def _cleanup_temp_files(self):
        try:
            if Path(self.config.backup_dir).exists():
                shutil.rmtree(self.config.backup_dir)
        except Exception as e:
            self.logger.error(f"Failed to cleanup temporary files: {e}")
