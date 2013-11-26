Success stories
===============

If you have a success story for Gevent, contact denis.bilenko@gmail.com or post to the `google group`_.

.. _google group: http://groups.google.com/group/gevent/


Omegle_
-------

I've been using gevent to power Omegle, my high-volume chat site,
since 2010. Omegle is used by nearly half a million people every day,
and it has as many as 20,000 users chatting at any given time. It
needs to needs to perform well and be extremely reliable, and gevent
makes that easy to do: gevent gives you power to do more creative
things, and it's fast enough that you can more easily write apps that
stand up to a lot of load.

gevent is well-engineered, and its development has been maintaining an
active, dedicated pace for as long as I've been following it. Any time
I've had an issue with gevent that I couldn't solve on my own, the
friendly community has been extremely helpful and knowledgeable. I
really think gevent is the best library of its type for Python right
now, and I would recommend it to anyone who needs a good networking
library.

-- Leif K-Brooks, Founder, Omegle.com_

.. _Omegle: http://omegle.com
.. _Omegle.com: http://omegle.com


Pediapress_
-----------

Pediapress_ powers Wikipedia_'s PDF rendering cluster. I've started using
gevent in 2009 after our NFS based job queue showed serious performance
problems on Wikipedia's PDF rendering cluster. I've replaced that with
a gevent based job queue server in a short time. gevent is managing the
generation of around 100000 PDF files daily and is serving them to wikipedia users.

Recently I've refactored the component that fetches articles and
images from wikipedia to use gevent instead of twisted. The code is
much cleaner and much more manageable then before.

-- Ralf Schmitt, Developer, Pediapress_

.. _Pediapress: http://pediapress.com/
.. _Wikipedia: http://www.wikipedia.org/


`ESN Social Software`_
----------------------

Wanting to avoid the ravages of asynchronous programming we choose to base
our real-time web development framework Planet on gevent and Python. We’ve
found gevent to be stable, efficient, highly functional and still simplistic
enough for our needs and our customer’s requirements.

-- Jonas Tärnström, Product Manager, `ESN Social Software`_

.. _ESN Social Software: http://esn.me


`Blue Shell Games`_
-------------------

At Blue Shell Games we use gevent to power the application servers that
connect more than a million daily players of our social casino games.
Recognizing that our game code is largely I/O bound — whether waiting on
a database, social networking data providers, or the clients themselves — we chose
gevent as our asynchronous networking framework. Not only does gevent offer
the best performance of any of the Python async networking packages, its
threading model makes multithreaded application servers far easier to write
than traditional kernel threading-based approaches. As our applications add
more real-time multiplayer features, gevent is ready to handle these kinds
of problems with ease.

-- David Young, CTO, Co-Founder, `Blue Shell Games`_

.. _Blue Shell Games: http://www.blueshellgames.com/


TellApart_
----------

At TellApart, we have been using gevent since 2010 as the underpinnings of
our frontend servers. It enables us to serve millions of requests every hour
through only a handful of servers, while achieving the strict latency
constraints of Real-Time Bidding ad exchanges. Since then, we've expanded
our use of gevent throughout our stack. Combined with tools such as closures
and generators, gevent makes complicated queuing, distribution, and
streaming workloads dramatically easier to implement. Our open-source event
aggregation service, Taba, couldn't have been built without it.

See also: `Gevent at TellApart`_

-- Kevin Ballard, Software Engineer, TellApart_

.. _TellApart: http://tellapart.com
.. _Gevent at TellApart: http://tellapart.com/gevent-at-tellapart


Disqus
------

See: `Making Disqus Realtime`_

.. _`Making Disqus Realtime`: https://ep2012.europython.eu/conference/talks/making-disqus-realtime


Pinterest
---------

Pinterest is one of the biggest players of gevents. We started using gevent in
2011 to query our mysql shards concurrently. It served us well so far. We run
all our WSGI containers using gevent. We are in the process of making all our
service calls gevented. We use a gevented based thrift server which proved to
be way more efficient than the normal python version. I think there is a cost
upfront to make your code greenlet safe but we saw pretty huge win later.
If you are looking to scale out on python gevent is your best friend.

-- Yash Nelapati, Engineer, Pinterest_

.. _Pinterest: http://pinterest.com/

TBA: Spotify, Twilio
