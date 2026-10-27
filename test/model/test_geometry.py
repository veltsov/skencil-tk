# Layer 1: headless model tests -- skpoint arithmetic.  Regression guard
# for the number-protocol slot layout of the _sketch point type: a stray
# nb_index entry in skpoint.c's PyNumberMethods shifted every slot after
# nb_float by one, so under py3 `Point / scalar' silently registered as
# nb_inplace_floor_divide and division raised TypeError (found via
# interactive resize: SelectionRectangle.ButtonDown computes
# (self.start + self.end) / 2).  (no display required)


import pytest

import testsupport


def test_point_divide_by_number():
    sk = testsupport.sketch()
    from Sketch import Point
    p = Point(10, 20)
    q = p / 2
    assert q[0] == 5.0
    assert q[1] == 10.0
    q = p / 2.0
    assert q[0] == 5.0
    assert q[1] == 10.0


def test_point_other_number_ops():
    sk = testsupport.sketch()
    from Sketch import Point
    p = Point(10, 20)
    assert (p * 2)[0] == 20.0 and (p * 2)[1] == 40.0
    assert (2 * p)[0] == 20.0 and (2 * p)[1] == 40.0
    assert (p + Point(1, 1))[0] == 11.0
    assert (p - Point(1, 1))[1] == 19.0
    assert (-p)[0] == -10.0
    assert p[0] == 10.0 and p[1] == 20.0


def test_point_unsupported_operations():
    # Point/Point, floor division, remainder and divmod were never
    # supported (same behaviour as under py2).
    sk = testsupport.sketch()
    from Sketch import Point
    p = Point(10, 20)
    with pytest.raises(TypeError):
        p / Point(2, 2)
    with pytest.raises(TypeError):
        p // 2
    with pytest.raises(TypeError):
        p % 2
    with pytest.raises(TypeError):
        divmod(p, 2)
