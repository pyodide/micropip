(basic-usage)=

# Basic Usage

(installing-packages-with-micropip)=

## Installing packages with micropip

micropip can install following types of packages:

1. Pure Python packages

Pure Python packages are packages that do not have any compiled code.
Most pure Python packages can be installed directly from PyPI with {any}`micropip.install`
if they have a pure Python wheel. Check if this is the case by trying `micropip.install("package-name")`.

2. Python packages that contain C-extensions

If a package has C-extensions (or any other compiled codes like Rust),
it will not have a pure Python wheel on PyPI.

Trying to install such a package with {any}`micropip.install` will result in an error like:

```
ValueError: Can't find a pure Python 3 wheel for 'tensorflow'.
See: https://pyodide.org/en/stable/usage/faq.html#micropip-can-t-find-a-pure-python-wheel
You can use `await micropip.install(..., keep_going=True)` to get a list of all packages with missing wheels.
```

To install such a package, you need to first build a Python wheels for WASM/Emscripten for it.

Note that pyodide provides several commonly used packages with pre-built wheels.
Those packages can be installed with `micropip.install("package-name")`.

```{note}
You can find a list of packages with pre-built wheels in the
[Pyodide documentation](https://pyodide.org/en/stable/usage/packages-in-pyodide.html).
If your package is not in the list, you can build a wheel for it yourself.
See the [Building packages](https://pyodide.org/en/stable/development/new-packages.html) section of the Pyodide documentation for more information.
```


### Examples

```python
import micropip

# snoballstemmer is a pure Python package
# and has a pure Python wheel on PyPI
# so it can be installed directly
await micropip.install("snowballstemmer")

# numpy is a package that has C-extensions
# and does not have a pure Python wheel on PyPI
# but it is provided by Pyodide
await micropip.install("numpy")

# It is also possible to install from
# - arbitrary URLs
await micropip.install("https://.../package.whl")
# - local files inside the Pyodide virtual file system
await micropip.install("emfs://.../package.whl")
```


## Advanced usage

You can pass multiple packages to `micropip.install`:

```python
await micropip.install(["pkg1", "pkg2"])
```

A dependency can be refined as per the [PEP-508] spec:

[pep-508]: https://peps.python.org/pep-0508

```python
await micropip.install("snowballstemmer==2.2.0")
await micropip.install("snowballstemmer>=2.2.0")
await micropip.install("snowballstemmer @ https://.../snowballstemmer.*.whl")
await micropip.install("snowballstemmer[all]")
```

### Disabling dependency resolution

micropip does dependency resolution by default, but you can disable it,
this is useful if you want to install a package that has a dependency
which is not a pure Python package, but it is not mandatory for your use case:

```python
await micropip.install("pkg", deps=False)
```

### Constraining indirect dependencies

Dependency resolution can be further customized with optional `constraints`:
these modify both _direct_ and _indirect_ dependency resolutions, while direct URLs
in either a requirement or constraint will generally bypass any other specifiers.

As described in the [`pip` documentation][pip-constraints], each constraint:

[pip-constraints]: https://pip.pypa.io/en/stable/user_guide/#constraints-files

  - _must_ provide a name
  - _must_ provide exactly one of
    - a set of version specifiers
    - a URL
  - _must not_  request any `[extras]`

Invalid constraints will be silently discarded, or logged if `verbose` is provided.

```python
await micropip.install(
    "pkg",
    constraints=[
        "other-pkg==0.1.1",
        "some-other-pkg<2",
        "yet-another-pkg@https://example.com/yet_another_pkg-0.1.2-py3-none-any.whl",
        # silently discarded                          # why?
        "yet_another_pkg-0.1.2-py3-none-any.whl",     # missing name
        "something-completely[different] ==0.1.1",    # extras
        "package-with-no-version",                    # missing version or URL
    ]
)
```

Over-constrained requirements will fail to resolve, leaving the environment unmodified.

```python
await micropip.install("pkg ==1", constraints=["pkg ==2"])
# ValueError: Can't find a pure Python 3 wheel for 'pkg==1,==2'.
```

### Setting default constraints

`micropip.set_constraints` replaces any default constraints for all subsequent
calls to `micropip.install` that don't specify `constraints`:

```python
micropip.set_constraints(["other-pkg ==0.1.1"])
await micropip.install("pkg")                         # uses defaults, if needed
await micropip.install("another-pkg", constraints=[]) # ignores defaults
```
