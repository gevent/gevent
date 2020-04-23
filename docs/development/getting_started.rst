=================
 Getting Started
=================

Developing gevent requires being able to install gevent from source.
See :doc:`installing_from_source` for general information about that.

Use A Virtual Environment
=========================

It is recommended to install the development copy of gevent in a
`virtual environment <https://docs.python.org/3/tutorial/venv.html>`_;
you can use the :mod:`venv` module distributed with Python 3, or
`virtualenv <https://pypi.org/project/virtualenv/>`_, possibly with
`virtualenvwrapper <https://pypi.org/project/virtualenvwrapper/>`_.

You may want a different virtual environment for each Python
implementation and version that you'll be working with. gevent
includes a `tox <http://tox.readthedocs.org/>`_ configuration for
automating the process of testing across multiple Python versions, but
that can be slow.

The rest of this document will assume working in an isolated virtual
environment, but usually won't show that in the prompt. An example of
creating a virtual environment is shown here::

  $ python3 -m venv gevent-env
  $ cd gevent-env
  $ . bin/activate
  (gevent-env) $


Installing Dependencies
=======================

To work on gevent, we'll need to get the source, install gevent's
dependencies, including test dependencies, and install gevent as an
`editable install
<https://pip.pypa.io/en/stable/reference/pip_install/#editable-installs>`_
using pip's ``-e`` option (also known as `development mode
<https://setuptools.readthedocs.io/en/latest/setuptools.html#development-mode>`_,
this is mostly the same as running ``python setup.py develop``).

Getting the source means cloning the git repository::

  (gevent-env) $ git clone https://github.com/gevent/gevent.git
  (gevent-env) $ cd gevent

Installing gevent's dependencies, test dependencies, and gevent itself
can be done in one line by installing the ``dev-requirements.txt`` file::

  (gevent-env) $ pip install -r dev-requirements.txt

.. warning::

   This pip command does not work with pip 19.1. Either use pip 19.0
   or below, or use pip 19.1.1 with ``--no-use-pep517``. See `issue
   1412 <https://github.com/gevent/gevent/issues/1412>`_.

Making Changes
==============

When adding new features (functions, methods, modules), be sure to
provide docstrings. The docstring should end with Sphinx's
`versionadded directive
<https://www.sphinx-doc.org/en/master/usage/restructuredtext/directives.html#directive-versionadded>`_,
using a version string of "NEXT". This string will automatically be
replaced with the correct version during the release process.

For example:

.. code-block:: python

   def make_plumbus(schleem, rub_fleeb=True):
      """
      Produces a plumbus.

      :param int scheem: The number of schleem to use.
          Possibly repurposed.
      :keyword bool rub_fleeb: Whether to rub the fleeb.
          Rubbing the fleeb is important, so only disable
          if you know what you're doing.
      .. versionadded:: NEXT
      """

When making a change to an existing feature that has already been
released, apply the appropriate `versionchanged
<https://www.sphinx-doc.org/en/master/usage/restructuredtext/directives.html#directive-versionchanged>`_
or `deprecated
<https://www.sphinx-doc.org/en/master/usage/restructuredtext/directives.html#directive-deprecated>`_
directive, also using "NEXT".

.. code-block:: python

   def make_plumbus(schleem, rub_fleeb=True):
      """
      Produces a plumbus.

      :param int schleem: The schleem to use.
          Possibly repurposed.
      :keyword bool rub_fleeb: Whether to rub the fleeb.
          Rubbing the fleeb is important, so only disable
          if you know what you're doing.
      :return: A :class:`Plumbus`.
      .. versionadded:: 20.04.0
      .. versionchanged:: NEXT
         The *rub_fleeb* parameter is ignored; the fleeb
         must always be rubbed.
      """

    def extract_fleeb_juice():
        """
        Get the fleeb juice.

        .. deprecated:: NEXT
           Extracting fleeb juice now happens automatically.
        """
