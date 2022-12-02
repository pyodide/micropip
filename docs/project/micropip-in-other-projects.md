# micropip in Other Projects

(micropip-jupyterlite)=

## Jupyterlite

In [Jupyterlite](https://jupyter.org/try-jupyter/lab/),
a package called [piplite](https://jupyterlite.readthedocs.io/en/latest/howto/python/packages.html#installing-packages-at-runtime) is provided, which is a layer
on top of micropip.

```python
import piplite
await piplite.install("snowballstemmer")
```

(micropip-pyscript)=

## PyScript

In [PyScript](https://pyscript.net/),
packages listed in `<py-config>` will be installed via micropip.

```html
<py-config>
packages = [
  "numpy",
  "matplotlib"
]
</py-config>
```
