import pytest
from pydantic import BaseModel
from tinypipe.utils import _deep_hash


class PlainModel(BaseModel):
    a: int
    b: list[int]


class PlainObj:
    def __init__(self, x):
        self.x = x


class TestDeepHash:
    @pytest.mark.parametrize(
        ("obj1", "obj2"),
        [
            ({"a": 1, "b": [2, 3]}, {"a": 2, "b": [2, 3]}),
            ({"a": 1, "b": [2, 3]}, "foo"),
            (0, "foo"),
            (PlainModel(a=1, b=[2, 3]), PlainModel(a=2, b=[2, 3])),
            (PlainObj(x=1), PlainObj(x=2)),
        ],
    )
    def test_deep_hash_diff_input_are_diff_hash(self, obj1, obj2):
        assert _deep_hash(obj1) != _deep_hash(obj2)

    def test_deep_hash_same_input_same_hash(self):
        obj = {"x": [1, 2, 3]}
        assert _deep_hash(obj) == _deep_hash(obj)
        model = PlainModel(a=5, b=[9, 9])
        assert _deep_hash(model) == _deep_hash(model)
        obj = PlainObj(x=1)
        assert _deep_hash(obj) == _deep_hash(obj)

    def test_deep_hash_sorted_keys(self):
        dict1 = {"b": 2, "a": 1}
        dict2 = {"a": 1, "b": 2}
        assert _deep_hash(dict1) == _deep_hash(dict2)
