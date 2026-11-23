# API Reference

## Top-level functions

The top-level functions use {any}`micropip.default_client`.

```{eval-rst}
.. automodule:: micropip
    :members:
    :undoc-members:
    :exclude-members: Client
    :member-order: bysource
```

## Client

```{eval-rst}
.. autoclass:: micropip.Client
    :members:
    :member-order: bysource
```

## Resolutions

See {doc}`customizing` for how to use {any}`micropip.Client.resolve` and
{any}`micropip.Client.install_resolution`.

```{eval-rst}
.. automodule:: micropip.resolution
    :members:
    :member-order: bysource
```

## Sources

```{eval-rst}
.. automodule:: micropip.sources
    :members:
    :member-order: bysource
```

## Compatibility layers

```{eval-rst}
.. automodule:: micropip.compat
    :members:
    :member-order: bysource
```

`micropip.compat.PyodideCompatibilityLayer` is the default layer. It can only be
imported in Pyodide, and implements {any}`micropip.compat.CompatibilityLayer`
with `pyfetch`, `pyodide.loadPackage` and the `pyodide-lock.json` that Pyodide
was loaded with. Subclass it to change part of its behavior (see {doc}`customizing`).

## Resolver and installer

```{warning}
These are advanced extension points, used by passing `resolver` / `installer`
to {any}`micropip.Client`. Their methods may change between releases.
```

```{eval-rst}
.. autoclass:: micropip.resolver.Resolver
    :members: resolve, query_package, find_wheel, download_wheel, download_wheel_metadata, fetch_bytes, fetch

.. autoclass:: micropip.installer.Installer
    :members: install, download_wheel, install_wheel, install_pyodide_packages, uninstall
```
