#!/usr/bin/env python3

import os
import sys
import json
import shutil
import subprocess
import requests
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from common import BorgCommon


class BorgRestore(BorgCommon):
    def __init__(self):
        super().__init__()
        self._publish_restore_entities()

    def _publish_restore_entities(self):
        """Publish restore-specific entities."""
        # Update main status sensor
        self.publish_entity(
            "sensor.borg_backup_status",
            "restore_mode",
            {
                "friendly_name": "Borg Backup Status",
                "icon": "mdi:backup-restore",
                "mode": "restore",
            },
        )

        # Try to get available backups
        try:
            self.init_borg_repo()
            backups = self.list_available_backups()
            backup_list = [b["name"] for b in backups] if backups else []

            self.publish_entity(
                "sensor.borg_available_backups",
                str(len(backup_list)),
                {
                    "friendly_name": "Available Borg Backups",
                    "icon": "mdi:backup-restore",
                    "backup_list": backup_list,
                    "latest_backup": backup_list[0] if backup_list else None,
                },
            )

            self.publish_entity(
                "binary_sensor.borg_backup_available",
                "on" if backup_list else "off",
                {
                    "friendly_name": "Borg Backup Available",
                    "icon": "mdi:check-circle",
                    "device_class": "connectivity",
                },
            )
        except Exception as e:
            self.logger.warning(f"Could not list backups for entity publishing: {e}")
            self.publish_entity(
                "sensor.borg_available_backups",
                "0",
                {
                    "friendly_name": "Available Borg Backups",
                    "icon": "mdi:backup-restore",
                    "error": str(e),
                },
            )

            self.publish_entity(
                "binary_sensor.borg_backup_available",
                "off",
                {
                    "friendly_name": "Borg Backup Available",
                    "icon": "mdi:check-circle",
                    "device_class": "connectivity",
                    "error": str(e),
                },
            )

    def restore_backup(self):
        """Restore a backup from Borg repository."""
        try:
            self.publish_entity(
                "sensor.borg_backup_status",
                "restoring",
                {"progress": "Starting restore process..."},
            )

            # Ensure repository is accessible
            try:
                self.init_borg_repo()
            except ValueError as e:
                self.logger.error(str(e))
                self._publish_error_status(str(e))
                sys.exit(1)
            except Exception as e:
                self.logger.error(f"Repository access failed: {e}")
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

            # List available backups
            self.publish_entity(
                "sensor.borg_backup_status",
                "listing_backups",
                {"progress": "Listing available backups..."},
            )

            backups = self.list_available_backups()
            if not backups:
                error_msg = "No backups found in the repository"
                self.logger.error(error_msg)
                self._publish_error_status(error_msg)
                sys.exit(1)

            # Get backup to restore
            backup_to_restore = self._select_backup_to_restore(backups)
            if not backup_to_restore:
                error_msg = "No valid backup selected for restoration"
                self.logger.error(error_msg)
                self._publish_error_status(error_msg)
                sys.exit(1)

            # Extract from Borg
            self.publish_entity(
                "sensor.borg_backup_status",
                "extracting",
                {"progress": f"Extracting backup {backup_to_restore}..."},
            )

            extracted_path = self.extract_from_borg(backup_to_restore)
            if not extracted_path:
                error_msg = "Failed to extract backup from Borg repository"
                self.logger.error(error_msg)
                self._publish_error_status(error_msg)
                sys.exit(1)

            # Restore to Home Assistant
            self.publish_entity(
                "sensor.borg_backup_status",
                "restoring_to_ha",
                {"progress": "Restoring to Home Assistant..."},
            )

            restore_result = self.restore_to_ha(extracted_path)

            if restore_result:
                self.publish_entity(
                    "sensor.borg_backup_status",
                    "restore_completed",
                    {
                        "restored_backup": backup_to_restore,
                        "completed_at": datetime.now().isoformat(),
                    },
                )
            else:
                self._publish_error_status("Failed to restore backup to Home Assistant")

        except Exception as e:
            self.logger.error(f"Restore operation failed: {e}")
            self._publish_error_status(f"Restore operation failed: {e}")
            sys.exit(1)
        finally:
            self._cleanup_temp_files()

    def _publish_error_status(self, error_message: str):
        """Publish error status."""
        self.publish_entity(
            "sensor.borg_backup_status",
            "restore_error",
            {"error_message": error_message, "last_error": datetime.now().isoformat()},
        )

    def list_available_backups(self) -> List[Dict[str, Any]]:
        """List available backups in the Borg repository."""
        self.logger.info("Listing available backups in repository...")

        cmd = ["borg", "list", "--json"]
        if self.config.debug:
            cmd.append("--debug")
        cmd.append(self.config.repo_url)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            data = json.loads(result.stdout)
            archives = data.get("archives", [])

            # Format the output for display
            formatted_backups = []
            for archive in archives:
                # Parse the timestamp
                timestamp = datetime.strptime(archive["time"], "%Y-%m-%dT%H:%M:%S.%f")

                formatted_backups.append(
                    {
                        "name": archive["name"],
                        "time": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                        "size": self._format_size(
                            archive.get("stats", {}).get("original_size", 0)
                        ),
                        "raw_time": archive["time"],  # Keep the original for sorting
                    }
                )

            # Sort by time, newest first
            formatted_backups.sort(key=lambda x: x["raw_time"], reverse=True)

            # Display the backups
            if formatted_backups:
                self.logger.info(f"Found {len(formatted_backups)} backups:")
                for i, backup in enumerate(formatted_backups):
                    self.logger.info(
                        f"{i+1}. {backup['name']} ({backup['time']}, {backup['size']})"
                    )
            else:
                self.logger.warning("No backups found in repository")

            return formatted_backups

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to list backups: {e}")
            self.logger.error(f"Error output: {e.stderr}")
            return []
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse backup list: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Unexpected error listing backups: {e}")
            return []

    def _format_size(self, size_bytes: int) -> str:
        """Format size in bytes to human-readable format."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes/1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes/(1024*1024):.1f} MB"
        else:
            return f"{size_bytes/(1024*1024*1024):.2f} GB"

    def _select_backup_to_restore(self, backups: List[Dict[str, Any]]) -> Optional[str]:
        """Select which backup to restore."""
        # Check if BACKUP_NAME environment variable is set
        backup_name = os.environ.get("BACKUP_NAME")

        if backup_name:
            self.logger.info(f"Using specified backup name: {backup_name}")
            # Verify the backup exists
            for backup in backups:
                if backup["name"] == backup_name:
                    return backup_name

            self.logger.error(
                f"Specified backup '{backup_name}' not found in repository"
            )
            return None

        # Check if BACKUP_INDEX environment variable is set
        backup_index = os.environ.get("BACKUP_INDEX")

        if backup_index:
            try:
                index = int(backup_index) - 1  # Convert to 0-based index
                if 0 <= index < len(backups):
                    selected_backup = backups[index]["name"]
                    self.logger.info(
                        f"Using backup at index {backup_index}: {selected_backup}"
                    )
                    return selected_backup
                else:
                    self.logger.error(
                        f"Backup index {backup_index} out of range (1-{len(backups)})"
                    )
                    return None
            except ValueError:
                self.logger.error(f"Invalid backup index: {backup_index}")
                return None

        # If no environment variables set and we have backups, use the most recent one
        if backups:
            selected_backup = backups[0]["name"]
            self.logger.info(f"Using most recent backup: {selected_backup}")
            return selected_backup

        return None

    def extract_from_borg(self, archive_name: str) -> Optional[Path]:
        """Extract a backup from Borg repository."""
        extract_dir = Path(self.config.backup_dir) / "restore"
        extract_dir.mkdir(parents=True, exist_ok=True)

        self.logger.info(f"Extracting backup '{archive_name}' from repository...")

        cmd = ["borg", "extract"]
        if self.config.debug:
            cmd.append("--debug")

        cmd.extend(
            [f"{self.config.repo_url}::{archive_name}", "--directory", str(extract_dir)]
        )

        try:
            subprocess.run(cmd, check=True)
            self.logger.info(f"Successfully extracted backup to {extract_dir}")
            return extract_dir
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to extract backup: {e}")
            return None

    def restore_to_ha(self, extracted_path: Path):
        """Restore the extracted backup to Home Assistant."""
        # Find the backup file in the extracted directory
        backup_files = list(extracted_path.glob("**/*.tar"))

        if not backup_files:
            self.logger.error("No backup files found in extracted directory")
            return False

        # Use the first backup file found
        backup_file = backup_files[0]
        self.logger.info(f"Found backup file: {backup_file}")

        # Copy the backup file to the /backup directory
        target_file = Path("/backup") / backup_file.name
        shutil.copy2(backup_file, target_file)

        self.logger.info(f"Copied backup file to {target_file}")

        # Restore the backup using the Supervisor API
        return self._restore_via_api(target_file.stem)

    def _restore_via_api(self, backup_slug: str) -> bool:
        """Restore a backup using the Supervisor API."""
        # Try both available tokens
        for token_name, token_value in [
            ("SUPERVISOR_TOKEN", os.environ.get("SUPERVISOR_TOKEN")),
            ("HASSIO_TOKEN", os.environ.get("HASSIO_TOKEN")),
        ]:
            if not token_value:
                continue

            self.logger.debug(f"Trying API restore with {token_name}")
            try:
                headers = {
                    "Authorization": f"Bearer {token_value}",
                    "Content-Type": "application/json",
                }

                # Start the restore process
                response = requests.post(
                    f"http://supervisor/backups/{backup_slug}/restore/full",
                    headers=headers,
                    timeout=300,
                )

                self.logger.debug(f"API response status: {response.status_code}")

                if response.status_code == 200:
                    data = response.json()
                    if data["result"] == "ok":
                        self.logger.info(
                            f"Restore initiated successfully using {token_name}"
                        )
                        self.logger.info(
                            "Home Assistant will now restart to complete the restore process"
                        )

                        # Update entity before Home Assistant restarts
                        self.publish_entity(
                            "sensor.borg_backup_status",
                            "restarting",
                            {
                                "message": "Home Assistant is restarting to complete restore",
                                "restored_backup": backup_slug,
                            },
                        )

                        return True
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

        self.logger.error("All API authentication methods failed for restore")
        return False

    def _cleanup_temp_files(self):
        try:
            if Path(self.config.backup_dir).exists():
                shutil.rmtree(self.config.backup_dir)
        except Exception as e:
            self.logger.error(f"Failed to cleanup temporary files: {e}")
