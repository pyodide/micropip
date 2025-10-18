# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## [0.11.0] - 2025/10/18

### Added

- `micropip.install` now supports extras in custom download locations through the `pkg[extras] @ https://example.com/pkg-1.0.0-py3-none-any.whl` syntax.
  [#257](https://github.com/pyodide/micropip/pull/257)

## [0.10.1] - 2025/07/05

### Fixed

- `micropip.freeze()` now updates the URLs inside the lockfile to absolute URLs.
  This behavior is consistent with the `lockfileURL` behavior change in Pyodide 0.28.0.
  [#241](https://github.com/pyodide/micropip/pull/241)

## [0.10.0] - 2025/07/02

### Added

- Added `reinstall` parameter to micropip.install to allow reinstalling
  a package that is already installed
  [#64](https://github.com/pyodide/micropip/pull/64)

### Fixed

- micropip now respects the `yanked` flag in the PyPI Simple API.
  [#208](https://github.com/pyodide/micropip/pull/208)

- Fixed a bug that relative URLs in some custom package indexes were not
  correctly resolved.
  [#230](https://github.com/pyodide/micropip/pull/230)

- When multiple index URLs are given, micropip.install will now ignore CORS error
  when one index URL fails to find a package, and will fallback to the next index URL.
  [#225](https://github.com/pyodide/micropip/pull/225)

## [0.9.0] - 2025/02/01

### Fixed

- Fix a bug that prevented non-standard relative urls to be treated as such
  (the ones that starts with `../` or `./`)
  [#174](https://github.com/pyodide/micropip/pull/174)

- Fixed an error when calling `micropip.install` with `deps=False` is set.
  [#187](https://github.com/pyodide/micropip/pull/187)

### Added

- `micropip` now vendors `pypa/packaging` for better reliability.
  [#178](https://github.com/pyodide/micropip/pull/178)
- `micropip.install` adds optional `constraints`, similar to `pip install -c`,
  which refine the version or direct URLs of requested packages and their
  dependencies. This includes built-in packages, which are now installed after
  any requested or constrained external packages.
  [#181](https://github.com/pyodide/micropip/pull/181)
- `micropip.set_constraints` sets default constraints for later
  calls to `micropip.install` that do not specify constraints.
  [#181](https://github.com/pyodide/micropip/pull/181)

## [0.8.0] - 2024/12/15

### Added

- Added support for PEP-658.
  [#139](https://github.com/pyodide/micropip/pull/139)

## [0.7.2] - 2024/11/26

### Fixed

 - Fix a bug that prevented some wasm32 wheel to be recognized as compatible with pyodide
  [#159](https://github.com/pyodide/micropip/pull/159)

## [0.7.1] - 2024/11/11

### Fixed

- Fixed bug that prevented package installation from `file:` path in Node.js environment.
  [#155](https://github.com/pyodide/micropip/pull/155)

## [0.7.0] - 2024/11/09

### Fixed

- `micropip.install` now works with simple http indexes that use relative
  links when referencing wheels. [#150](https://github.com/pyodide/micropip/pull/150)

### Added

- `micropip.install(index_urls=[...])` parameter now supports the special value
  `"PYPI"` to refer the `http://pypi.org/simple/` index instead of having to
  type the full url.

## [0.6.1] - 2024/10/05

### Fixed

- micropip.install and micropip.uninstall now accepts `verbosity=None`
  which does not overwrite a default log level.
  [#132](https://github.com/pyodide/micropip/pull/132)

- When multiple index urls are given, micropip.install will now correctly
  fallback to the next index url when one index url fails to find a package.
  [#129](https://github.com/pyodide/micropip/pull/129)

## [0.6.0] - 2024/01/31

### Fixed

- micropip.install can now locate shared libraries in `<pkg>.libs` directory.
  This is consistent with the behavior of pyodide.loadpackage.
  [#97](https://github.com/pyodide/micropip/pull/97)

## [0.5.0] - 2023/09/19

### Changed

- When custom index URLs are set by `micropip.set_index_urls` or by `micropip.install(index_urls=...)`,
  micropip will now query packages from the custom index first,
  and then from pyodide lockfile.
  [#83](https://github.com/pyodide/micropip/pull/83)

- Made micropip.freeze correctly list dependencies of manually installed packages.
  [#79](https://github.com/pyodide/micropip/pull/79)

## [0.4.0] - 2023/07/25

### Added

- Added `verbose` parameter to micropip.install and micropip.uninstall
  [#60](https://github.com/pyodide/micropip/pull/60)
- Added `index_urls` parameter to micropip.install to support installing
  from custom package indexes.
  [#74](https://github.com/pyodide/micropip/pull/74)
- Added `micropip.set_index_urls` to support installing from custom package
  indexes.
  [#74](https://github.com/pyodide/micropip/pull/74)
- Added support for Simple API (PEP 503 / PEP 691)
  [#75](https://github.com/pyodide/micropip/pull/75)
### Fixed

- Fixed `micropip.add_mock_package` to work with Pyodide>=0.23.0
  [#66](https://github.com/pyodide/micropip/pull/66)

### Changed

- The default index URL is changed to https://pypi.org/simple
  [#75](https://github.com/pyodide/micropip/pull/75)

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
