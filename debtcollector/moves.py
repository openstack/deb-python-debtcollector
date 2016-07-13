# -*- coding: utf-8 -*-

#    Copyright (C) 2015 Yahoo! Inc. All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import inspect

import six
import wrapt

from debtcollector import _utils

_KIND_MOVED_PREFIX_TPL = "%s '%s' has moved to '%s'"
_CLASS_MOVED_PREFIX_TPL = "Class '%s' has moved to '%s'"
_MOVED_CALLABLE_POSTFIX = "()"
_FUNC_MOVED_PREFIX_TPL = "Function '%s' has moved to '%s'"


def _moved_decorator(kind, new_attribute_name, message=None,
                     version=None, removal_version=None, stacklevel=3,
                     attr_postfix=None, category=None):
    """Decorates a method/property that was moved to another location."""

    def decorator(f):
        fully_qualified, old_attribute_name = _utils.get_qualified_name(f)
        if attr_postfix:
            old_attribute_name += attr_postfix

        @wrapt.decorator
        def wrapper(wrapped, instance, args, kwargs):
            base_name = _utils.get_class_name(wrapped, fully_qualified=False)
            if fully_qualified:
                old_name = old_attribute_name
            else:
                old_name = ".".join((base_name, old_attribute_name))
            new_name = ".".join((base_name, new_attribute_name))
            prefix = _KIND_MOVED_PREFIX_TPL % (kind, old_name, new_name)
            out_message = _utils.generate_message(
                prefix, message=message,
                version=version, removal_version=removal_version)
            _utils.deprecation(out_message, stacklevel=stacklevel,
                               category=category)
            return wrapped(*args, **kwargs)

        return wrapper(f)

    return decorator


def moved_function(new_func, old_func_name, old_module_name,
                   message=None, version=None, removal_version=None,
                   stacklevel=3, category=None):
    """Deprecates a function that was moved to another location.

    This generates a wrapper around ``new_func`` that will emit a deprecation
    warning when called. The warning message will include the new location
    to obtain the function from.
    """
    new_func_full_name = _utils.get_callable_name(new_func)
    new_func_full_name += _MOVED_CALLABLE_POSTFIX
    old_func_full_name = ".".join([old_module_name, old_func_name])
    old_func_full_name += _MOVED_CALLABLE_POSTFIX
    prefix = _FUNC_MOVED_PREFIX_TPL % (old_func_full_name, new_func_full_name)
    out_message = _utils.generate_message(prefix,
                                          message=message, version=version,
                                          removal_version=removal_version)

    @six.wraps(new_func, assigned=_utils.get_assigned(new_func))
    def old_new_func(*args, **kwargs):
        _utils.deprecation(out_message, stacklevel=stacklevel,
                           category=category)
        return new_func(*args, **kwargs)

    old_new_func.__name__ = old_func_name
    old_new_func.__module__ = old_module_name
    return old_new_func


class moved_read_only_property(object):
    """Descriptor for read-only properties moved to another location.

    This works like the ``@property`` descriptor but can be used instead to
    provide the same functionality and also interact with the :mod:`warnings`
    module to warn when a property is accessed, so that users of those
    properties can know that a previously read-only property at a prior
    location/name has moved to another location/name.

    :param old_name: old attribute location/name
    :param new_name: new attribute location/name
    :param version: version string (represents the version this deprecation
                    was created in)
    :param removal_version: version string (represents the version this
                            deprecation will be removed in); a string
                            of '?' will denote this will be removed in
                            some future unknown version
    :param stacklevel: stacklevel used in the :func:`warnings.warn` function
                       to locate where the users code is when reporting the
                       deprecation call (the default being 3)
    :param category: the :mod:`warnings` category to use, defaults to
                     :py:class:`DeprecationWarning` if not provided
    """

    def __init__(self, old_name, new_name,
                 version=None, removal_version=None,
                 stacklevel=3, category=None):
        self._old_name = old_name
        self._new_name = new_name
        self._message = _utils.generate_message(
            "Read-only property '%s' has moved"
            " to '%s'" % (self._old_name, self._new_name),
            version=version, removal_version=removal_version)
        self._stacklevel = stacklevel
        self._category = category

    def __get__(self, instance, owner):
        _utils.deprecation(self._message,
                           stacklevel=self._stacklevel,
                           category=self._category)
        # This handles the descriptor being applied on a
        # instance or a class and makes both work correctly...
        if instance is not None:
            real_owner = instance
        else:
            real_owner = owner
        return getattr(real_owner, self._new_name)


def moved_method(new_method_name, message=None,
                 version=None, removal_version=None, stacklevel=3,
                 category=None):
    """Decorates an *instance* method that was moved to another location."""
    if not new_method_name.endswith(_MOVED_CALLABLE_POSTFIX):
        new_method_name += _MOVED_CALLABLE_POSTFIX
    return _moved_decorator('Method', new_method_name, message=message,
                            version=version, removal_version=removal_version,
                            stacklevel=stacklevel,
                            attr_postfix=_MOVED_CALLABLE_POSTFIX,
                            category=category)


def moved_property(new_attribute_name, message=None,
                   version=None, removal_version=None, stacklevel=3,
                   category=None):
    """Decorates an *instance* property that was moved to another location."""
    return _moved_decorator('Property', new_attribute_name, message=message,
                            version=version, removal_version=removal_version,
                            stacklevel=stacklevel, category=category)


def moved_class(new_class, old_class_name, old_module_name,
                message=None, version=None, removal_version=None,
                stacklevel=3, category=None):
    """Deprecates a class that was moved to another location.

    This creates a 'new-old' type that can be used for a
    deprecation period that can be inherited from. This will emit warnings
    when the old locations class is initialized, telling where the new and
    improved location for the old class now is.
    """

    if not inspect.isclass(new_class):
        _qual, type_name = _utils.get_qualified_name(type(new_class))
        raise TypeError("Unexpected class type '%s' (expected"
                        " class type only)" % type_name)

    old_name = ".".join((old_module_name, old_class_name))
    new_name = _utils.get_class_name(new_class)
    prefix = _CLASS_MOVED_PREFIX_TPL % (old_name, new_name)
    out_message = _utils.generate_message(
        prefix, message=message, version=version,
        removal_version=removal_version)

    def decorator(f):

        @six.wraps(f, assigned=_utils.get_assigned(f))
        def wrapper(self, *args, **kwargs):
            _utils.deprecation(out_message, stacklevel=stacklevel,
                               category=category)
            return f(self, *args, **kwargs)

        return wrapper

    old_class = type(old_class_name, (new_class,), {})
    old_class.__module__ = old_module_name
    old_class.__init__ = decorator(old_class.__init__)
    return old_class
