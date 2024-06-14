class Manager:
    """
    Manager provides an extensible interface for customizing micropip's behavior.

    Each Manager instance holds its own local state that is 
    independent of other instances, including the global state.
    """

    def __init__(self):
        pass

    def install(self):
        pass

    def list(self):
        pass

    def freeze(self) -> str:
        pass

    def add_mock_package(self):
        pass

    def list_mock_packages(self):
        pass

    def remove_mock_package(self):
        pass

    def uninstall(self):
        pass

    def set_index_urls(self, urls: list[str] | str) -> None:
        pass
