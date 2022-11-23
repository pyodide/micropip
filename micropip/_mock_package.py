import importlib.abc
import importlib.machinery
import importlib.metadata
import sys
from collections.abc import Callable


class MockDistribution(importlib.metadata.Distribution):
    def __init__(self, file_dict, modules):
        self.file_dict = file_dict
        self.modules = modules

    def read_text(self, filename):
        """Attempt to load metadata file given by the name.
        :param filename: The name of the file in the distribution info.
        :return: The text if found, otherwise None.
        """
        if filename in self.file_dict:
            return self.file_dict[filename]
        else:
            return None

    def locate_file(self, path):
        """
        Given a path to a file in this distribution, return a path
        to it.
        """
        return None


_mock_modules: "dict[str,str|Callable]" = {}
_mock_distributions: dict[str, MockDistribution] = {}


class _MockModuleFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def __init__(self):
        pass

    def find_distributions(self, context):
        if context.name in _mock_distributions:
            return [_mock_distributions[context.name]]
        elif context.name is None:
            return _mock_distributions.values()
        else:
            return []

    def find_module(self, fullname, path=None):
        spec = self.find_spec(fullname, path)
        if spec is None:
            return None
        return spec

    def create_module(self, spec):
        # let the default module creation occur
        return None

    def exec_module(self, module):
        init_object = _mock_modules[module.__name__]
        if isinstance(init_object, str):
            # run module init code in the module
            exec(init_object, module.__dict__)
        elif callable(init_object):
            # run module init function
            init_object(module)

    def find_spec(self, fullname, path=None, target=None):
        if fullname not in _mock_modules.keys():
            return None

        spec = importlib.machinery.ModuleSpec(fullname, self)
        return spec


_finder = _MockModuleFinder()
sys.meta_path = [_finder] + sys.meta_path


def add_in_memory_distribution(name, metafiles, modules):
    _mock_distributions[name] = MockDistribution(metafiles, modules)
    for name, obj in modules.items():
        _add_mock_module(name, obj)


def _add_mock_module(name, obj):
    _mock_modules[name] = obj


def remove_in_memory_distribution(name):
    if name in _mock_distributions:
        for module in _mock_distributions[name].modules.keys():
            del _mock_modules[module]
        del _mock_distributions[name]