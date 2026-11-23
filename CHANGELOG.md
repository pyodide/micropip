# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

This release reorganizes micropip around a public `Client`, replaceable
resolvers and installers, and a documented compatibility layer. The module-level
API (`micropip.install`, `micropip.list`, ...) keeps working as before. Projects
that imported micropip internals (e.g. `micropip.transaction`,
`micropip.package_index.query_package` or `micropip._package_manager_singleton`)
need to migrate: see **Removed** below and the *Customizing micropip* page of
the documentation.

### Added

- `micropip.Client`: a micropip client with its own index URLs, constraints and
  compatibility layer.
  [#305](https://github.com/pyodide/micropip/pull/305),
  [#317](https://github.com/pyodide/micropip/pull/317)

- `micropip.compat`: the interface between micropip and the runtime
  (`CompatibilityLayer`, `FetchOptions`, `FetchResponse`, `LockFile`,
  `LockedPackage`), and `PyodideCompatibilityLayer`, the default layer in
  Pyodide. Pass a layer to `Client(compat=...)` to change how micropip fetches
  files, installs wheels, or reads the lock file. A layer may have no lock file
  (`lockfile = None`); then every package is looked up on the indexes and
  `freeze()` raises `RuntimeError`.
  [#302](https://github.com/pyodide/micropip/pull/302),
  [#305](https://github.com/pyodide/micropip/pull/305),
  [#315](https://github.com/pyodide/micropip/pull/315),
  [#321](https://github.com/pyodide/micropip/pull/321),
  [#322](https://github.com/pyodide/micropip/pull/322),
  [#327](https://github.com/pyodide/micropip/pull/327)

- `micropip.sources`: `index_urls` accepts `Source` objects alongside URL
  strings, so packages can be looked up somewhere other than a package index
  (e.g. a single JSON file listing many packages). `ordered_sources()` returns
  the order in which sources are searched.
  [#317](https://github.com/pyodide/micropip/pull/317),
  [#323](https://github.com/pyodide/micropip/pull/323)

- The special value `"PYODIDE"` can be used in `index_urls` (in `install`,
  `set_index_urls` and `Client`) to search the Pyodide lock file at that position.
  For example, `["PYODIDE", "https://example.com/simple", "PYPI"]` searches the
  lock file, then the custom index, then PyPI. Without `"PYODIDE"`, the lock file
  is searched first with the default index, and after custom indexes otherwise,
  as before.
  [#314](https://github.com/pyodide/micropip/pull/314)

- `Client.resolve()` returns what would be installed (`micropip.resolution.Resolution`)
  without installing it, and `Client.install_resolution()` installs it.
  `Client.install` is `resolve` followed by `install_resolution`, and behaves as before.
  [#319](https://github.com/pyodide/micropip/pull/319),
  [#320](https://github.com/pyodide/micropip/pull/320)

- The resolver and the installer can be replaced by subclassing `Client` and
  setting `resolver_class` / `installer_class`.
  [#304](https://github.com/pyodide/micropip/pull/304),
  [#320](https://github.com/pyodide/micropip/pull/320),
  [#328](https://github.com/pyodide/micropip/pull/328)

### Changed

- Resolving only fetches wheel metadata (PEP 658) when the index provides it;
  wheels are downloaded when they are installed. Wheels without separate
  metadata are still downloaded while resolving (to read their metadata), and
  not downloaded again.
  [#324](https://github.com/pyodide/micropip/pull/324)

- A package from the Pyodide lock file that fails to load is now reported as failed, and `install` raises
  `RuntimeError`, instead of printing "Successfully installed".
  [#319](https://github.com/pyodide/micropip/pull/319)

- Outside of Pyodide, `import micropip` still works, but functions that need the
  Pyodide runtime (e.g. `install`, `list`, `freeze`, `uninstall`) raise
  `RuntimeError`.
  [#300](https://github.com/pyodide/micropip/pull/300)

- `install` now raises a helpful `ValueError` when given a VCS URL
  (`git+`, `hg+`, `svn+`, `bzr+`) instead of an opaque parser error,
  explaining that micropip only installs prebuilt wheels.
  [#277](https://github.com/pyodide/micropip/pull/277)

- Updated the vendored `packaging` library from 24.2 to 26.3. This speeds up
  parsing and comparing versions, filtering versions with specifiers, and
  parsing requirements and wheel filenames.
  [#308](https://github.com/pyodide/micropip/pull/308)

### Fixed

- The resolver no longer selects two versions of the same package. A package
  from the lock file needed by several requirements was added once per
  requirement, and a requirement that conflicted with an earlier selection could
  add a second version (e.g. `["fastapi==0.110.0", "starlette>=0.36"]` installed
  two versions of starlette). micropip's resolver doesn't backtrack: it now keeps
  the version selected first and logs a warning naming the unsatisfied
  requirement.
  [#326](https://github.com/pyodide/micropip/pull/326)

- When the PEP 658 metadata file advertised by an index can't be fetched,
  micropip falls back to downloading the wheel, as intended.
  [#324](https://github.com/pyodide/micropip/pull/324)

- Relative file URLs in Simple JSON API (PEP 691) responses are now resolved
  against the index page URL.
  [#317](https://github.com/pyodide/micropip/pull/317)

- The error raised for a wheel URL with an unsupported scheme now says
  "Unexpected URL scheme" and lists the supported schemes, instead of
  "Cannot download from a non-remote location".
  [#312](https://github.com/pyodide/micropip/pull/312)

- Messages from `pyodide.loadPackage` when installing packages from the Pyodide
  lock file now go through micropip's logger instead of always being printed.
  "Loading ..."/"Loaded ..." are shown only with `verbose=True`, and load errors
  are logged as warnings.
  [#309](https://github.com/pyodide/micropip/pull/309)

- `install` now reports a failed wheel download (e.g. HTTP 404) as a fetch error
  instead of an opaque `BadZipFile` error.
  [#298](https://github.com/pyodide/micropip/pull/298)

- `freeze` no longer fails with `PackageNotFoundError` when a package installed
  with `deps=False` has a dependency that is not installed.
  [#307](https://github.com/pyodide/micropip/pull/307)

### Removed

These were internals, but some projects used them. Replacements:

- `micropip.transaction.Transaction` → `micropip.resolver.Resolver`, constructed
  as `Resolver(compat_layer, ResolveRequest(...))`; use `Client.resolve()` and
  `Client.install_resolution()` instead of driving it directly.
  [#303](https://github.com/pyodide/micropip/pull/303),
  [#319](https://github.com/pyodide/micropip/pull/319),
  [#320](https://github.com/pyodide/micropip/pull/320)

- `micropip.package_index.query_package` (and patching it to add a package
  source) → a `micropip.sources.Source` in `index_urls`. `Resolver.query_package`
  remains as an override point. `micropip.package_index` no longer re-exports
  `CompatibilityLayer`; import it from `micropip.compat`.
  [#303](https://github.com/pyodide/micropip/pull/303),
  [#317](https://github.com/pyodide/micropip/pull/317)

- `micropip._package_manager_singleton` → `micropip.default_client`.
  [#317](https://github.com/pyodide/micropip/pull/317)

- The compatibility layer interface changed: `fetch_bytes` and
  `fetch_string_and_headers` → `fetch(url, FetchOptions)`; `lockfile_info`,
  `lockfile_packages`, `lockfile_base_url` and `loadPackage` → a `LockFile`
  (`lockfile`); `loadedPackages` and `to_js` → `loaded_packages()`,
  `add_loaded_package()` and `remove_loaded_package()`. Layers are passed as
  instances, not classes.
  [#302](https://github.com/pyodide/micropip/pull/302),
  [#315](https://github.com/pyodide/micropip/pull/315)

- The `micropip.freeze` module (the pyodide-lock.json writer) is now internal;
  the `micropip.freeze()` function is unchanged.
  [#315](https://github.com/pyodide/micropip/pull/315)

- `WheelInfo.download()` / `download_pep658_metadata()` / `install()` →
  `Resolver.download_wheel()` / `download_wheel_metadata()` and
  `Installer.install_wheel()`.
  [#303](https://github.com/pyodide/micropip/pull/303),
  [#304](https://github.com/pyodide/micropip/pull/304)

## [0.11.1] - 2026/04/02

### Fixed

- Fixed content-type header parsing to handle PyPI mirrors that include charset parameters.
  This improves compatibility with mirrors that return headers like `application/json; charset=utf-8`.
  [#261](https://github.com/pyodide/micropip/pull/261)

### Changed

- micropip now accepts `pyemscripten` platform wheels in addition to `pyodide` platform wheels,
  following the PEP 783 standard.
  [#270](https://github.com/pyodide/micropip/pull/270)

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
