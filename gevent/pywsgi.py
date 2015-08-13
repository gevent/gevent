# Copyright (c) 2005-2009, eventlet contributors
# Copyright (c) 2009-2015, gevent contributors
"""
A pure-Python, gevent-friendly WSGI server.

The server is provided in :class:`WSGIServer`, but most of the actual
WSGI work is handled by :class:`WSGIHandler` --- a new instance is
created for each request. The server can be customized to use
different subclasses of :class:`WSGIHandler`.

"""
import errno
from io import BytesIO
import string
import sys
import time
import traceback
from datetime import datetime
try:
    from urllib import unquote
except ImportError:
    from urllib.parse import unquote

from gevent import socket
import gevent
from gevent.server import StreamServer
from gevent.hub import GreenletExit, PY3, reraise


__all__ = ['WSGIHandler', 'WSGIServer', 'LoggingLogAdapter']


MAX_REQUEST_LINE = 8192
# Weekday and month names for HTTP date/time formatting; always English!
_WEEKDAYNAME = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_MONTHNAME = [None,  # Dummy so we can use 1-based month numbers
              "Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# The contents of the "HEX" grammar rule for HTTP, upper and lowercase A-F plus digits,
# in byte form for comparing to the network.
_HEX = string.hexdigits.encode('ascii')

# Errors
_ERRORS = dict()
_INTERNAL_ERROR_STATUS = '500 Internal Server Error'
_INTERNAL_ERROR_BODY = b'Internal Server Error'
_INTERNAL_ERROR_HEADERS = [('Content-Type', 'text/plain'),
                           ('Connection', 'close'),
                           ('Content-Length', str(len(_INTERNAL_ERROR_BODY)))]
_ERRORS[500] = (_INTERNAL_ERROR_STATUS, _INTERNAL_ERROR_HEADERS, _INTERNAL_ERROR_BODY)

_BAD_REQUEST_STATUS = '400 Bad Request'
_BAD_REQUEST_BODY = ''
_BAD_REQUEST_HEADERS = [('Content-Type', 'text/plain'),
                        ('Connection', 'close'),
                        ('Content-Length', str(len(_BAD_REQUEST_BODY)))]
_ERRORS[400] = (_BAD_REQUEST_STATUS, _BAD_REQUEST_HEADERS, _BAD_REQUEST_BODY)

_REQUEST_TOO_LONG_RESPONSE = b"HTTP/1.1 414 Request URI Too Long\r\nConnection: close\r\nContent-length: 0\r\n\r\n"
_BAD_REQUEST_RESPONSE = b"HTTP/1.1 400 Bad Request\r\nConnection: close\r\nContent-length: 0\r\n\r\n"
_CONTINUE_RESPONSE = b"HTTP/1.1 100 Continue\r\n\r\n"


def format_date_time(timestamp):
    year, month, day, hh, mm, ss, wd, _y, _z = time.gmtime(timestamp)
    return "%s, %02d %3s %4d %02d:%02d:%02d GMT" % (_WEEKDAYNAME[wd], day, _MONTHNAME[month], year, hh, mm, ss)


class _InvalidClientInput(IOError):
    # Internal exception raised by Input indicating that the
    # client sent invalid data. The result *should* be a HTTP 400
    # error.
    pass


class Input(object):

    __slots__ = ('rfile', 'content_length', 'socket', 'position',
                 'chunked_input', 'chunk_length', '_chunked_input_error')

    def __init__(self, rfile, content_length, socket=None, chunked_input=False):
        self.rfile = rfile
        self.content_length = content_length
        self.socket = socket
        self.position = 0
        self.chunked_input = chunked_input
        self.chunk_length = -1
        self._chunked_input_error = False

    def _discard(self):
        if self._chunked_input_error:
            # We are in an unknown state, so we can't necessarily discard
            # the body (e.g., if the client keeps the socket open, we could hang
            # here forever).
            # In this case, we've raised an exception and the user of this object
            # is going to close the socket, so we don't have to discard
            return

        if self.socket is None and (self.position < (self.content_length or 0) or self.chunked_input):
            # ## Read and discard body
            while 1:
                d = self.read(16384)
                if not d:
                    break

    def _send_100_continue(self):
        if self.socket is not None:
            self.socket.sendall(_CONTINUE_RESPONSE)
            self.socket = None

    def _do_read(self, length=None, use_readline=False):
        if use_readline:
            reader = self.rfile.readline
        else:
            reader = self.rfile.read
        content_length = self.content_length
        if content_length is None:
            # Either Content-Length or "Transfer-Encoding: chunked" must be present in a request with a body
            # if it was chunked, then this function would have not been called
            return b''
        self._send_100_continue()
        left = content_length - self.position
        if length is None:
            length = left
        elif length > left:
            length = left
        if not length:
            return b''
        read = reader(length)
        self.position += len(read)
        if len(read) < length:
            if (use_readline and not read.endswith(b"\n")) or not use_readline:
                raise IOError("unexpected end of file while reading request at position %s" % (self.position,))

        return read

    def __read_chunk_length(self, rfile):
        # Read and return the next integer chunk length. If no
        # chunk length can be read, raises _InvalidClientInput.

        # Here's the production for a chunk:
        # (http://www.w3.org/Protocols/rfc2616/rfc2616-sec3.html)
        #   chunk          = chunk-size [ chunk-extension ] CRLF
        #                    chunk-data CRLF
        #   chunk-size     = 1*HEX
        #   chunk-extension= *( ";" chunk-ext-name [ "=" chunk-ext-val ] )
        #   chunk-ext-name = token
        #   chunk-ext-val  = token | quoted-string

        # To cope with malicious or broken clients that fail to send valid
        # chunk lines, the strategy is to read character by character until we either reach
        # a ; or newline. If at any time we read a non-HEX digit, we bail. If we hit a
        # ;, indicating an chunk-extension, we'll read up to the next MAX_REQUEST_LINE charaters
        # looking for the CRLF, and if we don't find it, we bail. If we read more than 16 hex characters,
        # (the number needed to represent a 64-bit chunk size), we bail (this protects us from
        # a client that sends an infinite stream of `F`, for example).

        buf = BytesIO()
        while 1:
            char = rfile.read(1)
            if not char:
                self._chunked_input_error = True
                raise _InvalidClientInput("EOF before chunk end reached")
            if char == b'\r':
                break
            if char == b';':
                break

            if char not in _HEX:
                self._chunked_input_error = True
                raise _InvalidClientInput("Non-hex data", char)
            buf.write(char)
            if buf.tell() > 16:
                self._chunked_input_error = True
                raise _InvalidClientInput("Chunk-size too large.")

        if char == b';':
            i = 0
            while i < MAX_REQUEST_LINE:
                char = rfile.read(1)
                if char == b'\r':
                    break
                i += 1
            else:
                # we read more than MAX_REQUEST_LINE without
                # hitting CR
                self._chunked_input_error = True
                raise _InvalidClientInput("Too large chunk extension")

        if char == b'\r':
            # We either got here from the main loop or from the
            # end of an extension
            char = rfile.read(1)
            if char != b'\n':
                self._chunked_input_error = True
                raise _InvalidClientInput("Line didn't end in CRLF")
            return int(buf.getvalue(), 16)

    def _chunked_read(self, length=None, use_readline=False):
        rfile = self.rfile
        self._send_100_continue()

        if length == 0:
            return b""

        if length is not None and length < 0:
            length = None

        if use_readline:
            reader = self.rfile.readline
        else:
            reader = self.rfile.read

        response = []
        while self.chunk_length != 0:
            maxreadlen = self.chunk_length - self.position
            if length is not None and length < maxreadlen:
                maxreadlen = length

            if maxreadlen > 0:
                data = reader(maxreadlen)
                if not data:
                    self.chunk_length = 0
                    self._chunked_input_error = True
                    raise IOError("unexpected end of file while parsing chunked data")

                datalen = len(data)
                response.append(data)

                self.position += datalen
                if self.chunk_length == self.position:
                    rfile.readline()

                if length is not None:
                    length -= datalen
                    if length == 0:
                        break
                if use_readline and data[-1] == b"\n"[0]:
                    break
            else:
                # We're at the beginning of a chunk, so we need to
                # determine the next size to read
                self.chunk_length = self.__read_chunk_length(rfile)
                self.position = 0
                if self.chunk_length == 0:
                    # Last chunk. Terminates with a CRLF.
                    rfile.readline()
        return b''.join(response)

    def read(self, length=None):
        if self.chunked_input:
            return self._chunked_read(length)
        return self._do_read(length)

    def readline(self, size=None):
        if self.chunked_input:
            return self._chunked_read(size, True)
        else:
            return self._do_read(size, use_readline=True)

    def readlines(self, hint=None):
        return list(self)

    def __iter__(self):
        return self

    def next(self):
        line = self.readline()
        if not line:
            raise StopIteration
        return line
    __next__ = next


try:
    import mimetools
    headers_factory = mimetools.Message
except ImportError:
    # adapt Python 3 HTTP headers to old API
    from http import client

    class OldMessage(client.HTTPMessage):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.status = ''

        def getheader(self, name, default=None):
            return self.get(name, default)

        @property
        def headers(self):
            for key, value in self._headers:
                yield '%s: %s\r\n' % (key, value)

        @property
        def typeheader(self):
            return self.get('content-type')

    def headers_factory(fp, *args):
        try:
            ret = client.parse_headers(fp, _class=OldMessage)
        except client.LineTooLong:
            ret = OldMessage()
            ret.status = 'Line too long'
        return ret


class WSGIHandler(object):
    protocol_version = 'HTTP/1.1'
    if PY3:
        # if we do like Py2, then headers_factory unconditionally
        # becomes a bound method, meaning the fp argument becomes WSGIHandler
        def MessageClass(self, *args):
            return headers_factory(*args)
    else:
        MessageClass = headers_factory

    def __init__(self, socket, address, server, rfile=None):
        self.socket = socket
        self.client_address = address
        self.server = server
        if rfile is None:
            self.rfile = socket.makefile('rb', -1)
        else:
            self.rfile = rfile

    def handle(self):
        """
        The main request handling method, called by the server.

        This method runs until all requests on the connection have
        been handled (that is, it implements pipelining).
        """
        try:
            while self.socket is not None:
                self.time_start = time.time()
                self.time_finish = 0

                result = self.handle_one_request()
                if result is None:
                    break
                if result is True:
                    continue
                self.status, response_body = result
                self.socket.sendall(response_body)
                if self.time_finish == 0:
                    self.time_finish = time.time()
                self.log_request()
                break
        finally:
            if self.socket is not None:
                _sock = getattr(self.socket, '_sock', None) # Python 3
                try:
                    # read out request data to prevent error: [Errno 104] Connection reset by peer
                    if _sock:
                        try:
                            # socket.recv would hang
                            _sock.recv(16384)
                        finally:
                            _sock.close()
                    self.socket.close()
                except socket.error:
                    pass
            self.__dict__.pop('socket', None)
            self.__dict__.pop('rfile', None)

    def _check_http_version(self):
        version = self.request_version
        if not version.startswith("HTTP/"):
            return False
        version = tuple(int(x) for x in version[5:].split("."))  # "HTTP/"
        if version[1] < 0 or version < (0, 9) or version >= (2, 0):
            return False
        return True

    def read_request(self, raw_requestline):
        """
        Process the incoming request. Parse various headers.

        :raises ValueError: If the request is invalid. This error will
           not be logged (because it's a client issue, not a server problem).
        """
        self.requestline = raw_requestline.rstrip()
        words = self.requestline.split()
        if len(words) == 3:
            self.command, self.path, self.request_version = words
            if not self._check_http_version():
                self.log_error('Invalid http version: %r', raw_requestline)
                return
        elif len(words) == 2:
            self.command, self.path = words
            if self.command != "GET":
                self.log_error('Expected GET method: %r', raw_requestline)
                return
            self.request_version = "HTTP/0.9"
            # QQQ I'm pretty sure we can drop support for HTTP/0.9
        else:
            self.log_error('Invalid HTTP method: %r', raw_requestline)
            return

        self.headers = self.MessageClass(self.rfile, 0)

        if self.headers.status:
            self.log_error('Invalid headers status: %r', self.headers.status)
            return

        if self.headers.get("transfer-encoding", "").lower() == "chunked":
            try:
                del self.headers["content-length"]
            except KeyError:
                pass

        content_length = self.headers.get("content-length")
        if content_length is not None:
            content_length = int(content_length)
            if content_length < 0:
                self.log_error('Invalid Content-Length: %r', content_length)
                return
            if content_length and self.command in ('HEAD', ):
                self.log_error('Unexpected Content-Length')
                return

        self.content_length = content_length

        if self.request_version == "HTTP/1.1":
            conntype = self.headers.get("Connection", "").lower()
            if conntype == "close":
                self.close_connection = True
            else:
                self.close_connection = False
        else:
            self.close_connection = True

        return True

    def log_error(self, msg, *args):
        try:
            message = msg % args
        except Exception:
            traceback.print_exc()
            message = '%r %r' % (msg, args)
        try:
            message = '%s: %s' % (self.socket, message)
        except Exception:
            pass

        try:
            self.server.error_log.write(message + '\n')
        except Exception:
            traceback.print_exc()

    def read_requestline(self):
        """
        Read and return the HTTP request line.

        Under both Python 2 and 3, this should return the native
        ``str`` type; under Python 3, this probably means the bytes read
        from the network need to be decoded (using the ISO-8859-1 charset, aka
        latin-1).
        """
        line = self.rfile.readline(MAX_REQUEST_LINE)
        if PY3:
            line = line.decode('latin-1')
        return line

    def handle_one_request(self):
        if self.rfile.closed:
            return
        try:
            self.requestline = self.read_requestline()
            # Account for old subclasses that haven't done this
            if PY3 and isinstance(self.requestline, bytes):
                self.requestline = self.requestline.decode('latin-1')
        except socket.error:
            # "Connection reset by peer" or other socket errors aren't interesting here
            return

        if not self.requestline:
            return

        self.response_length = 0

        if len(self.requestline) >= MAX_REQUEST_LINE:
            return ('414', _REQUEST_TOO_LONG_RESPONSE)

        try:
            # for compatibility with older versions of pywsgi, we pass self.requestline as an argument there
            if not self.read_request(self.requestline):
                return ('400', _BAD_REQUEST_RESPONSE)
        except Exception as ex:
            if not isinstance(ex, ValueError):
                traceback.print_exc()
            self.log_error('Invalid request: %s', str(ex) or ex.__class__.__name__)
            return ('400', _BAD_REQUEST_RESPONSE)

        self.environ = self.get_environ()
        self.application = self.server.application

        self.handle_one_response()

        if self.close_connection:
            return

        if self.rfile.closed:
            return

        return True  # read more requests

    def finalize_headers(self):
        if self.provided_date is None:
            self.response_headers.append(('Date', format_date_time(time.time())))

        if self.code not in (304, 204):
            # the reply will include message-body; make sure we have either Content-Length or chunked
            if self.provided_content_length is None:
                if hasattr(self.result, '__len__'):
                    self.response_headers.append(('Content-Length', str(sum(len(chunk) for chunk in self.result))))
                else:
                    if self.request_version != 'HTTP/1.0':
                        self.response_use_chunked = True
                        self.response_headers.append(('Transfer-Encoding', 'chunked'))

    def _sendall(self, data):
        try:
            self.socket.sendall(data)
        except socket.error as ex:
            self.status = 'socket error: %s' % ex
            if self.code > 0:
                self.code = -self.code
            raise
        self.response_length += len(data)

    def _write(self, data):
        if not data:
            return
        if self.response_use_chunked:
            ## Write the chunked encoding
            data = ("%x\r\n" % len(data)).encode('ascii') + data + b'\r\n'
        self._sendall(data)

    def write(self, data):
        if self.code in (304, 204) and data:
            raise AssertionError('The %s response must have no body' % self.code)

        if self.headers_sent:
            self._write(data)
        else:
            if not self.status:
                raise AssertionError("The application did not call start_response()")
            self._write_with_headers(data)

    def _write_with_headers(self, data):
        towrite = bytearray()
        self.headers_sent = True
        self.finalize_headers()

        towrite.extend(('HTTP/1.1 %s\r\n' % self.status).encode('latin-1'))
        for header in self.response_headers:
            towrite.extend(('%s: %s\r\n' % header).encode('latin-1'))

        towrite.extend(b'\r\n')
        if data:
            if self.response_use_chunked:
                ## Write the chunked encoding
                towrite.extend(("%x\r\n" % len(data)).encode('latin-1'))
                towrite.extend(data)
                towrite.extend(b"\r\n")
            else:
                try:
                    towrite.extend(data)
                except TypeError:
                    raise TypeError("Not an bytestring", data)
        self._sendall(towrite)

    def start_response(self, status, headers, exc_info=None):
        if exc_info:
            try:
                if self.headers_sent:
                    # Re-raise original exception if headers sent
                    reraise(*exc_info)
            finally:
                # Avoid dangling circular ref
                exc_info = None
        self.code = int(status.split(' ', 1)[0])
        self.status = status
        self.response_headers = headers

        provided_connection = None
        self.provided_date = None
        self.provided_content_length = None

        for header, value in headers:
            header = header.lower()
            if header == 'connection':
                provided_connection = value
            elif header == 'date':
                self.provided_date = value
            elif header == 'content-length':
                self.provided_content_length = value

        if self.request_version == 'HTTP/1.0' and provided_connection is None:
            headers.append(('Connection', 'close'))
            self.close_connection = True
        elif provided_connection == 'close':
            self.close_connection = True

        if self.code in (304, 204):
            if self.provided_content_length is not None and self.provided_content_length != '0':
                msg = 'Invalid Content-Length for %s response: %r (must be absent or zero)' % (self.code, self.provided_content_length)
                if PY3:
                    msg = msg.encode('latin-1')
                raise AssertionError(msg)

        return self.write

    def log_request(self):
        self.server.log.write(self.format_request() + '\n')

    def format_request(self):
        now = datetime.now().replace(microsecond=0)
        length = self.response_length or '-'
        if self.time_finish:
            delta = '%.6f' % (self.time_finish - self.time_start)
        else:
            delta = '-'
        client_address = self.client_address[0] if isinstance(self.client_address, tuple) else self.client_address
        return '%s - - [%s] "%s" %s %s %s' % (
            client_address or '-',
            now,
            getattr(self, 'requestline', ''),
            (getattr(self, 'status', None) or '000').split()[0],
            length,
            delta)

    def process_result(self):
        for data in self.result:
            if data:
                self.write(data)
        if self.status and not self.headers_sent:
            self.write(b'')
        if self.response_use_chunked:
            self.socket.sendall(b'0\r\n\r\n')
            self.response_length += 5

    def run_application(self):
        self.result = self.application(self.environ, self.start_response)
        self.process_result()

    def handle_one_response(self):
        self.time_start = time.time()
        self.status = None
        self.headers_sent = False

        self.result = None
        self.response_use_chunked = False
        self.response_length = 0

        try:
            try:
                self.run_application()
            finally:
                close = getattr(self.result, 'close', None)
                if close is not None:
                    close()
                try:
                    self.wsgi_input._discard()
                except (socket.error, IOError):
                    # Don't let exceptions during discarding
                    # input override any exception that may have been
                    # raised by the application, such as our own _InvalidClientInput.
                    # In the general case, these aren't even worth logging (see the comment
                    # just below)
                    pass
        except _InvalidClientInput:
            self._send_error_response_if_possible(400)
        except socket.error as ex:
            if ex.args[0] in (errno.EPIPE, errno.ECONNRESET):
                # Broken pipe, connection reset by peer.
                # Swallow these silently to avoid spewing
                # useless info on normal operating conditions,
                # bloating logfiles. See https://github.com/gevent/gevent/pull/377
                # and https://github.com/gevent/gevent/issues/136.
                if not PY3:
                    sys.exc_clear()
                self.close_connection = True
            else:
                self.handle_error(*sys.exc_info())
        except:
            self.handle_error(*sys.exc_info())
        finally:
            self.time_finish = time.time()
            self.log_request()

    def _send_error_response_if_possible(self, error_code):
        if self.response_length:
            self.close_connection = True
        else:
            status, headers, body = _ERRORS[error_code]
            self.start_response(status, headers[:])
            self.write(body)

    def handle_error(self, type, value, tb):
        if not issubclass(type, GreenletExit):
            self.server.loop.handle_error(self.environ, type, value, tb)
        del tb
        self._send_error_response_if_possible(500)

    def _headers(self):
        key = None
        value = None
        for header in self.headers.headers:
            if key is not None and header[:1] in " \t":
                value += header
                continue

            if key not in (None, 'CONTENT_TYPE', 'CONTENT_LENGTH'):
                yield 'HTTP_' + key, value.strip()

            key, value = header.split(':', 1)
            key = key.replace('-', '_').upper()

        if key not in (None, 'CONTENT_TYPE', 'CONTENT_LENGTH'):
            yield 'HTTP_' + key, value.strip()

    def get_environ(self):
        env = self.server.get_environ()
        env['REQUEST_METHOD'] = self.command
        env['SCRIPT_NAME'] = ''

        if '?' in self.path:
            path, query = self.path.split('?', 1)
        else:
            path, query = self.path, ''
        env['PATH_INFO'] = unquote(path)
        env['QUERY_STRING'] = query

        if self.headers.typeheader is not None:
            env['CONTENT_TYPE'] = self.headers.typeheader

        length = self.headers.getheader('content-length')
        if length:
            env['CONTENT_LENGTH'] = length
        env['SERVER_PROTOCOL'] = self.request_version

        client_address = self.client_address
        if isinstance(client_address, tuple):
            env['REMOTE_ADDR'] = str(client_address[0])
            env['REMOTE_PORT'] = str(client_address[1])

        for key, value in self._headers():
            if key in env:
                if 'COOKIE' in key:
                    env[key] += '; ' + value
                else:
                    env[key] += ',' + value
            else:
                env[key] = value

        if env.get('HTTP_EXPECT') == '100-continue':
            socket = self.socket
        else:
            socket = None
        chunked = env.get('HTTP_TRANSFER_ENCODING', '').lower() == 'chunked'
        self.wsgi_input = Input(self.rfile, self.content_length, socket=socket, chunked_input=chunked)
        env['wsgi.input'] = self.wsgi_input
        return env


class _NoopLog(object):
    # Does nothing; implements just enough file-like methods
    # to pass the WSGI validator

    def write(self, *args, **kwargs):
        return

    def flush(self):
        pass

    def writelines(self, *args, **kwargs):
        pass


class LoggingLogAdapter(object):
    """
    An adapter for :class:`logging.Logger` instances
    to let them be used with :class:`WSGIServer`.

    .. warning:: Unless the entire process is monkey-patched at a very
        early part of the lifecycle (before logging is configured),
        loggers are likely to not be gevent-cooperative. For example,
        the socket and syslog handlers use the socket module in a way
        that can block, and most handlers acquire threading locks.

    .. warning:: It *may* be possible for the logging functions to be
       called in the :class:`gevent.Hub` greenlet. Code running in the
       hub greenlet cannot use any gevent blocking functions without triggering
       a ``LoopExit``.

    .. versionadded:: 1.1a3
    """

    # gevent avoids importing and using logging because importing it and
    # creating loggers creates native locks unless monkey-patched.

    def __init__(self, logger, level=20):
        """
        Write information to the *logger* at the given *level* (default to INFO).
        """
        self.logger = logger
        self.level = level

    def write(self, msg):
        self.logger.log(self.level, msg)

    def flush(self):
        "No-op; required to be a file-like object"
        pass

    def writelines(self, lines):
        for line in lines:
            self.write(line)


class WSGIServer(StreamServer):
    """
    A WSGI server based on :class:`StreamServer` that supports HTTPS.


    :keyword log: If given, an object with a ``write`` method to which
        request (access) logs will be written. If not given, defaults to
        :obj:`sys.stderr`. You may pass ``None`` to disable request
        logging. You may use a wrapper, around e.g., :mod:`logging`,
        to support objects that don't implement a ``write`` method.
        (If you pass a :class:`logging.Logger` instance, such a
        wrapper will automatically be created and it will be logged to
        at the :data:`logging.INFO` level.)

    :keyword error_log: If given, a file-like object with ``write``,
        ``writelines`` and ``flush`` methods to which error logs will
        be written. If not given, defaults to :obj:`sys.stderr`. You
        may pass ``None`` to disable error logging (not recommended).
        You may use a wrapper, around e.g., :mod:`logging`, to support
        objects that don't implement the proper methods. (If you pass
        a :class:`logging.Logger` instance, such a wrapper will
        automatically be created, and it will be logged to at the
        :data:`logging.ERROR` level.) This parameter will become the
        value for ``wsgi.errors`` in the WSGI environment (if not already set).

    .. seealso::

        :class:`LoggingLogAdapter`
            See important warnings before attempting to use :mod:`logging`.

    .. versionchanged:: 1.1a3
        Added the ``error_log`` parameter, and set ``wsgi.errors`` in the WSGI
        environment to this value.
    .. versionchanged:: 1.1a3
        Add support for passing :class:`logging.Logger` objects to the ``log`` and
        ``error_log`` arguments.
    """

    handler_class = WSGIHandler

    #: The object to which request logs will be written.
    #: It must never be None. Initialized from the ``log`` constructor
    #: parameter.
    log = None

    #: The object to which error logs will be written.
    #: It must never be None. Initialized from the ``error_log`` constructor
    #: parameter.
    error_log = None

    base_env = {'GATEWAY_INTERFACE': 'CGI/1.1',
                'SERVER_SOFTWARE': 'gevent/%d.%d Python/%d.%d' % (gevent.version_info[:2] + sys.version_info[:2]),
                'SCRIPT_NAME': '',
                'wsgi.version': (1, 0),
                'wsgi.multithread': False,
                'wsgi.multiprocess': False,
                'wsgi.run_once': False}

    def __init__(self, listener, application=None, backlog=None, spawn='default',
                 log='default', error_log='default',
                 handler_class=None,
                 environ=None, **ssl_args):
        StreamServer.__init__(self, listener, backlog=backlog, spawn=spawn, **ssl_args)
        if application is not None:
            self.application = application
        if handler_class is not None:
            self.handler_class = handler_class

        # Note that we can't initialize these as class variables:
        # sys.stderr might get monkey patched at runtime.
        def _make_log(l, level=20):
            if l == 'default':
                return sys.stderr
            if l is None:
                return _NoopLog()
            if not hasattr(l, 'write') and hasattr(l, 'log'):
                return LoggingLogAdapter(l, level)
            return l
        self.log = _make_log(log)
        self.error_log = _make_log(error_log, 40) # logging.ERROR

        self.set_environ(environ)
        self.set_max_accept()

    def set_environ(self, environ=None):
        if environ is not None:
            self.environ = environ
        environ_update = getattr(self, 'environ', None)
        self.environ = self.base_env.copy()
        if self.ssl_enabled:
            self.environ['wsgi.url_scheme'] = 'https'
        else:
            self.environ['wsgi.url_scheme'] = 'http'
        if environ_update is not None:
            self.environ.update(environ_update)
        if self.environ.get('wsgi.errors') is None:
            self.environ['wsgi.errors'] = self.error_log

    def set_max_accept(self):
        if self.environ.get('wsgi.multiprocess'):
            self.max_accept = 1

    def get_environ(self):
        return self.environ.copy()

    def init_socket(self):
        StreamServer.init_socket(self)
        self.update_environ()

    def update_environ(self):
        """
        Called before the first request is handled to fill in WSGI environment values.

        This includes getting the correct server name and port.
        """
        address = self.address
        if isinstance(address, tuple):
            if 'SERVER_NAME' not in self.environ:
                try:
                    name = socket.getfqdn(address[0])
                except socket.error:
                    name = str(address[0])
                if PY3 and not isinstance(name, str):
                    name = name.decode('ascii')
                self.environ['SERVER_NAME'] = name
            self.environ.setdefault('SERVER_PORT', str(address[1]))
        else:
            self.environ.setdefault('SERVER_NAME', '')
            self.environ.setdefault('SERVER_PORT', '')

    def handle(self, socket, address):
        """
        Create an instance of :attr:`handler_class` to handle the request.

        This method blocks until the handler returns.
        """
        handler = self.handler_class(socket, address, self)
        handler.handle()
