# micropip

[![PyPI Latest Release](https://img.shields.io/pypi/v/micropip.svg)](https://pypi.org/project/micropip/)
![GHA](https://github.com/pyodide/micropip/actions/workflows/main.yml/badge.svg)

A lightweight Python package installer for the web

## Installation

In [Pyodide](https://pyodide.org), you can install micropip,
 - either implicitly by importing it in the REPL
 - or explicitly via `pyodide.loadPackage('micropip')`. You can also install by URL from PyPI for instance.

## Usage

```py
import micropip
await micropip.install(<list-of-packages>)
```
For more information see the
[documentation](https://pyodide.org/en/stable/usage/loading-packages.html#micropip).

## License

micropip uses the [Mozilla Public License Version
2.0](https://choosealicense.com/licenses/mpl-2.0/).
