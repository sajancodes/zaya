"""One desktop Zaya per user, with activation of the already running window."""
import hashlib
from pathlib import Path
import tempfile

from PyQt6.QtCore import QLockFile
from PyQt6.QtNetwork import QLocalServer, QLocalSocket


class SingleInstance:
    def __init__(self, name=None, directory=None):
        identity = hashlib.sha256(str(Path.home()).casefold().encode('utf-8')).hexdigest()[:20]
        self.name = name or f'zaya-desktop-{identity}'
        self.lock = QLockFile(str(Path(directory or tempfile.gettempdir()) / f'{self.name}.lock'))
        # A long-running assistant is never stale just because time has passed.
        # Qt can still recover a lock whose owning process has exited/crashed.
        self.lock.setStaleLockTime(0)
        self.server = None
        self.on_activate = None
        self.owned = False

    def acquire(self):
        if self.owned:
            return True
        if not self.lock.tryLock(0):
            if self.lock.error() != QLockFile.LockError.LockFailedError:
                raise RuntimeError('Zaya could not acquire its startup lock.')
            self.activate_existing()
            return False
        self.owned = True
        self.server = QLocalServer()
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        # Only the lock owner may remove a socket left behind by a crashed run.
        QLocalServer.removeServer(self.name)
        self.server.newConnection.connect(self._activate)
        if not self.server.listen(self.name):
            self.close()
            raise RuntimeError('Zaya could not open its local activation connection.')
        return True

    def activate_existing(self):
        socket = QLocalSocket()
        socket.connectToServer(self.name)
        connected = socket.waitForConnected(1200)
        if connected:
            socket.write(b'activate\n')
            socket.waitForBytesWritten(500)
            socket.disconnectFromServer()
        return connected

    def _activate(self):
        while self.server and self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            socket.close()
            socket.deleteLater()
            if self.on_activate:
                self.on_activate()

    def close(self):
        if self.owned:
            if self.server:
                self.server.close()
                QLocalServer.removeServer(self.name)
                self.server = None
            self.lock.unlock()
            self.owned = False
