#!/usr/bin/env python3

import os
import sys
from backup import BorgBackup
from restore import BorgRestore


def main():
    # Check if restore mode is requested
    restore_mode = os.environ.get("RESTORE_MODE", "false").lower() == "true"

    if restore_mode:
        restore = BorgRestore()
        restore.restore_backup()
    else:
        backup = BorgBackup()
        backup.create_backup()


if __name__ == "__main__":
    main()
