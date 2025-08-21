from .core.pii import get_redactor


def run_warmups() -> None:
    """
    Run all expensive initializations so the first request
    doesn't pay the cost.
    """
    # Warm up PII redactor
    _ = get_redactor()
