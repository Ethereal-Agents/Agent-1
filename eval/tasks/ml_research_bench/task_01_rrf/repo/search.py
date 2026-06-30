from typing import List, Dict, Any

def rrf_fuse(dense_ranks: List[str], sparse_ranks: List[str], k: int = 60) -> List[str]:
    """
    Combine two ranked lists of document IDs using Reciprocal Rank Fusion (RRF).
    
    The RRF formula is: score(d) = Σ 1 / (k + rank(d))
    where rank(d) is the 1-indexed position of document d in the list.
    
    Args:
        dense_ranks: A ranked list of document IDs from a dense retriever.
        sparse_ranks: A ranked list of document IDs from a sparse retriever.
        k: The RRF constant (default 60).
        
    Returns:
        A single fused ranked list of document IDs, sorted by highest RRF score first.
        If scores tie, preserve the original order of document appearance 
        (dense first, then sparse).
    """
    # TODO: Implement this function
    pass
