import requests


def _check_cors(response):
    assert "Access-Control-Allow-Origin" in response.headers
    assert response.headers["Access-Control-Allow-Origin"] == "*"


def test_nginx_healthcheck(devpi):
    response = requests.get(f"{devpi}/health")
    assert response.status_code == 200

    assert response.json() == {"message": "healthy"}


def test_devpi_root_url(devpi):
    response = requests.get(f"{devpi}/devpi/", headers={"Accept": "application/json"})

    assert response.status_code == 200
    _check_cors(response)

    content = response.json()

    assert "result" in content
    assert "root" in content["result"]
    assert "type" in content


def test_devpi_simple_PEP_691_list(devpi_simple_root):
    response = requests.get(
        devpi_simple_root, headers={"Accept": "application/vnd.pypi.simple.v1+json"}
    )

    assert response.status_code == 200
    _check_cors(response)

    content = response.json()
    assert "meta" in content
    assert "api-version" in content["meta"]
    assert "projects" in content
    assert isinstance(content["projects"], list)

    # dummy package is in the list
    assert any([x["name"] == "test-dummy" for x in content["projects"]])


def test_devpi_simple_PEP_691_detail(devpi_simple_detail):
    package_name = "test-dummy"
    url = devpi_simple_detail.format(package_name=package_name)
    response = requests.get(
        url, headers={"Accept": "application/vnd.pypi.simple.v1+json"}
    )

    assert response.status_code == 200
    _check_cors(response)

    content = response.json()
    assert "meta" in content
    assert "api-version" in content["meta"]

    assert "name" in content
    assert content["name"] == package_name

    assert "files" in content
    assert isinstance(content["files"], list)
    assert len(content["files"]) > 0

    file = content["files"][0]
    assert "filename" in file
    assert "url" in file
    # url should be absolute, devpi requires `--absolute-url` flag for this.
    assert file["url"].startswith("http")

    assert "hashes" in file
    assert "sha256" in file["hashes"]


def test_devpi_simple_PEP_503_list(devpi_simple_root):
    # Very basic test, rest of the tests needs to be done in micropip

    response = requests.get(devpi_simple_root, headers={"Accept": "text/html"})

    assert response.status_code == 200
    _check_cors(response)

    content = response.text

    assert "<!DOCTYPE html>" in content
    assert "root/dev" in content


def test_devpi_simple_PEP_503_detail(devpi_simple_detail):
    # Very basic test, rest of the tests needs to be done in micropip

    package_name = "test-dummy"
    url = devpi_simple_detail.format(package_name=package_name)
    response = requests.get(url, headers={"Accept": "text/html"})

    assert response.status_code == 200
    _check_cors(response)

    content = response.text

    assert "<!DOCTYPE html>" in content
    assert "root/dev" in content
    assert "test_dummy" in content


def test_devpi_warehouse_json_detail(devpi_json_detail):
    # test JSON api that pypa/warehouse supports.
    # See: https://warehouse.pypa.io/api-reference/json.html

    package_name = "test-dummy"
    url = devpi_json_detail.format(package_name=package_name)

    response = requests.get(url, headers={"Accept": "application/json"})

    assert response.status_code == 200
    _check_cors(response)

    content = response.json()

    assert "info" in content
    assert "name" in content["info"]
    assert content["info"]["name"] == package_name
    assert "version" in content["info"]

    assert "releases" in content
    assert isinstance(content["releases"], dict)
    assert len(content["releases"]) > 0

    for releases in content["releases"].values():
        for release in releases:
            assert "filename" in release
            assert "url" in release
            assert "digests" in release
            assert "sha256" in release["digests"]
