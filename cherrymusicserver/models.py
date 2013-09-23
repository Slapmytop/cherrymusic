#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# CherryMusic - a standalone music server
# Copyright (c) 2012-2013 Tom Wallroth & Tilman Boerner
#
# Project page:
#   http://fomori.org/cherrymusic/
# Sources on github:
#   http://github.com/devsnd/cherrymusic/
#
# CherryMusic is based on
#   jPlayer (GPL/MIT license) http://www.jplayer.org/
#   CherryPy (BSD license) http://www.cherrypy.org/
#
# licensed under GNU GPL version 3 (or later)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>
#

from backport import callable as _callable

from cherrymusicserver import log

def get(typename):
    return _ModelType.get(typename)


class field(object):
    ''' Model attribute descriptor with a default value.

        Callable default values are called with the model instance as
        argument and the result is used as the actual value.

            >>> class X(object):
            ...    @field
            ...    def id(self): return 'value'
            ...
            >>> X().id
            'value'
    '''
    def __init__(self, default=None, name=None, doc=None):
        self.default = default
        self.name = name
        self.doc = doc or (_callable(default) and default.__doc__) or repr(self)

    def __get__(self, container, owner):
        if container is None:
            return self
        value = self.default
        return value(container) if _callable(value) else value

    def __repr__(self):
        return '{0}(default={1!r})'.format(
            type(self).__name__, self.default)

    @property
    def doc(self):
        '''Field docstring'''
        return self.__doc__

    @doc.setter
    def doc(self, docstr):
        self.__doc__ = docstr

    @property
    def name(self):
        return self.__name__

    @name.setter
    def name(self, name):
        self.__name__ = name


def model(arg=None, **kwargs):
    ''' Create a model class from a spec dictionary or a template class.

        Spec dict:
            ``model(clsname, [fieldname=default,]*)``

            >>> TestModel = model('TestModel', a=1)
            >>> TestModel().a
            1

        Template class:
            usable as class decorator

            >>> @model
            ... class M(object):
            ...    a = field()
            ...
            >>> M._fields
            ('_id', '_type', 'a')
    '''
    if isinstance(arg, type):
        return _modelcls_from_class(arg, **kwargs)
    return _modelcls_from_spec(arg, **kwargs)

def _modelcls_from_spec(__clsname, **fields_with_defaults):
    fields = dict((n, field(default=v)) for n, v in fields_with_defaults.items())
    return _ModelType(__clsname, (Model,), fields)

def _modelcls_from_class(cls):
    if issubclass(type(cls), _ModelType):
        return cls
    bases = (Model,) + cls.__bases__
    clsdict = dict(cls.__dict__)
    return _ModelType(cls.__name__, bases, clsdict)


class _ModelType(type):

    types = {}

    def __new__(meta, name, bases, clsdict):
        attr = {'_fields': ()}
        attr.update(clsdict)
        cls = super(_ModelType, meta).__new__(meta, name, bases, attr)
        if not cls._fields:
            is_field = lambda x: isinstance(x, field)
            is_fieldname = lambda n: is_field(getattr(cls, n))
            cls._fields = tuple(filter(is_fieldname, dir(cls)))
        meta._register(cls)
        meta._init_fields(cls)
        return cls

    @classmethod
    def get(meta, name):
        return meta.types[name]

    @classmethod
    def _register(meta, cls):
        name = cls.__name__.lower()
        if name in meta.types:
            msg = 'overwriting type {0!r} {1} with {2}'.format(
                name, meta.types[name], cls)
            log.w(msg)
        if '_type' in cls._fields:
            cls._type = field(name)
        meta.types[name] = cls

    @classmethod
    def _init_fields(meta, cls):
        for fieldname in cls._fields:
            f = getattr(cls, fieldname, None)
            if not isinstance(f, field):
                f = field(default=f, name=fieldname)
            else:
                f.name = fieldname


class Model(object):
    ''' A generic model class that contains fields (``_fields``) and provides a
        dict view to them.

        Setting unknown attributes adds them to .
    '''

    _id = field()
    _type = field('set by metaclass', doc='the lowercase class name')

    def __new__(cls, *super_args, **fieldvalues):
        ''' Create a new Model instance.

            Positional arguments are passed to super.__new__, keyword arguments
            are used to initialize the fields after instantiation.
        '''
        instance = super(Model, cls).__new__(cls, *super_args)
        instance._fields = set(cls._fields)
        instance._update(**fieldvalues)
        return instance

    def __setattr__(self, name, value):
        is_new = name not in dir(self)
        super(Model, self).__setattr__(name, value)
        if is_new:
            self._fields.add(name)

    def __repr__(self):
        return repr(self.as_dict)

    def __eq__(self, other):
        ''' Models are equal if their dict_views are equal; they compare the
            same way to raw dicts.
        '''
        if not isinstance(other, (Model, dict)):
            return NotImplemented
        selfdict = self.as_dict
        otherdict = other if isinstance(other, dict) else other.as_dict
        return selfdict == otherdict

    def __ne__(self, other):
        return not self.__eq__(other)

    __hash__ = None     # unhashable; explicitly set to None for python2 compat

    @property
    def as_dict(self):
        ''' dict view of this object's fields and their values'''
        return dict((name, getattr(self, name)) for name in self._fields)

    def _update(self, **fieldvalues):
        for name, value in fieldvalues.items():
            setattr(self, name, value)
        return self

# Python 2 compatible metaclass workaround:
Model = _ModelType('Model', (object,), dict(Model.__dict__))
