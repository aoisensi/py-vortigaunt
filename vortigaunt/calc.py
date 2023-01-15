
from typing import overload
from type import Vector2, Vector3, Vector4


@overload
def vec_max(a: Vector2, b: Vector2) -> Vector2:
    ...


@overload
def vec_max(a: Vector3, b: Vector3) -> Vector3:
    ...


@overload
def vec_max(a: Vector4, b: Vector4) -> Vector4:
    ...


def vec_max(a, b):
    return tuple(map(max, zip(a, b)))


@overload
def vec_min(a: Vector2, b: Vector2) -> Vector2:
    ...


@overload
def vec_min(a: Vector3, b: Vector3) -> Vector3:
    ...


@overload
def vec_min(a: Vector4, b: Vector4) -> Vector4:
    ...


def vec_min(a, b):
    return tuple(map(min, zip(a, b)))
