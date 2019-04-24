==========
 Examples
==========

..
  All files generated with shell oneliner:
  for i in examples/*py; do bn=`basename $i`; bnp=`basename $i .py`; echo -e "=============================\nExample $bn\n=============================\n.. literalinclude:: ../../examples/$bn\n  :language: python\n  :linenos:\n\n\`Current source <https://github.com/gevent/gevent/blob/master/examples/$bn>\`_\n" > doc/examples/$bnp.rst; done

This is a snapshot of the examples contained in `the gevent source
<https://github.com/gevent/gevent/tree/master/examples>`_.

.. toctree::
   concurrent_download
   dns_mass_resolve
   echoserver
   geventsendfile
   portforwarder
   processes
   psycopg2_pool
   threadpool
   udp_client
   udp_server
   unixsocket_client
   unixsocket_server
   webproxy
   webpy
   wsgiserver
   wsgiserver_ssl
