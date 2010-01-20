# Copyright 2008 Owen Taylor
# Copyright 2008 Kai Willadsen
#
# This file is part of Reinteract and distributed under the terms
# of the BSD license. See the file COPYING in the Reinteract
# distribution for full details.
#
########################################################################

import copy
import inspect

def default_filter(baseclass, name):
    """Filter out attributes that should be excluded from a proxy class.

    @param baseclass: the class being proxied
    @param name: the C{baseclass} attribute being filtered
    @returns: False if C{baseclass.name} should not be proxied
    """
    if not inspect.ismethod(getattr(baseclass, name)):
        return False
    if name.startswith('_'):
        return False
    return True

class ReplayException(Exception):
    """
    Exception class to help with locating an exception-causing call for a
    recorded class. Note that information such as line numbers is not used,
    so it's currently only slightly helpful.
    """
    def __init__(self, orig_exception, orig_call):
        self.orig_exception = orig_exception
        self.orig_call = orig_call

    def __str__(self):
        exc_string = "on %(call_name)s()\n%(exc_name)s: %(exc_desc)s" % {
                           'call_name': self.orig_call[0],
                           'exc_name': self.orig_exception.__class__,
                           'exc_desc': str(self.orig_exception) }
        return exc_string

def _arg_count(n, non_keyword=False):
    non_keyword_s = 'non-keyword ' if non_keyword else ''
    if n == 1:
        return "1 %sargument" % (non_keyword_s,)
    else:
        return "%d %sarguments" % (n, non_keyword_s)

class RecordedObject(object):
    """
    A RecordedObject is a proxy for another object that Reinteract can't copy
    properly. It is designed for objects that are built up over a series of
    calls and then evaluated. This class should be used by subclassing
    C{RecordedObject} and then calling L{_set_target_class} on the new subclass.

    Because of the way that calls are recorded and replayed, exceptions from
    called methods will not be thrown until C{_replay} is called. To catch
    simple errors earlier, argument-checking support can be provided in
    subclasses by implementing a C{_check_} method for a given call. For
    example, to add argument checking for the C{plot} method, you would
    add the C{_check_plot} method to your subclass.
    """
    def __init__(self):
        self._recreation_calls = []

    def _replay(self, target):
        # At any point in time, an object's state can be recreated by
        # _replay()ing the calls recorded on it.
        for (call, args, kwargs) in self._recreation_calls:
            func = getattr(target, call)
            try:
                func(*args, **kwargs)
            except Exception, e:
                raise ReplayException(e, (call, args, kwargs))

    def __copy__(self):
        new = self.__class__()
        new._recreation_calls = copy.copy(self._recreation_calls)
        return new

    def _check_call(self, name, args, kwargs, spec):
        # This tries to duplicate some of python's argument checking logic
        num_args      = len(spec[0]) if spec[0] else 0
        use_varargs   = True if spec[1] else False
        use_varkwargs = True if spec[2] else False
        num_defaults  = len(spec[3]) if spec[3] else 0

        given_args = len(args) + 1 # self not included
        min_args = num_args - num_defaults

        if kwargs:
            for k, v in kwargs.iteritems():
                try:
                    pos = spec[0].index(k)
                except ValueError, e:
                    pos = -1

                if pos >= 0:
                    if pos < len(args) + 1:
                        # Duplicate of an argument specified without a keyword
                        raise TypeError("%(name)s() got multiple values for keyword argument '%(kw)s'" % {
                              'name': name,
                              'kw': k })
                    elif pos < num_args - num_defaults:
                        # If the user names a required argument, we don't need to look for it in args
                        given_args += 1
                elif not use_varkwargs:
                    raise TypeError("%(name)s() got an unexpected keyword argument '%(kw)s'" % {
                         'name': name,
                         'kw': k })

        exact_args = num_defaults == 0 and not use_varargs
        if exact_args and given_args != min_args:
            raise TypeError("%(name)s() takes exactly %(reqd)s (%(nargs)d given)" % {
                'name': name,
                'reqd': _arg_count(num_args),
                'nargs': given_args })
        elif given_args < min_args:
            raise TypeError("%(name)s() takes at least %(reqd)s (%(nargs)d given)" % {
                'name': name,
                'reqd': _arg_count(min_args, non_keyword=kwargs),
                'nargs': given_args })
        elif given_args > num_args and not use_varargs:
            raise TypeError("%(name)s() takes at most %(reqd)s (%(nargs)d given)" % {
                'name': name,
                'reqd': _arg_count(num_args),
                'nargs': given_args })

    @classmethod
    def _set_target_class(cls, baseclass, attr_filter=default_filter):
        """
        Give class proxy methods from C{baseclass}, which can later be replayed.

        @param baseclass: the class to proxy
        @param attr_filter: a filter function for C{baseclass} attributes

          The C{attr_filter} function should take the baseclass and attribute
          name as arguments, and return True if an attribute should be
          included. This should be used to remove attributes that it makes
          little sense to include (e.g., C{__class__} or getters) or that you
          want to override. See L{default_filter}.
        """
        def _create_proxy_method(name):
            spec = inspect.getargspec(getattr(baseclass, name))
            try:
                func = getattr(cls, '_check_' + name)
            except AttributeError:
                func = getattr(cls, '_check_call')

            def record(self, *args, **kwargs):
                func(self, name, args, kwargs, spec)
                self._recreation_calls.append((name, args, kwargs))
            return record

        whitelist = (d for d in dir(baseclass) if attr_filter(baseclass, d))

        for attr in whitelist:
            if hasattr(cls, attr):
                raise AttributeError('%s already has attribute %s' % (cls, attr))
            record = _create_proxy_method(attr)
            record.__name__ = attr
            record.__doc__ = getattr(baseclass, attr).__doc__
            setattr(cls, attr, record)

