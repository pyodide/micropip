FAQ_URLS = {
    "cant_find_wheel": "https://pyodide.org/en/stable/usage/faq.html#why-can-t-micropip-find-a-pure-python-wheel-for-a-package"
}

# https://github.com/pypa/pip/blob/de44d991024ca8a03e9433ca6178f9a5f661754f/src/pip/_internal/resolution/resolvelib/resolver.py#L164-L167
YANKED_WARNING_MESSAGE = (
    "The candidate selected for download or install is a "
    "yanked version: '%s' candidate (version %s "
    "at %s)\nReason for being yanked: %s"
)
