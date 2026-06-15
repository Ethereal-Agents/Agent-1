def truncate_output(text: str, max_len: int = 3000) -> str:
    """
    Truncates text if it exceeds max_len, appending the standard truncation warning
    required by the tool response format plan.
    """
    if len(text) <= max_len:
        return text
    warning = "\n...[OUTPUT TRUNCATED. Use search or pagination tools to see more]"
    # Leave room for the warning message so total length is exactly max_len
    keep_len = max_len - len(warning)
    return text[:keep_len] + warning


def format_error(reason: str, attempted: str, hint: str) -> str:
    """
    Formats all errors into the strict tripartite format required by the 2026 Zylos study,
    preventing LLM retry death-spirals.
    """
    return f"ERROR: {reason}\nATTEMPTED: {attempted}\nHINT: {hint}"
