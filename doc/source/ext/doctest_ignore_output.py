
def setup(app):
    """Add an "IGNORE_RESULT" doctest optionflag to sphinx.ext.doctest

    Any output following the flag will be ignored. This can be used when the
    result of a method call is not relevant to the doctest or code example::

        >>> p = pathlib.Path('somefile.txt')
        >>> # `write_text` returns the number of bytes written, but we don't care
        >>> p.write_text('foo')
        3
        >>> # Ignore it to make the code example cleaner
        >>> p.write_text('foo') #doctest: +IGNORE_RESULT

    """
    app.setup_extension('sphinx.ext.doctest')

    import doctest
    from sphinx.ext import doctest as sphinx_doctest
    _SphinxDocTestRunner_orig = sphinx_doctest.SphinxDocTestRunner
    sphinx_doctest._SphinxDocTestRunner_orig = _SphinxDocTestRunner_orig
    IGNORE_RESULT = doctest.register_optionflag('IGNORE_RESULT')

    class IgnoreOutputChecker(doctest.OutputChecker):
        def check_output(self, want, got, optionflags):
            if optionflags & IGNORE_RESULT:
                return True
            return super().check_output(want, got, optionflags)

    class MyRunner(_SphinxDocTestRunner_orig):
        def __init__(self, checker=None, verbose=None, optionflags=0):
            checker = IgnoreOutputChecker()
            super().__init__(checker, verbose, optionflags)

    sphinx_doctest.SphinxDocTestRunner = MyRunner

    return {
        'version': '0.1',
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }
