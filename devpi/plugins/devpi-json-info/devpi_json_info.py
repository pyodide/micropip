import os
from typing import Any

from devpi_common.url import URL
from devpi_server.readonly import get_mutable_deepcopy
from pluggy import HookimplMarker
from pyramid.view import view_config

devpiserver_hookimpl = HookimplMarker("devpiserver")


@devpiserver_hookimpl
def devpiserver_pyramid_configure(config, pyramid_config):
    # by using include, the package name doesn't need to be set explicitly
    # for registrations of static views etc
    pyramid_config.include("devpi_json_info")


def includeme(config):
    config.add_route("json_info", "/{user}/{index}/{project}/json")
    config.scan()


@view_config(
    route_name="json_info",
    accept="application/json",
    request_method="GET",
    renderer="json",
)
def json_info_view(context, request) -> dict[str, Any]:
    # Override the base_url with the BASE_URL environment variable
    # This is useful when running behind a reverse proxy
    base_url: str = os.environ.get("BASE_URL", request.application_url)
    base_url_path: Any = URL(base_url).asdir()

    _version: str = context.stage.get_latest_version(context.project, stable=True)
    info: dict[str, Any] = get_mutable_deepcopy(
        context.stage.get_versiondata(context.project, _version)
    )
    info.pop("+elinks", None)

    releases: dict[str, Any] = {}

    for release in context.stage.get_releaselinks(context.project):
        version: str = release.version

        if version not in releases:
            releases[version] = []

        full_url: str = base_url_path.joinpath(release.relpath).url
        sha256: str = release.hash_spec.removeprefix("sha256=")

        releases[version].append(
            {
                "url": full_url,
                "filename": release.basename,
                "digests": {
                    "sha256": sha256,
                },
            }
        )

    result: dict[str, Any] = {
        "info": info,
        "releases": releases,
    }

    return result
