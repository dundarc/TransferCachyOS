from threading import Thread

from PySide6.QtCore import QObject, Signal, Slot


class ReadTask(QObject):
    """Run a bounded read-only query without blocking the Qt event loop."""

    completed = Signal(object, object)
    _reply = Signal(object, object)

    def __init__(self, parent):
        super().__init__(parent)
        self.running = False
        self._reply.connect(self._deliver)

    def start(self, query, *arguments):
        if self.running:
            return False
        self.running = True

        def work():
            try:
                result, error = query(*arguments), None
            except Exception as exception:
                result, error = None, exception
            try:
                self._reply.emit(result, error)
            except RuntimeError:
                # The owning window can close while a read-only query is running.
                pass

        Thread(target=work, daemon=True).start()
        return True

    @Slot(object, object)
    def _deliver(self, result, error):
        self.running = False
        self.completed.emit(result, error)
