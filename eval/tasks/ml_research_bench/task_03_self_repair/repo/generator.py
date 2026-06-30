from typing import Callable, Tuple

def generate_with_repair(
    prompt: str,
    generate_fn: Callable[[str], str],
    validate_fn: Callable[[str], Tuple[bool, str]],
    max_retries: int = 3
) -> Tuple[str, bool, int]:
    """
    Implements a self-repair loop for code generation.
    
    1. Calls generate_fn(prompt) to get initial code.
    2. Calls validate_fn(code) to check if it's correct.
    3. If valid, returns the code, True, and the number of retries used (0).
    4. If invalid, construct a repair prompt combining the original prompt, the failed code, 
       and the error message from validate_fn. 
       Format: "Original prompt: {prompt}\nFailed code: {code}\nError: {error}\nPlease fix the code."
    5. Calls generate_fn with the repair prompt to get new code.
    6. Repeats up to max_retries times.
    7. If it still fails after max_retries, returns the last generated code, False, and max_retries.
    
    Args:
        prompt: The initial prompt for code generation.
        generate_fn: A function that takes a prompt string and returns generated code string.
        validate_fn: A function that takes code and returns (is_valid, error_message).
        max_retries: Maximum number of repair attempts (excluding initial generation).
        
    Returns:
        A tuple of (final_code, is_valid, num_retries_used).
    """
    # TODO: Implement the self-repair loop
    pass
