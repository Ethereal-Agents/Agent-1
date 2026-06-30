import pytest
from generator import generate_with_repair

def test_repair_success_first_try():
    """Test that if the code is valid initially, it returns immediately with 0 retries."""
    calls = []
    
    def dummy_generate(prompt):
        calls.append(prompt)
        return "perfect code"
        
    def dummy_validate(code):
        return True, ""
        
    code, is_valid, retries = generate_with_repair(
        prompt="Write a loop", 
        generate_fn=dummy_generate, 
        validate_fn=dummy_validate, 
        max_retries=3
    )
    
    assert code == "perfect code"
    assert is_valid is True
    assert retries == 0
    assert len(calls) == 1
    assert calls[0] == "Write a loop"


def test_repair_success_with_retries():
    """Test that the loop retries and successfully returns when code becomes valid."""
    generate_calls = []
    
    # Mock generator that fails twice, then succeeds
    def dummy_generate(prompt):
        generate_calls.append(prompt)
        if len(generate_calls) == 1:
            return "bad code 1"
        elif len(generate_calls) == 2:
            return "bad code 2"
        else:
            return "good code"
            
    def dummy_validate(code):
        if code == "good code":
            return True, ""
        return False, f"SyntaxError in {code}"
        
    code, is_valid, retries = generate_with_repair(
        prompt="Write a function", 
        generate_fn=dummy_generate, 
        validate_fn=dummy_validate, 
        max_retries=5
    )
    
    assert code == "good code"
    assert is_valid is True
    assert retries == 2
    assert len(generate_calls) == 3


def test_repair_exhaust_max_retries():
    """Test that it stops after max_retries and returns the last failed code."""
    generate_calls = []
    
    # Mock generator that always fails
    def dummy_generate(prompt):
        generate_calls.append(prompt)
        return f"failed code {len(generate_calls)}"
        
    def dummy_validate(code):
        return False, "Always fails"
        
    code, is_valid, retries = generate_with_repair(
        prompt="Write impossible code", 
        generate_fn=dummy_generate, 
        validate_fn=dummy_validate, 
        max_retries=2
    )
    
    # Initial call (1) + 2 retries = 3 calls total
    assert len(generate_calls) == 3
    assert code == "failed code 3"
    assert is_valid is False
    assert retries == 2


def test_repair_prompt_format():
    """Test that the repair prompt is formatted EXACTLY as specified."""
    generate_calls = []
    
    def dummy_generate(prompt):
        generate_calls.append(prompt)
        return "bad code"
        
    def dummy_validate(code):
        return False, "Custom error message"
        
    # Set max_retries to 1 so we get exactly one repair attempt
    generate_with_repair(
        prompt="Initial prompt", 
        generate_fn=dummy_generate, 
        validate_fn=dummy_validate, 
        max_retries=1
    )
    
    assert len(generate_calls) == 2
    
    expected_repair_prompt = (
        "Original prompt: Initial prompt\n"
        "Failed code: bad code\n"
        "Error: Custom error message\n"
        "Please fix the code."
    )
    
    # The second call to generate_fn should use the exact formatted repair prompt
    assert generate_calls[1] == expected_repair_prompt
