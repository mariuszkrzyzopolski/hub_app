"""Name collision suggestion factory.

Provides alternative name suggestions when a guest name is already taken.
Generates simple variants by appending suffixes.
"""


def suggest_names(taken_name, max_suggestions=5):
    """Generate alternative name suggestions.

    Args:
        taken_name: The name that was already taken.
        max_suggestions: Maximum number of suggestions to return.

    Returns:
        A list of suggested alternative names as strings.
    """
    suggestions = []

    # Try appending common suffixes
    suffixes = ['_', '2', '_2', '_alt', '_guest']
    for suffix in suffixes:
        if len(suggestions) >= max_suggestions:
            break
        suggestions.append(f"{taken_name}{suffix}")

    return suggestions