# API Reference

```{eval-rst}
.. automodule:: micropip
    :members:
    :undoc-members:
    :member-order: bysource
```

## Customization

See {ref}`customizing-micropip` for examples.

```{eval-rst}
.. autoclass:: micropip.compat.CompatibilityLayer
    :members:
    :member-order: bysource

.. py:currentmodule:: micropip.compat

.. class:: PyodideCompatibilityLayer

    The default :py:class:`~micropip.compat.CompatibilityLayer`, used in Pyodide.
    Subclass it to change part of the default behavior, e.g. ``fetch_bytes``.
    It can only be imported in Pyodide.

.. autoclass:: micropip.resolver.Resolver
    :members: query_package, find_wheel, download_wheel, download_wheel_metadata, fetch_bytes
    :member-order: bysource

.. autoclass:: micropip.installer.Installer
    :members:
    :member-order: bysource
```
