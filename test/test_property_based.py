import pytest
from hypothesis import given, assume, strategies as st

import msgpack

try:
    from msgpack import _cmsgpack
except ImportError:
    _cmsgpack = None
from msgpack import fallback

HYPOTHESIS_MAX = 50

# https://github.com/msgpack/msgpack/blob/master/spec.md#type-system
# TODO: test timestamps
# TODO: test the extension type
simple_types = (
    st.integers(min_value=-(2 ** 63), max_value=2 ** 64 - 1)
    | st.none()
    | st.booleans()
    | st.floats()
    # TODO: The msgpack speck says that string objects may contain invalid byte sequence
    | st.text(max_size=HYPOTHESIS_MAX)
    | st.binary(max_size=HYPOTHESIS_MAX)
)


def composite_types(any_type):
    return st.lists(any_type, max_size=HYPOTHESIS_MAX) | st.dictionaries(
        simple_types, any_type, max_size=HYPOTHESIS_MAX
    )


any_type = st.recursive(simple_types, composite_types)


@pytest.mark.skipif(_cmsgpack is None, reason="C extension is not available")
@given(any_type)
def test_extension_and_fallback_pack_identically(obj):
    extension_packer = _cmsgpack.Packer()
    fallback_packer = fallback.Packer()

    assert extension_packer.pack(obj) == fallback_packer.pack(obj)


# TODO: also test with strict_map_key=True
@pytest.mark.parametrize("impl", [fallback, _cmsgpack])
@given(obj=any_type)
def test_roudtrip(obj, impl):
    if impl is None:
        pytest.skip("C extension is not available")
    packer = impl.Packer()
    buf = packer.pack(obj)
    got = impl.unpackb(buf, strict_map_key=False)
    # using obj == got fails because NaN != NaN
    assert repr(obj) == repr(got)


# TODO: also test with strict_map_key=True
@pytest.mark.skipif(_cmsgpack is None, reason="C extension is not available")
@given(st.binary(max_size=HYPOTHESIS_MAX))
def test_extension_and_fallback_unpack_identically(buf):
    try:
        from_extension = _cmsgpack.unpackb(buf)
    except (msgpack.ExtraData, ValueError) as e:
        # Ignore the exception message. This avoids:
        #
        # Falsifying example: buf=b'\x00\x00'
        # Error: ExtraData(0, bytearray(b'\x00')) != ExtraData(0, b'\x00')
        #
        # Falsifying example: buf=b'\xa2'
        # Error: ValueError('2 exceeds max_str_len(1)') != ValueError('Unpack failed: incomplete input')
        # See https://github.com/msgpack/msgpack-python/pull/464
        from_extension = type(e)
    except Exception as e:
        from_extension = e
    try:
        from_fallback = fallback.unpackb(buf)
    except (msgpack.ExtraData, ValueError) as e:
        from_fallback = type(e)
    except Exception as e:
        from_fallback = e

    assert repr(from_extension) == repr(from_fallback)
