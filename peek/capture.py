from abc import ABCMeta


class Capture(metaclass=ABCMeta):

    def stop(self):
        pass

    def status(self):
        pass

    def file(self):
        pass


class NoOpCapture(Capture):

    def status(self):
        return 'No capture is running'


class FileCapture(Capture):

    def __init__(self, f):
        self.f = f
        self.outs = open(self.f, 'w')

    def stop(self):
        self.outs.close()

    def status(self):
        return f'Capture with file: {self.f}'

    def file(self):
        return self.outs
