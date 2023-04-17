from typing import Any
from typing_extensions import TypeAlias

from .externals.mousebender import simple
from ._compat import fetch_string_and_headers

DEFAULT_INDEX_URL = 'https://pypi.org/simple/'

async def fetch_project_details(project_name: str, index_url: str | list[str] | None = None, fetch_kwargs: dict[str, str] = {}) -> simple.ProjectDetails:
    """
    Fetch the project details from the given index URLs.

    Parameters
    ----------
    project_name:
        The name of the project to fetch details for.

    index_url:
        The index URL to fetch from. If None, the default index URL is https://pypi.org/simple/.
        The index URL may be a string or a list of strings. If a list, the first URL
        that returns a valid response is used.

        The index URL must support Simple Repository API (PEP 503, PEP 691).
    
    fetch_kwargs:
        Additional keyword arguments to pass to the fetch function.

    Returns
    -------
    A list of project file details.

    """
    if index_url is None:
        index_url = DEFAULT_INDEX_URL
    
    if isinstance(index_url, str):
        index_url = [index_url]

    # Prefer JSON, but fall back to HTML if necessary
    _fetch_kwargs = fetch_kwargs.copy()
    _fetch_kwargs.setdefault('Accept', 'application/vnd.pypi.simple.v1+json, */*;q=0.01')

    for url in index_url:
        url = url.rstrip('/') + '/'
        try:
            project_url = url + project_name + '/'
            content, headers = await fetch_string_and_headers(project_url, fetch_kwargs)
            content_type = headers["Content-Type"]
            break
        except OSError:
            continue
    else: # no break
        raise ValueError(
            f"Can't fetch metadata for '{project_name}' from any index. "
            "Please make sure you have entered a correct package name."
        )

    try:
        details = simple.parse_project_details(content, content_type, project_name)
    except simple.UnsupportedMIMEType:
        raise ValueError(
            f"Invalid content type '{content_type}' for '{project_name}' from index '{url}'. "
        )
    
    return details
    