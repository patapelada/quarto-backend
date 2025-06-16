from typing import Dict, Generic, Optional, TypeVar

# Define type variables for keys and values
K = TypeVar("K")
V = TypeVar("V")


class InMemoryDB(Generic[K, V]):
    def __init__(self):
        self._data: Dict[K, V] = {}

    def create(self, key: K, value: V) -> None:
        if key in self._data:
            raise KeyError(f"Key '{key}' already exists.")
        self._data[key] = value

    def read(self, key: K) -> Optional[V]:
        return self._data.get(key, None)

    def update(self, key: K, value: V) -> None:
        if key not in self._data:
            raise KeyError(f"Key '{key}' does not exist.")
        self._data[key] = value

    def delete(self, key: K) -> None:
        if key not in self._data:
            raise KeyError(f"Key '{key}' does not exist.")
        del self._data[key]

    def list_all(self) -> Dict[K, V]:
        return self._data.copy()
