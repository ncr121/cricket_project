import numpy as np
import random as rd
from operator import attrgetter


class Float(float):
    def __truediv__(self, other):
        try:
            return super().__truediv__(other)
        except ZeroDivisionError:
            return float('inf') if self else float()


class List(list):
    def __getitem__(self, index):
        try:
            return super().__getitem__(index)
        except TypeError:
            return super().__getitem__(super().index(index))

    def copy(self):
        return self.__class__(super().copy())

    def remove(self, value):
        try:
            super().remove(value)
        except ValueError:
            pass

    def get(self, index, default=None):
        try:
            return self.__getitem__(index)
        except ValueError:
            return default


def attrlister(objs, *attrs):
    return [attrgetter(*attrs)(obj) for obj in objs]


def rvg(d):
    d = d.copy()
    d.pop('total', None)
    return rd.choices(*zip(*d.items()))[0]


def total_dicts(d):
    try:
        if isinstance(d, dict):
            d['total'] = sum(d.values())
    except TypeError:
        for v in d.values():
            total_dicts(v)


def zero_freqs():
    return np.zeros(8, int)
