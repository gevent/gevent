=================
 Release Process
=================

Release Cadence and Versions
============================

After :doc:`gevent 1.5 <../whatsnew_1_5>`, gevent releases switched to
`CalVer <https://calver.org>`_, using the scheme ``YY.MM.Micro``
(two-digit year, month, micro/patch number). Thus the
first release in April of 2020 would be version ``20.4.0``. A second
release would be ``20.4.1``, etc. The first release in May
would be ``20.5.0``, and so on.

If there have been changes to master, gevent should produce a release
at least once a month.

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
<https://pypi.org/project/zest.releaser/>`_. Binary wheels are
published automatically by Github Actions CI.


1. Push all relevant changes to master.
2. From the gevent working copy, run ``fullrelease``. Fix any issues it
   brings up. Let it bump the version number (or enter the correct
   one), commit, create the tag, create the sdist, upload the sdist
   and push the tag to GitHub. Note that you might want to upload the
   sdist only after all the CI processes complete and binary wheels
   are in place. This prevents complaints from users who were
   expecting to find a binary wheel but got a sdist instead.
3. Monitor the build process on the CI systems. If particular builds
   fail due to test instability, re-run them to allow the binary wheel
   to be uploaded.
