#!/usr/bin/env python3

import os
import sys
import json
from backup import BorgBackup
from restore import BorgRestore


def main():
    # Load configuration
    try:
        with open("/data/options.json", "r") as f:
            options = json.load(f)
    except Exception as e:
        print(f"Error loading options: {e}")
        sys.exit(1)

    # Check if restore mode is requested
    restore_mode = options.get("restore_mode", False)

    # Set environment variables for backward compatibility
    if restore_mode:
        os.environ["RESTORE_MODE"] = "true"
        os.environ["BACKUP_NAME"] = options.get("backup_name", "")
        os.environ["BACKUP_INDEX"] = str(options.get("backup_index", 1))

    if restore_mode:
        restore = BorgRestore()
        restore.restore_backup()
    else:
        backup = BorgBackup()
        backup.create_backup()


if __name__ == "__main__":
    main()
