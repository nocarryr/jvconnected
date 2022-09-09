# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys
# sys.path.insert(0, os.path.abspath('.'))
sys.path.append(os.path.abspath('./ext'))


# -- Project information -----------------------------------------------------

project = 'jvconnected'
copyright = '2020, Matthew Reid'
author = 'Matthew Reid'

# The full version, including alpha/beta/rc tags
release = '0.0.1'


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    # 'sphinx.ext.autosummary',
    'sphinx.ext.viewcode',
    'sphinx.ext.intersphinx',
    'sphinx.ext.todo',
    'sphinx.ext.doctest',
    'doctest_ignore_output',
    'pydispatch_sphinx',
    'autodoc_qt',
]
autodoc_member_order = 'bysource'
autodoc_default_options = {
    'show-inheritance':True,
}
autodoc_typehints = 'both'
autodoc_typehints_description_target = 'documented'

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'sphinx_rtd_theme'
html_theme_options = {
    'collapse_navigation':False,
}
html_css_files = [
    'css/custom.css',
]

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

intersphinx_mapping = {
    'python':('https://docs.python.org/', None),
    'pydispatch': ('https://python-dispatch.readthedocs.io/en/latest/', None),
    'tslumd': ('https://tslumd.readthedocs.io/en/latest/', None),
    'zeroconf':('https://python-zeroconf.readthedocs.io/en/latest/', None),
    'mido':('https://mido.readthedocs.io/en/latest/', None),
    'numpy':('https://numpy.org/doc/stable/', None),
    'PIL':('https://pillow.readthedocs.io/en/stable/', None),
    'PySide2':('https://doc.qt.io/qtforpython/', None),
    'PySide6':('https://doc.qt.io/qtforpython-6/', None),
}
