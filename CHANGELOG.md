# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Support for adding mock packages, for use where something is a dependency and you don't need it, or you need only a limited subset of the package. This is done using `micropip.add_mock_package`, `micropip.remove_mock_package` and `micropip.list_mock_packages`. Packages installed like this will be skipped by dependency resolution when you later install real packages.

## [0.1.0] - 2022/09/18

Initial standalone release. For earlier release notes, see
the [Pyodide project changelog](https://pyodide.org/en/stable/project/changelog.html).
