from types import coroutine
from socket import socket, SOCK_STREAM, AF_INET
from select import select
from itertools import chain
from collections import deque


SERVER_ADDR = ('localhost', 8004)


class AsyncSocket:

    def __init__(self, *args, **kwargs):
        self._sock = socket(*args, **kwargs)
        self._sock.setblocking(False)

    @classmethod
    def from_socket(cls, sock):
        async_sock = cls.__new__(cls)
        sock.setblocking(False)
        async_sock._sock = sock
        return async_sock

    @coroutine
    def sendall(self, data):
        data_ = memoryview(data)
        while data_:
            nsent = self._sock.send(data_)
            if nsent:
                data_ = data_[nsent:]
            else:
                yield 'w', self._sock.fileno()

    @coroutine
    def recv(self, buffer_size):
        while True:
            try:
                data = self._sock.recv(buffer_size)
            except BlockingIOError:
                yield 'r', self._sock.fileno()
            else:
                return data

    @coroutine
    def accept(self):
        while True:
            try:
                client_socket, client_addr = self._sock.accept()
            except BlockingIOError:
                yield 'r', self._sock.fileno()
            else:
                return self.from_socket(client_socket), client_addr

    def bind(self, address):
        self._sock.bind(address)

    def listen(self, backlog):
        self._sock.listen(backlog)

    def close(self):
        self._sock.close()

    async def __aenter__(self):
        self._sock.__enter__()
        return self

    async def __aexit__(self, *args):
        if self._sock:
            self._sock.__exit__(*args)


async def client_handler(sock, addr):
    print(f'Established connection with: {addr}')
    async with sock:
        while True:
            data = await sock.recv(4096)
            if data:
                await sock.sendall(data)
            else:
                break
    print(f'Closed connection with: {addr}')


async def echo_server(loop):
    server_sock = AsyncSocket(AF_INET, SOCK_STREAM)
    server_sock.bind(SERVER_ADDR)
    server_sock.listen(5)
    print(f'Server listening on: {SERVER_ADDR}')
    async with server_sock:
        while True:
            client_sock, client_addr = await server_sock.accept()
            loop.register(client_handler(client_sock, client_addr))


class EventLoop:
    def __init__(self):
        self.tasks = deque()
        self.waiting_tasks = {}
        self.waiting_for_read = []
        self.waiting_for_write = []

    def register(self, task):
        self.tasks.append(task)

    def run(self):
        try:
            self._run()
        except KeyboardInterrupt:
            for task in chain(self.tasks, self.waiting_tasks.values()):
                task.close()

    def _run(self):
        while self.tasks or self.waiting_tasks:
            while self.tasks:
                task = self.tasks.popleft()
                try:
                    event, fd = task.send(None)
                except StopIteration:
                    continue
                else:
                    if event == 'w':
                        self.waiting_for_write.append(fd)
                    elif event == 'r':
                        self.waiting_for_read.append(fd)
                    self.waiting_tasks[fd] = task

            r, w, _ = select(self.waiting_for_read, self.waiting_for_write, [])
            self.waiting_for_read = list(set(self.waiting_for_read) - set(r))
            self.waiting_for_write = list(set(self.waiting_for_write) - set(w))
            for fd in chain(r, w):
                self.tasks.append(self.waiting_tasks.pop(fd))


if __name__ == '__main__':
    event_loop = EventLoop()
    event_loop.register(echo_server(event_loop))
    event_loop.run()
