# Changelog

## [0.0.10] - 2025-09-15

### Changed

- Update dependencies

## [0.0.9] - 2025-07-28

### Changed

- parser refactoring
- better handling of relogin
- python 3.13 for devcontainer

## [0.0.8] - 2025-01-20

### Added

- Tests
- Test coverage checks

### Fixed

- Set the correct property when "start with minimum current" quirk is enabled

### Changed

- Improved GitHub actions
- Small refactoring
- Update dependencies

## [0.0.7] - 2025-01-17

### Added

- Swedish translations

### Fixed

- Start and stop charge tweaks
- Fix response parsing on charge start command

### Changed

- Warn on bad connector status when stopping a charge

## [0.0.6] - 2025-01-16

### Added

- LED intensity setting

### Fixed

- Force data refresh service

### Changed

- Try starting charge again after reboot, if state is preparing/suspended_evse (with quirks enabled)

## [0.0.5] - 2025-01-15

### Fixed

- Issue with command execution timing
- Datetime timezone handling
- Possibly fixed infinite recursion on status updates

### Changed

- Improved logging for better debugging

## [0.0.4] - 2025-01-14

### Added

- Possibility to send arbitrary commands
- Added all (dynamic) configuration keys as attributes on the connector switches

### Fixed

- Better quirks and options flow
- Reloading should now work

### Changed

- Translations

## [0.0.3] - 2025-01-12

### Added

- Translation strings

### Fixed

- Switch states
- Charge state enum -> translated string

## [0.0.2] - 2025-01-11

### Added

- Max charge current setting

### Fixed

- Kindof working charging switch

### Changed

- Numeric sensors return 0 instead of None
