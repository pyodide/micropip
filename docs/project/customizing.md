# Customizing micropip

The top-level functions ({any}`micropip.install`, {any}`micropip.list`, ...)
cover most uses. This page is for projects that embed micropip and need to
change where packages come from, how files are fetched, or how installation is
reported.

## Clients

A {any}`micropip.Client` has its own index URLs, constraints and compatibility
layer. The top-level functions use {any}`micropip.default_client`, so
changing it changes them too.

```python
import micropip

client = micropip.Client()
client.set_index_urls(["https://example.com/simple", "PYODIDE"])
await client.install("pkg")
```

Installed packages are shared by all clients: they all install into the same
Python environment.

## Package sources

`index_urls` lists where packages are looked up, in order (see
{ref}`choosing-package-indexes` for URLs and the `"PYPI"` and `"PYODIDE"`
special values). Entries can also be {any}`micropip.sources.Source` objects, to
look up packages somewhere other than a package index.

A source returns the files of a project as a {any}`micropip.sources.ProjectPage`
(like a Simple JSON API page), or `None` if it doesn't have the project. Use the
`fetch` function it is given, so that the client's compatibility layer and fetch
options apply.

For example, a site can ship one JSON file with the releases of many packages,
in the JSON API format, and use it before the packages that come with Pyodide,
without querying PyPI:

```python
import json

import micropip
from micropip.sources import ProjectPage, Source


class AllJsonSource(Source):
    def __init__(self, url):
        self.url = url
        self.data = None

    async def get_project(self, name, fetch):
        if self.data is None:
            self.data = json.loads((await fetch(self.url)).text())
        project = self.data.get(name)
        if project is None:
            return None
        # Relative file URLs are resolved against the URL of the JSON file
        return ProjectPage.from_json_api(project, base_url=self.url, name=name)


micropip.set_index_urls([AllJsonSource("https://example.com/lite/all.json"), "PYODIDE"])
```

{any}`micropip.sources.ordered_sources` returns the order in which the sources of
a list of index URLs are searched, for example to implement another resolver
that follows the same rules.

## Compatibility layers

A {any}`micropip.compat.CompatibilityLayer` connects micropip to the runtime:
fetching files, installing wheels, and the lock file of packages the runtime can
load directly. Pass one to `Client(compat=...)`. In Pyodide, subclass
`micropip.compat.PyodideCompatibilityLayer` to change only part of it.

Caching downloads:

```python
import micropip
from micropip.compat import PyodideCompatibilityLayer


class CachedCompatibilityLayer(PyodideCompatibilityLayer):
    def __init__(self):
        super().__init__()
        self.cache = {}

    async def fetch(self, url, options):
        if url not in self.cache:
            self.cache[url] = await super().fetch(url, options)
        return self.cache[url]


client = micropip.Client(compat=CachedCompatibilityLayer())
await client.install("snowballstemmer")
```

{any}`micropip.compat.FetchOptions` carries the options of a request. Its `extra`
field is passed to the runtime's fetch function as is, e.g. to bypass the
browser cache:

```python
import dataclasses


class NoCacheCompatibilityLayer(PyodideCompatibilityLayer):
    async def fetch(self, url, options):
        options = dataclasses.replace(options, extra={**options.extra, "cache": "no-store"})
        return await super().fetch(url, options)
```

### Lock files

A compatibility layer's `lockfile` is a {any}`micropip.compat.LockFile`: packages
that can be loaded without looking them up on an index (in Pyodide, the
`pyodide-lock.json` it was loaded with). Implement one to use another format, or
set `lockfile = None` to always use the package indexes (then
{any}`micropip.freeze` raises `RuntimeError`).

```python
from micropip.compat import LockedPackage, LockFile, PyodideCompatibilityLayer


class MyLockFile(LockFile):
    def __init__(self, packages):
        self.packages = packages  # name -> LockedPackage

    def __iter__(self):
        return iter(self.packages.values())

    def get(self, name):
        return self.packages.get(name)

    async def load(self, names):
        ...  # load the packages into the runtime
        return names  # the names that are loaded now

    def freeze(self):
        ...  # a lock file in the same format, with the installed packages


class NoLockFileLayer(PyodideCompatibilityLayer):
    def __init__(self):
        super().__init__()
        self.lockfile = None
```

## Resolving and installing separately

{any}`micropip.Client.install` is {any}`micropip.Client.resolve` followed by
{any}`micropip.Client.install_resolution`. Calling them separately lets you look at
what will be installed, install what can be installed when some requirements
fail, and report progress per package:

```python
client = micropip.default_client

resolution = await client.resolve(["pkg-a", "pkg-b"], keep_going=True)
for requirement in resolution.failed:
    print(f"Can't install {requirement}")

async for result in client.install_resolution(resolution):
    if result.ok:
        print(f"Installed {result.name} {result.version} from {result.source}")
    else:
        print(f"Failed to install {result.name}: {result.error}")
```

`resolution.requested_by` maps each package to install (by canonicalized name) to
the top-level requirements, as written, that pulled it in. Wheels are downloaded
by `install_resolution()`; `resolve()` only fetches their metadata when the index
provides it.

## Replacing the resolver or the installer

Pass `resolver` or `installer` to {any}`micropip.Client`. To change one step,
subclass {any}`micropip.resolver.Resolver` or
{any}`micropip.installer.Installer`:

```python
from micropip.resolver import Resolver


class LoggingResolver(Resolver):
    async def query_package(self, name, index_urls=None):
        print(f"Looking up {name}")
        return await super().query_package(name, index_urls)


client = micropip.Client(resolver=LoggingResolver)
```

`resolver` and `installer` are factories, called as `resolver(compat_layer, request)`
and `installer(compat_layer)`. To pass settings to a subclass, use
{py:func}`functools.partial`:

```python
client = micropip.Client(resolver=functools.partial(MyResolver, setting="..."))
```

A different resolver only needs the same contract: the factory is called
with `(compat_layer, request)`, where `request` is a
{any}`micropip.resolution.ResolveRequest`, and its `async resolve()` returns a
{any}`micropip.resolution.Resolution`. The request includes the installed
packages, so the resolver doesn't need to read the environment.
