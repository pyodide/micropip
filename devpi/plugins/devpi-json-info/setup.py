from setuptools import setup

setup(
    name="devpi-json-info",
    license="MIT",
    entry_points={"devpi_server": ["devpi-json-info = devpi_json_info"]},
    install_requires=["devpi-server"],
    py_modules=["devpi_json_info"],
)
