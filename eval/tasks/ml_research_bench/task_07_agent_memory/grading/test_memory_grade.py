import pytest
import time
from memory_manager import MemoryManager

def test_semantic_similarity_ranking():
    """Verify memories are ranked correctly by cosine similarity (no time decay)."""
    manager = MemoryManager(decay_rate=1.0) # Disable time decay
    t = 1000.0
    
    # apple vector: [1, 0, 0]
    # dog vector: [0, 1, 0]
    manager.add_memory("I bought an apple", timestamp=t)
    manager.add_memory("I walked the dog", timestamp=t)
    
    # Query "apple" -> should match apple vector perfectly (1.0), and dog vector orthogonally (0.0)
    results = manager.retrieve("apple", current_time=t, k=2)
    
    assert len(results) == 2
    assert "apple" in results[0][0]
    assert results[0][1] == pytest.approx(1.0) # Cosine similarity should be 1.0
    assert "dog" in results[1][0]
    assert results[1][1] == pytest.approx(0.0)


def test_time_decay():
    """Verify that older memories are penalized by the decay rate."""
    manager = MemoryManager(decay_rate=0.9)
    current_time = 100000.0
    
    # Both are "apple", so both have similarity 1.0 to an "apple" query.
    # The older one is 10 hours old, the newer is 1 hour old.
    t_old = current_time - (10 * 3600)
    t_new = current_time - (1 * 3600)
    
    manager.add_memory("An old apple", timestamp=t_old)
    manager.add_memory("A new apple", timestamp=t_new)
    
    results = manager.retrieve("apple", current_time=current_time, k=2)
    
    assert len(results) == 2
    # The new apple should win because it decayed less
    assert "new apple" in results[0][0]
    assert "old apple" in results[1][0]
    
    # Check exact math: score = sim * (0.9 ** age_in_hours)
    # new apple age = 1 hour -> score = 1.0 * (0.9 ** 1) = 0.9
    # old apple age = 10 hours -> score = 1.0 * (0.9 ** 10) = 0.3486...
    assert results[0][1] == pytest.approx(0.9)
    assert results[1][1] == pytest.approx(0.9 ** 10)


def test_combined_similarity_and_decay():
    """Verify that a slightly less similar but much newer memory can outrank a perfect but old memory."""
    manager = MemoryManager(decay_rate=0.5) # Fast decay for extreme test
    current_time = 10000.0
    
    # Query: "apple" (vector [1, 0, 0])
    # Memory 1 (Perfect match, but 4 hours old)
    manager.add_memory("I love apple", timestamp=current_time - (4 * 3600))
    # Sim = 1.0, Age = 4 -> Final = 1.0 * (0.5 ** 4) = 0.0625
    
    # Memory 2 (Default orthogonal match, but 0 hours old)
    manager.add_memory("Random stuff", timestamp=current_time)
    # Default vector is [0.5, 0.5, 0.5]/sqrt(0.75). Cosine sim to [1,0,0] is ~0.577.
    # Age = 0 -> Final = 0.577 * (0.5 ** 0) = 0.577
    
    results = manager.retrieve("apple", current_time=current_time, k=2)
    
    assert len(results) == 2
    # The newer but less relevant memory should win
    assert "Random stuff" in results[0][0]
    assert "I love apple" in results[1][0]


def test_k_limit():
    """Verify retrieve only returns k items."""
    manager = MemoryManager()
    t = 100.0
    for i in range(10):
        manager.add_memory(f"apple {i}", timestamp=t)
        
    results = manager.retrieve("apple", current_time=t, k=3)
    assert len(results) == 3


def test_missing_timestamps():
    """Verify the system handles missing timestamps by defaulting to time.time()."""
    manager = MemoryManager()
    
    # Should not crash
    manager.add_memory("apple")
    results = manager.retrieve("apple", k=1)
    
    assert len(results) == 1
    assert "apple" in results[0][0]
    # Age should be near 0, so score should be near 1.0
    assert results[0][1] == pytest.approx(1.0)