if __name__ == '__main__': #pragma: no cover
    from test_utils import assert_equals

    class TestTarget:
        def __init__():
            pass

        def exactargs(self, a, b):
            pass

        def defaultargs(self, a, b=1):
            pass

        def varargs(self, *args):
            pass

        def kwargs(self, **kwargs):
            pass

    class TestRecorded(RecordedObject):
        pass

    TestRecorded._set_target_class(TestTarget)
    o = TestRecorded()

    # Tests of our argument checking

    def expect_ok(method, *args, **kwargs):
        o.__class__.__dict__[method](o, *args, **kwargs)

    def expect_fail(method, msg, *args, **kwargs):
        try:
            o.__class__.__dict__[method](o, *args, **kwargs)
            raise AssertionError("Expected failure with '%s', got success" % (msg,))
        except TypeError, e:
            if str(e) != msg:
                raise AssertionError("Expected failure with '%s', got '%s'" % (msg, str(e)))

    expect_ok('exactargs', 1, 2)
    expect_ok('exactargs', 1, b=2)
    expect_fail('exactargs', "exactargs() takes exactly 3 arguments (2 given)",
                1)
    expect_fail('exactargs', "exactargs() got an unexpected keyword argument 'c'",
                1, 2, c=3)
    expect_fail('exactargs', "exactargs() got multiple values for keyword argument 'a'",
                1, a=1)

    expect_ok('defaultargs', 1, 2)
    expect_ok('defaultargs', 1)
    expect_ok('defaultargs', a=1, b=2)
    expect_fail('defaultargs', "defaultargs() takes at least 2 arguments (1 given)",
                )
    expect_fail('defaultargs', "defaultargs() takes at least 2 non-keyword arguments (1 given)",
                b=1)
    expect_fail('defaultargs', "defaultargs() takes at most 3 arguments (4 given)",
                1, 2, 3)
    expect_fail('defaultargs', "defaultargs() got an unexpected keyword argument 'c'",
                1, 2, c=3)
    expect_fail('defaultargs', "defaultargs() got multiple values for keyword argument 'a'",
                1, a=1)

    expect_ok('varargs', 1)
    expect_fail('varargs', "varargs() got an unexpected keyword argument 'a'",
                1, a=1)

    expect_ok('kwargs', a=1)
    expect_fail('kwargs', "kwargs() takes exactly 1 argument (2 given)",
                1)
