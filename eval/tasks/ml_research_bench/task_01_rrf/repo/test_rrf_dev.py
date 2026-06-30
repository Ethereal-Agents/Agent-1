import pytest
from search import rrf_fuse

def test_rrf_basic():
    """Basic sanity check to ensure the function returns a list and doesn't crash."""
    dense = ["doc1", "doc2"]
    sparse = ["doc2", "doc3"]
    
    result = rrf_fuse(dense, sparse)
    
    # It should return a list
    assert isinstance(result, list)
    
    # It should contain all unique documents
    assert set(result) == {"doc1", "doc2", "doc3"}
    
    # doc2 appears in both, should be ranked first
    assert result[0] == "doc2"
