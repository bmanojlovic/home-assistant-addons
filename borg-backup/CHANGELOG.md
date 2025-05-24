# Changelog

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
