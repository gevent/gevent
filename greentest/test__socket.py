from gevent import proc, socket

listener = socket.tcp_listener(('127.0.0.1', 0))

def server():
    (client, addr) = listener.accept()
    # start reading, then, while reading, start writing. the reader should not hang forever
    N = 100000 # must be a big enough number so that sendall calls trampoline
    proc.spawn_greenlet(client.sendall, 't' * N) 
    result = client.recv(1000)
    assert result == 'hello world', result
    
#print '%s: client' % getcurrent()

server_proc = proc.spawn(server)
client = socket.create_connection(('127.0.0.1', listener.getsockname()[1]))
proc.spawn_greenlet(client.makefile().read)
client.send('hello world')

# close() used to hang
client.close()

# this tests "full duplex" bug which is only fixed in libevent hub at the moment
server_proc.wait()
