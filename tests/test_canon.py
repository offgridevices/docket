import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from docket.canon import canonical_json, content_hash, round6, sha256_hex


def test_canonical_json_sorts_keys_and_strips_whitespace():
    obj = {"b": 1, "a": [1, 2, {"z": 0, "y": None}]}
    assert canonical_json(obj) == '{"a":[1,2,{"y":null,"z":0}],"b":1}'


def test_canonical_json_rejects_nan():
    with pytest.raises(ValueError):
        canonical_json({"x": math.nan})


def test_canonical_json_keeps_unicode():
    assert canonical_json({"s": "¶4-5b"}) == '{"s":"¶4-5b"}'


def test_content_hash_is_sha256_of_canonical():
    obj = {"k": "v"}
    assert content_hash(obj) == sha256_hex(canonical_json(obj))
    assert len(content_hash(obj)) == 64


def test_round6():
    assert round6(1 / 3) == 0.333333
    assert round6(2.0) == 2.0


json_scalars = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(),
)
json_values = st.recursive(
    json_scalars, lambda c: st.lists(c) | st.dictionaries(st.text(), c), max_leaves=20
)


@given(json_values)
def test_canonical_json_is_deterministic(v):
    assert canonical_json(v) == canonical_json(v)
