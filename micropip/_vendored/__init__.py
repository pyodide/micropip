# micropip/_vendored/__init__.py

# This is a proxy file that redirects imports from micropip._vendored.packaging
# to the actual packaging API present in the packaging/src/packaging directory
# next to this file.

import importlib.util
import sys
import types
from pathlib import Path

PACKAGING_PATH = Path(__file__).parent / "packaging" / "src" / "packaging"


def _create_module(name, package_path=None):
    """
    Creates a module object for the given name and makes it available both under
    micropip._vendored.packaging and packaging namespaces.

    Args:
        name: The name of the module (without the full package path)
        package_path: Optional path to the module file, if different from default location
    """
    vendored_name = f"micropip._vendored.packaging.{name}"
    direct_name = f"packaging.{name}"

    # If the module is already in sys.modules, return it, and we
    # add it to sys.modules under both names before executing it.
    if vendored_name in sys.modules:
        return sys.modules[vendored_name]

    module = types.ModuleType(vendored_name)
    module.__package__ = "micropip._vendored.packaging"

    sys.modules[vendored_name] = module
    sys.modules[direct_name] = module

    if package_path is None:
        module_path = PACKAGING_PATH / f"{name}.py"
    else:
        module_path = package_path

    if module_path.exists():
        spec = importlib.util.spec_from_file_location(
            vendored_name, module_path, submodule_search_locations=[str(PACKAGING_PATH)]
        )
        module.__spec__ = spec
        module.__file__ = str(module_path)
        loader = spec.loader
        loader.exec_module(module)

    return module


####################################################

packaging_vendored = types.ModuleType("micropip._vendored.packaging")
packaging_direct = types.ModuleType(
    "packaging"
)  # this is where we redirect the imports.

packaging_vendored.__path__ = [str(PACKAGING_PATH)]
packaging_vendored.__package__ = "micropip._vendored"
packaging_direct.__path__ = [str(PACKAGING_PATH)]
packaging_direct.__package__ = ""

sys.modules["micropip._vendored.packaging"] = packaging_vendored
sys.modules["packaging"] = packaging_direct

####################################################

# 1. First, handle any packages: these are directories with __init__.py.
# 2. Then, we load all the internal modules
# 3. Finally, we'll load all the regular modules (whatever is in the
# public API)
#
# While rudimentary, this order is important because the internal modules
# may depend on subpackages, and regular modules may depend on internal ones.
#
# For example, the metadata.py module imports from licenses, requirements,
# specifiers, and utils.
#
# Similarly, tags.py needs _manylinux and _musllinux to be available.


for path in PACKAGING_PATH.glob("*/__init__.py"):
    package_name = path.parent.name
    module = _create_module(f"{package_name}/__init__", path)
    setattr(packaging_vendored, package_name, module)
    setattr(packaging_direct, package_name, module)

internal_modules = [path.stem for path in PACKAGING_PATH.glob("_*.py")]
for name in internal_modules:
    module = _create_module(name)
    setattr(packaging_vendored, name, module)
    setattr(packaging_direct, name, module)


for path in PACKAGING_PATH.glob("*.py"):
    if path.stem == "__init__" or path.stem.startswith("_"):
        continue

    module = _create_module(path.stem)
    setattr(packaging_vendored, path.stem, module)
    setattr(packaging_direct, path.stem, module)


globals()["packaging"] = packaging_vendored
