from typing import overload


@overload
def at[T](items: list[T], index: int, default: None = None) -> T | None: ...
@overload
def at[T](items: list[T], index: int, default: T) -> T: ...
@overload
def at[T, D](items: list[T], index: int, default: D) -> T | D: ...
def at[T, D](items: list[T], index: int, default: T | D | None = None) -> T | D | None:
    """Safely accesses a list at a given index, returning a default if the index is out of range"""
    try:
        return items[index]
    except IndexError:
        return default
