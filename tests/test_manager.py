from micropip.manager import Manager
import micropip.package_index as package_index


def test_manager() -> Manager:
    manager = Manager()
    assert manager.index_urls == package_index.DEFAULT_INDEX_URLS

    return manager


def test_set_index_urls():
    manager = test_manager()

    default_index_urls = package_index.DEFAULT_INDEX_URLS
    assert manager.index_urls == default_index_urls

    valid_url1 = "https://pkg-index.com/{package_name}/json/"
    valid_url2 = "https://another-pkg-index.com/{package_name}"
    valid_url3 = "https://another-pkg-index.com/simple/"
    try:
        manager.set_index_urls(valid_url1)
        assert manager.index_urls == [valid_url1]

        manager.set_index_urls([valid_url1, valid_url2, valid_url3])
        assert manager.index_urls == [valid_url1, valid_url2, valid_url3]
    finally:
        manager.set_index_urls(default_index_urls)
        assert manager.index_urls == default_index_urls
