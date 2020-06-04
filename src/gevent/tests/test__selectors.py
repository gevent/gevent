# Tests for gevent.selectors in its native form, without
# monkey-patching.

import gevent
from gevent import socket
from gevent import selectors

import gevent.testing as greentest

class SelectorTestMixin(object):

    @staticmethod
    def run_selector_once(sel):
        # Run in a background greenlet, leaving the main
        # greenlet free to send data.
        events = sel.select(timeout=3)
        for key, mask in events:
            key.data(sel, key.fileobj, mask)
            gevent.sleep()

    unregister_after_send = True

    def read_from_ready_socket_and_reply(self, selector, conn, _events):
        data = conn.recv(100)  # Should be ready
        if data:
            conn.send(data)  # Hope it won't block

        # Must unregister before we close.
        if self.unregister_after_send:
            selector.unregister(conn)
            conn.close()

    def _check_selector(self, sel):
        server, client = socket.socketpair()
        try:
            sel.register(server, selectors.EVENT_READ, self.read_from_ready_socket_and_reply)
            glet = gevent.spawn(self.run_selector_once, sel)
            DATA = b'abcdef'
            client.send(DATA)
            data = client.recv(50) # here is probably where we yield to the event loop
            self.assertEqual(data, DATA)
        finally:
            sel.close()
            server.close()
            client.close()
            glet.join(10)
        self.assertTrue(glet.ready())


class GeventSelectorTest(SelectorTestMixin,
                         greentest.TestCase):

    def test_select_using_socketpair(self):
        # Basic test.
        with selectors.GeventSelector() as sel:
            self._check_selector(sel)

    def test_select_many_sockets(self):
        pairs = [socket.socketpair() for _ in range(10)]
        clients = [s[1] for s in pairs]

        try:
            server_sel = selectors.GeventSelector()
            client_sel = selectors.GeventSelector()
            for i, pair in enumerate(pairs):
                server, client = pair
                server_sel.register(server, selectors.EVENT_READ,
                                    self.read_from_ready_socket_and_reply)
                client_sel.register(client, selectors.EVENT_READ, i)
            # Prime them all to be ready at once.
            for i, client in enumerate(clients):
                data = str(i).encode('ascii')
                client.send(data)

            # Read and reply to all the clients
            self.run_selector_once(server_sel)

            found = 0
            for key, _ in client_sel.select(timeout=3):
                expected = str(key.data).encode('ascii')
                data = key.fileobj.recv(50)
                self.assertEqual(data, expected)
                found += 1
            self.assertEqual(found, len(pairs))
        finally:
            server_sel.close()
            client_sel.close()
            for pair in pairs:
                for s in pair:
                    s.close()



if __name__ == '__main__':
    greentest.main()
