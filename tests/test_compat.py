"""
test that function in compati behave the same

"""

import pytest
from pytest_pyodide import run_in_pyodide


@pytest.mark.driver_timeout(10)
def test_404(selenium_standalone_micropip, httpserver, request):
    selenium_standalone_micropip.set_script_timeout(11)

    @run_in_pyodide(packages=["micropip", "packaging"])
    async def _inner_test_404_raise(selenium, url):
        import pytest

        from micropip._compat import HttpStatusError, fetch_string_and_headers

        with pytest.raises(HttpStatusError):
            await fetch_string_and_headers(url, {})

    httpserver.expect_request("/404").respond_with_data(
        "Not found",
        status=404,
        content_type="text/plain",
        headers={"Access-Control-Allow-Origin": "*"},
    )
    url_404 = httpserver.url_for("/404")
    _inner_test_404_raise(selenium_standalone_micropip, url_404)
