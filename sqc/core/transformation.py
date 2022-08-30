"""Module providing tools for three dimensional affine transformation."""

import numpy as np
from numpy.linalg import inv

__all__ = ["affine_transformation", "transform"]


def affine_transformation(s1, s2, s3, t1, t2, t3) -> tuple:
    """Calculates the transformation matrix of the system.
    Via the equation T = P^-1 Q where P and Q are coming from the linear system
    s*T + V0 = v, si are the corresponding vectors (coordinates) in the sensor
    system, ti are those from the table system.
    They must be numpy arrays.
    """

    Q = [
        [t2[0] - t1[0], t2[1] - t1[1], t2[2] - t1[2]],
        [t3[0] - t1[0], t3[1] - t1[1], t3[2] - t1[2]]
    ]

    P = [
        [s2[0] - s1[0], s2[1] - s1[1]], [s3[0] - s1[0], s3[1] - s1[1]]
    ]

    try:
        # Invert the P matrix
        Pinv = inv(P)

        # Build the dot product
        T = np.dot(Pinv, Q).tolist()

        # Offset
        V0 = np.subtract(t2, np.transpose(s2[:2]).dot(T)).tolist()
    except Exception:
        return -1, -1

    return T, V0


def transform(T, V0, p) -> tuple:
    """This function transforms a Vector from the sensor system to the table
    system by vs * T + V0 = vt
    """
    p = np.add(np.array(p[:2]).dot(T), V0).tolist()
    return tuple(p)
