from typing import List, Dict, Any, Tuple
import time

import numpy as np

def get_embedding(text: str) -> np.ndarray:
    """
    A deterministic dummy embedding function for testing.
    It maps simple keywords to specific unit vectors.
    """
    text = text.lower()
    if "apple" in text:
        return np.array([1.0, 0.0, 0.0])
    elif "dog" in text:
        return np.array([0.0, 1.0, 0.0])
    elif "car" in text:
        return np.array([0.0, 0.0, 1.0])
    else:
        # Default orthogonal vector
        return np.array([0.5, 0.5, 0.5]) / np.sqrt(0.75)


class MemoryManager:
    """
    A semantic memory manager that stores text observations and retrieves them
    based on a combination of semantic similarity and recency.
    """
    
    def __init__(self, decay_rate: float = 0.99):
        """
        Args:
            decay_rate: The time-decay factor. A memory's raw similarity score 
                        is multiplied by (decay_rate ** age_in_hours).
        """
        self.decay_rate = decay_rate
        # TODO: Initialize necessary data structures
        
    def add_memory(self, text: str, timestamp: float = None) -> None:
        """
        Store a new memory observation.
        
        Args:
            text: The content of the memory.
            timestamp: The unix timestamp of the memory. If None, use current time.
        """
        # TODO: Implement adding a memory
        pass
        
    def retrieve(self, query: str, current_time: float = None, k: int = 5) -> List[Tuple[str, float]]:
        """
        Retrieve the top-k most relevant memories for a query.
        
        The final score for a memory is: 
            similarity(query, memory) * (decay_rate ** age_in_hours)
            
        Assume you have access to a simple dummy embedding function `get_embedding(text)`
        that returns a random numpy array for the sake of the dev test. The agent 
        should implement basic cosine similarity.
        
        Args:
            query: The text to search for.
            current_time: The current unix timestamp (to calculate age). 
                          If None, use current time.
            k: The number of memories to return.
            
        Returns:
            A list of tuples (memory_text, final_score), sorted by highest score first.
        """
        # TODO: Implement retrieval logic combining similarity and time decay
        return []
