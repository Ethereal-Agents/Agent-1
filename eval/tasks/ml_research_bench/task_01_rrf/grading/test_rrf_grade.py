import pytest
from search import rrf_fuse

def test_rrf_disjoint_sets():
    """Documents only appear in one of the lists."""
    dense = ["A", "B"]
    sparse = ["C", "D"]
    
    # rank 1: score = 1/(60+1) = 1/61
    # rank 2: score = 1/(60+2) = 1/62
    # Since A and C both have rank 1, they tie. 
    # Function should preserve original order (dense first), so A then C.
    # B and D both have rank 2, so B then D.
    result = rrf_fuse(dense, sparse)
    assert result == ["A", "C", "B", "D"]


def test_rrf_overlap():
    """Documents appear in both lists."""
    dense = ["A", "B", "C"]
    sparse = ["C", "B", "A"]
    
    # A: dense rank 1, sparse rank 3 -> 1/61 + 1/63 = 0.01639 + 0.01587 = 0.03226
    # B: dense rank 2, sparse rank 2 -> 1/62 + 1/62 = 0.01612 + 0.01612 = 0.03225
    # C: dense rank 3, sparse rank 1 -> 1/63 + 1/61 = 0.01587 + 0.01639 = 0.03226
    # A and C tie for first. A appears first in dense, so A then C. Then B.
    
    result = rrf_fuse(dense, sparse)
    assert result == ["A", "C", "B"]


def test_rrf_missing_elements():
    """One list is empty or shorter."""
    dense = ["A", "B", "C"]
    sparse = ["B"]
    
    # A: dense 1 -> 1/61
    # B: dense 2, sparse 1 -> 1/62 + 1/61
    # C: dense 3 -> 1/63
    # Order: B, A, C
    
    result = rrf_fuse(dense, sparse)
    assert result == ["B", "A", "C"]


def test_rrf_empty_lists():
    """Both lists are empty."""
    assert rrf_fuse([], []) == []


def test_rrf_custom_k():
    """Test with a custom k value to ensure k is not hardcoded to 60."""
    dense = ["A", "B"]
    sparse = ["B", "A"]
    
    # Let k=1. 
    # A: dense 1, sparse 2 -> 1/(1+1) + 1/(1+2) = 1/2 + 1/3 = 5/6
    # B: dense 2, sparse 1 -> 1/(1+2) + 1/(1+1) = 1/3 + 1/2 = 5/6
    # Tie, so A then B.
    result = rrf_fuse(dense, sparse, k=1)
    assert result == ["A", "B"]
