from functools import partial

from sqc.core.transformation import affine_transformation, transform


def round_values(values, precision=9):
    return [round(value, precision) for value in values]


class TestTransformation:

    def test_affine_transformation(self):
        T, V0 = affine_transformation(
            (0, 0, 0), (0, 100, 0), (100, 100, 0),
            (1, 1, 1), (1, 111, 10), (101, 101, 20)
        )
        assert round_values(T[0]) == [1.0, -0.1, 0.1]
        assert round_values(T[1]) == [0.0, 1.1, 0.09]
        assert round_values(V0) == round_values([1.0, 0.9999999999999858, 1.0])

    def test_transform(self):
        T, V0 = affine_transformation(
            (0, 0, 0), (0, 100, 0), (100, 100, 0),
            (0, 0, 0), (0, 100, 6), (100, 100, 6),
        )
        tr = partial(transform, T, V0)
        assert tr((0, 0, 0)) == (0.0, 0.0, 0.0)
        assert tr((0, 50, 0)) == (0.0, 50.0, 3.0)
        assert tr((0, 100, 0)) == (0.0, 100.0, 6.0)
        assert round_values(tr((100, 0, 0))) == round_values((100.0, 2.0816681711721685e-15, 3.469446951953614e-16))

    def test_transform_z(self):
        T, V0 = affine_transformation(
            (0, 0, 0), (0, 100, 0), (100, 100, 0),
            (0, 0, 0), (0, 100, 10), (100, 100, 0),
        )
        tr = partial(transform, T, V0)
        assert tr((0, 0, 0)) == (0, 0, 0)
        assert tr((0, 100, 0)) == (0, 100, 10)
        assert tr((0, 50, 0)) == (0, 50, 5)
        assert round_values(tr((50, 100, 0))) == round_values((50, 100, 5))
