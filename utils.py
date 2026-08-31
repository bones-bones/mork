from typing import TypeVar, overload

T = TypeVar("T")
D = TypeVar("D")


@overload
def at(items: list[T], index: int, default: None = None) -> T | None: ...
@overload
def at(items: list[T], index: int, default: T) -> T: ...
@overload
def at(items: list[T], index: int, default: D) -> T | D: ...
def at(items: list[T], index: int, default: T | D | None = None) -> T | D | None:
    """Safely accesses a list at a given index, returning a default if the index is out of range"""
    try:
        return items[index]
    except IndexError:
        return default
