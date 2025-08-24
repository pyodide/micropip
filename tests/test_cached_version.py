
import pytest
from micropip._cached_version import CachedVersion
from micropip._vendored.packaging.src.packaging.version import Version


@pytest.mark.parametrize("version1, version2", [
    ("1.0.0", "1.0.1"),
    ("1.0a0", "1.0a1"),
    ("1.0.0rc1", "1.0.0rc2")
])
def test_equal_behavior(version1, version2):
    """Check equal behavior between Version and CachedVersion"""
    original = Version(version1) 
    cached = CachedVersion(version1)
    different = CachedVersion(version2)
        
    assert original == cached
    assert cached == original
    assert cached != different
        
    assert hash(original) == hash(cached)
        
    version_set = {original, cached}
    assert len(version_set) == 1, "Equal versions should deduplicate in sets"


def test_consistency_invariants():
    """Check that the caching doesn't break consistency"""
    obj = CachedVersion("1.0.0")
    
    hashes = [hash(obj) for _ in range(5)]
    strings = [str(obj) for _ in range(5)]
        
    assert all(h == hashes[0] for h in hashes), "Hash should be consistent across calls"
    assert all(s == strings[0] for s in strings), "String should be consistent across calls"
    
    version_set = {obj, CachedVersion("1.0.0")}
    assert len(version_set) == 1, "Identical cached versions should deduplicate"

    other_instance = CachedVersion("1.0.0")
    assert obj == other_instance
    assert hash(obj) == hash(other_instance)
    assert str(obj) == str(other_instance)
