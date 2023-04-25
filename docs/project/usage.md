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

You can specify additional constraints:

```python
await micropip.install("snowballstemmer==2.2.0")
await micropip.install("snowballstemmer>=2.2.0")
await micropip.install("snowballstemmer[all]")
```

micropip does dependency resolution by default, but you can disable it,
this is useful if you want to install a package that has a dependency
which is not a pure Python package, but it is not mandatory for your use case:

```python
await micropip.install("pkg", deps=False)
```
