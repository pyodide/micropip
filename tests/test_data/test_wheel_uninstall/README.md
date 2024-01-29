This directory contains a wheel that is used to test the uninstallation functionality of the micropip.
If something is changed in the wheel, create a new wheel and copy it to the `wheel` directory.

```sh
python -m build
cp dist/test_wheel_uninstall-1.0.0-py3-none-any.whl ../wheel/
```