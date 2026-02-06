def calculate_fibonacci(n: int) -> list[int]:
    """
    Calculates the Fibonacci sequence up to the nth term.

    Args:
        n: The number of terms to calculate.

    Returns:
        A list of integers representing the Fibonacci sequence.
    """
    if n <= 0:
        return []
    if n == 1:
        return [0]
    fib_sequence = [0, 1]
    a, b = 0, 1
    for _ in range(2, n):
        a, b = b, a + b
        fib_sequence.append(b)
    return fib_sequence