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
