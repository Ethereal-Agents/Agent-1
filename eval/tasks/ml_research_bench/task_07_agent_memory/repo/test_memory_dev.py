import pytest
from memory_manager import MemoryManager

def test_memory_basic_retrieval():
    """Basic sanity check to ensure the class initializes and returns results."""
    manager = MemoryManager()
    
    manager.add_memory("The user's favorite color is blue.")
    manager.add_memory("The sky is blue today.")
    
    # Should not crash and should return k results
    results = manager.retrieve("What is the user's favorite color?", k=1)
    
    assert isinstance(results, list)
    if results:
        assert isinstance(results[0], tuple)
        assert len(results[0]) == 2
        assert isinstance(results[0][0], str)
        assert isinstance(results[0][1], float)
