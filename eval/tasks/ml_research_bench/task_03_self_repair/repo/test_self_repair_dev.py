import pytest
from generator import generate_with_repair

def test_self_repair_basic_success():
    """Basic sanity check: generate_fn returns valid code immediately."""
    def dummy_generate(prompt):
        return "valid code"
        
    def dummy_validate(code):
        return True, ""
        
    code, is_valid, retries = generate_with_repair("Make some code", dummy_generate, dummy_validate, max_retries=2)
    
    assert code == "valid code"
    assert is_valid is True
    assert retries == 0
