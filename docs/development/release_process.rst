=================
 Release Process
=================

Release Cadence
===============

TODO: Write me.

Deprecation Policy
==================

.. This is largely based on what pip says.

Any change to gevent that removes or significantly alters user-visible
behavior that is described in the gevent documentation will be
deprecated for a minimum of 6 months before the change occurs.
Deprecation will be called out in the documentation and in some cases
with a runtime warning when the feature is used (because of the
performance sensitive nature of gevent, not all deprecations will have
a runtime warning). Longer deprecation periods, or deprecation
warnings for behavior changes that would not normally be covered by
this policy, are also possible depending on circumstances, but this is
at the discretion of the gevent developers.

Note that the documentation is the sole reference for what counts as
agreed behavior. If something isn’t explicitly mentioned in the
documentation, it can be changed without warning, or any deprecation
period, in a gevent release. However, we are aware that the documentation
isn’t always complete - PRs that document existing behavior with the
intention of covering that behavior with the above deprecation process
are always acceptable, and will be considered on their merits.


Releasing gevent
================

.. note:: This is a semi-organized collection of notes for gevent
          maintainers.

gevent is released using `zest.releaser
<https://pypi.org/project/zest.releaser/>`_. The general flow is
something like this:

1. Push all relevant changes to master.
2. From the gevent working copy, run ``prerelease``. Fix any issues it
   brings up. Let it bump the version number (or enter the correct
   one) and commit.
3. Run ``release``. Let it create the tag and commit it; let it create
   an sdist, but **do not** let it upload it.
4. Push the tag and master to github.
5. Let appveyor build the tag. Download all the built wheels from that
   release. The easiest way to do that is with Ned Batchelder's
   `appveyor-download.py script
   <https://bitbucket.org/ned/coveragepy/src/tip/ci/download_appveyor.py>`_.
6. Meanwhile, spin up docker and from the root of the gevent checkout
   run ``scripts/releases/make-manylinux``. This creates wheels in
   ``wheelhouse/``.
7. If on a mac, ``cd scripts/releases && ./geventreleases.sh``. This
   creates wheels in ``/tmp/gevent/``.
8. Upload the Appveyor, manylinux, and mac wheels to pypi using
   ``twine``. Also be sure to upload the sdist!
9. Run ``postrelease``, let it bump the version and push the changes
   to github.
