# Changelog

## 1.3.20

### Added
- Added Home Assistant entity integration for native dashboard display
- Added sensor.borg_backup_status entity to show current backup/restore status
- Added sensor.borg_backup_last entity to show last successful backup time
- Added sensor.borg_backup_repository entity with repository statistics
- Added binary_sensor.borg_backup_available to show repository connectivity
- Added sensor.borg_available_backups to show available backups in restore mode
- Added example Lovelace dashboard configurations to documentation
- Added notification automation example for backup status changes

### Changed
- Enhanced backup and restore processes with detailed status updates
- Improved error handling with better status reporting
- Updated documentation with Home Assistant integration examples

## 1.3.16

### Changed
- Renamed addon from "borg based backup for home assistant" to "Borg Backup for Home Assistant" for better clarity and consistency

### Fixed
- Updated README.md automation instructions to remove outdated Almond references
- Improved automation setup instructions with both UI and YAML methods
- Clarified modern Home Assistant automation interface steps

### Documentation
- Enhanced automation section with clearer step-by-step instructions
- Added both graphical UI and YAML configuration examples
- Updated README.md for consistency with DOCS.md
- Added missing encryption section to README.md
- Standardized configuration examples between both documentation files
- Added troubleshooting section to README.md
- Improved clarity on configuration options and SSH key setup
- Added encryption feature to the feature list
- Updated issue tracker URL from home-assistant-borg-backup repository to home-assistant-addons repository
- Corrected support links in both README.md and DOCS.md to point to the main addon repository
- Updated DOCS.md automation section to match README.md with both UI and YAML examples
- Added System Optimization section to DOCS.md for consistency
- Ensured complete consistency between README.md and DOCS.md documentation

## 1.3.15

### Fixed
- Fixed repository authentication issues when accessing existing encrypted repositories
- Added proper validation for repository access and passphrase requirements
- Added repository repair functionality for corrupted repositories
- Improved error messages for repository authentication failures
- Added better handling of encrypted vs unencrypted repository initialization

### Security
- Enhanced warnings when no passphrase is configured
- Better validation of repository access credentials

### Added
- Repository repair functionality for handling corrupted repositories
- More detailed error messages for troubleshooting repository issues

## 1.3.14

### Fixed
- Fixed AppArmor profile to allow netlink raw socket creation for network operations
- Added missing network capabilities (net_raw, net_admin) to AppArmor profile
- Fixed Borg archive command format by including repository URL in archive specification
- Resolved "Invalid location format" error in Borg create command

### Security
- Enhanced AppArmor profile with proper network access permissions while maintaining security

## 1.3.13

### Fixed
- Removed forced BorgBackup version specification to use distribution default version
- Fixed build failures caused by version conflicts with Alpine package repository
- Now uses latest available BorgBackup version from Alpine Linux package manager

## 1.3.12

### Changed
- Updated base images to use Python 3.13 with Alpine 3.21 for latest security patches and performance improvements
- Upgraded from Alpine 3.18 to Alpine 3.21 for better compatibility and security

## 1.3.11

### Fixed
- Fixed S6 service script permissions by adding execute permissions to run and finish scripts
- Resolved "Permission denied" error when S6 tries to spawn the service

## 1.3.10

### Fixed
- Fixed S6 overlay initialization by setting init: false to properly use S6 service structure
- Resolved "can only run as pid 1" error with S6 overlay suexec

## 1.3.9

### Fixed
- Fixed environment variable access by implementing proper S6 overlay service structure
- Added S6 service scripts to properly pass SUPERVISOR_TOKEN and HASSIO_TOKEN to Python process
- Resolved issue where tokens were available in Docker but not accessible to the application

## 1.3.8

### Fixed
- Fixed API authentication by trying both SUPERVISOR_TOKEN and HASSIO_TOKEN
- Added better debugging for API token issues
- Improved error handling with fallback mechanisms for backup creation and cleanup

## 1.3.7

### Fixed
- Fixed Supervisor API authentication by using direct HTTP API calls instead of ha command
- Added fallback to ha command when SUPERVISOR_TOKEN is not available
- Improved error handling for API communication issues

## 1.3.6

### Fixed
- Fixed SUPERVISOR_TOKEN environment variable access by updating hassio_role to manager
- Improved error handling for missing environment variables
- Added debug logging for troubleshooting API access issues

## 1.3.5

### Added
- Added SSH key thumbprint display when using existing SSH key for verification
- Shows fingerprint of existing SSH key on addon startup for easy identification

## 1.3.4

### Fixed
- Fixed Home Assistant API authentication by properly passing SUPERVISOR_TOKEN to `ha` command
- Resolved "No API token provided" error when creating and managing backups

## 1.3.3

### Fixed
- Fixed AppArmor profile to allow network access for Home Assistant API communication
- Resolved issue where `ha` command was blocked from creating backups due to network restrictions

## 1.3.2

### Fixed
- Fixed configuration validation logic for borg_repo_url vs component parts
- Improved error handling for configuration loading

## 1.3.1

### Changed
- Updated Home Assistant Builder to version 2025.03.0 for improved build performance and latest security patches

## 1.3.0

### Added
- Added AppArmor profile for improved security
- Added authentication API support
- Added Codenotary signing
- Added addon_config mapping for custom configuration files
- Added backup integration with Home Assistant
- Added system capability detection for optimized performance

### Changed
- Improved error handling and logging
- Updated base image references to use explicit version tags
- Enhanced documentation with more detailed setup instructions

### Fixed
- Fixed build configuration to use proper version tags

## 1.2.0

### Added
- Added support for custom exclusion patterns
- Added option to exclude log files from backups
- Added parallel compression support for multi-core systems

### Changed
- Improved backup extraction process
- Enhanced error reporting

## 1.1.0

### Added
- Added SSH parameter customization
- Added compression algorithm selection
- Added backup retention policy

### Changed
- Migrated to Python implementation for better error handling
- Improved repository initialization process

## 1.0.0

### Added
- Initial release
- Basic Borg backup functionality
- Support for remote repositories via SSH
- Encryption support
