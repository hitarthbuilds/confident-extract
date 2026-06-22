"""Custom repair strategy registration for the confident-extract pipeline."""

from __future__ import annotations

from collections.abc import Callable

_RepairStrategy = Callable[[str], str]

_CUSTOM_STRATEGIES: list[tuple[str, _RepairStrategy]] = []


def register_strategy(name: str, fn: _RepairStrategy, *, prepend: bool = False) -> None:
    """Registers a custom repair strategy in the global repair pipeline.

    Custom strategies are tried after all built-in strategies fail to produce
    valid JSON. Use ``prepend=True`` to run your strategy before the built-ins.

    The strategy function receives the current text and must return the
    (potentially mutated) text. Return the input unchanged if the strategy
    does not apply — the engine uses string identity to detect mutations.

    Args:
        name: Unique strategy name used in ``strategy_trace`` and confidence
            scoring. Must not clash with a built-in strategy name.
        fn: Callable ``(text: str) -> str``. Pure function — no side effects.
        prepend: When ``True``, the strategy is tried before built-in strategies.

    Raises:
        ValueError: If a strategy with the same name is already registered.

    Example::

        from confident_extract.repair.registry import register_strategy

        def fix_nan_values(text: str) -> str:
            return text.replace(": NaN", ": null").replace(":NaN", ":null")

        register_strategy("fix_nan_values", fix_nan_values)
    """
    for registered_name, _ in _CUSTOM_STRATEGIES:
        if registered_name == name:
            msg = f"A strategy named {name!r} is already registered. Unregister it first."
            raise ValueError(msg)

    if prepend:
        _CUSTOM_STRATEGIES.insert(0, (name, fn))
    else:
        _CUSTOM_STRATEGIES.append((name, fn))


def unregister_strategy(name: str) -> bool:
    """Removes a previously registered custom strategy.

    Args:
        name: Strategy name to remove.

    Returns:
        ``True`` if the strategy was found and removed, ``False`` otherwise.
    """
    for idx, (registered_name, _) in enumerate(_CUSTOM_STRATEGIES):
        if registered_name == name:
            del _CUSTOM_STRATEGIES[idx]
            return True
    return False


def list_strategies() -> list[str]:
    """Returns the names of all currently registered custom strategies."""
    return [name for name, _ in _CUSTOM_STRATEGIES]


def get_custom_strategies() -> list[tuple[str, _RepairStrategy]]:
    """Returns the live custom strategy list for use by the repair engine."""
    return _CUSTOM_STRATEGIES
