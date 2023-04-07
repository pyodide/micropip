# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2023/03/29

### Added

- Added `micropip.uninstall` to uninstall packages
  [#55](https://github.com/pyodide/micropip/pull/55)

## [0.2.2] - 2023/03/04

### Fixed

- When there is an invalid version on PyPi (defined as unparsable
  by [`packaging.version.Version`](https://packaging.pypa.io/en/stable/version.html))
  that version is now skipped. Otherwise a single invalid version would
  make the package uninstallable, following removal of `LegacyVersion` in
  [packaging#407](https://github.com/pypa/packaging/pull/407).

### Fixed

## [0.2.1] - 2023/02/20

### Changed

- micropip now depends on packaging>=0.23.0
  [#49](https://github.com/pyodide/micropip/pull/49)

## [0.2.0] - 2022/12/12

### Added

- Support for adding mock packages, for use where something is a dependency and you don't need it, or you need only a limited subset of the package. This is done using `micropip.add_mock_package`, `micropip.remove_mock_package` and `micropip.list_mock_packages`. Packages installed like this will be skipped by dependency resolution when you later install real packages.
  [#26](https://github.com/pyodide/micropip/pull/26)


### Fixed

- When multiple compatible builds for a package exist, the best
  build is now installed, as determined by the order of tags in
  [`packaging.tags.sys_tags`](https://packaging.pypa.io/en/latest/tags.html#packaging.tags.sys_tags).
  For example, if a package has two pure Python wheels, one tagged `py30` and
  another tagged `py35`, the `py35` wheel will now always get installed.
  [#34](https://github.com/pyodide/micropip/pull/34)
- `micropip.install` now supports installing packages by URLs with query parameters
  [#33](https://github.com/pyodide/micropip/pull/33)


## [0.1.0] - 2022/09/18

Initial standalone release. For earlier release notes, see
the [Pyodide project changelog](https://pyodide.org/en/stable/project/changelog.html).
