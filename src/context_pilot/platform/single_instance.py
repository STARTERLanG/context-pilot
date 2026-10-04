"""单实例控制：确保只有一个 ContextPilot 进程，二次启动唤起已有窗口。"""

import getpass

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

_CONNECT_TIMEOUT_MS = 300
_SHOW_COMMAND = b"SHOW\n"


class SingleInstance(QObject):
    """持有本地套接字服务；二次启动时发出 show_requested 让已有实例浮出窗口。"""

    show_requested = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._name = f"ContextPilot-{getpass.getuser()}"
        self._server: QLocalServer | None = None

    def try_acquire(self) -> bool:
        """抢到唯一实例返回 True；发现已有实例则通知它并返回 False。"""
        if self._notify_existing():
            return False

        # 没有实例在跑，抢注服务名
        QLocalServer.removeServer(self._name)
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._on_new_connection)
        if self._server.listen(self._name):
            return True

        # 极窄竞态：另一个实例刚抢注，再通知一次
        self._notify_existing()
        return False

    def _notify_existing(self) -> bool:
        socket = QLocalSocket()
        socket.connectToServer(self._name)
        if not socket.waitForConnected(_CONNECT_TIMEOUT_MS):
            return False
        socket.write(_SHOW_COMMAND)
        socket.flush()
        socket.waitForBytesWritten(_CONNECT_TIMEOUT_MS)
        socket.disconnectFromServer()
        return True

    def _on_new_connection(self) -> None:
        if self._server is None:
            return
        connection = self._server.nextPendingConnection()
        if connection is None:
            return
        connection.readyRead.connect(lambda: self._on_ready(connection))
        connection.disconnected.connect(connection.deleteLater)

    def _on_ready(self, connection: QLocalSocket) -> None:
        if b"SHOW" in bytes(connection.readAll()):
            self.show_requested.emit()
