import logging
import logging.handlers
import os


class Logger:
    LOGGER_FORMAT = '[%(levelname)s|%(filename)s:%(lineno)s] %(asctime)s > %(message)s'
    PRINT_LOGGER_FORMAT = '%(asctime)s > %(message)s'

    def __init__(self, name, path=None, file_name='log', level=logging.INFO, stdout_only=False):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        formatter = logging.Formatter(Logger.LOGGER_FORMAT)

        self.file_handler = None
        if not stdout_only:
            self.file_handler = logging.FileHandler(os.path.join(path, file_name))
            self.file_handler.setFormatter(formatter)
            self.logger.addHandler(self.file_handler)

        self.stream_handler = logging.StreamHandler()
        self.stream_handler.setFormatter(formatter)
        self.logger.addHandler(self.stream_handler)

    def __repr__(self):
        return self.__class__.__name__

    def __del__(self):
        if self.file_handler is not None:
            self.logger.removeHandler(self.file_handler)
        self.logger.removeHandler(self.stream_handler)
        del self.logger

    def get_log(self, level='info'):
        # catch *args and make to str
        def deco(func):
            def wrapper(*args):
                msg = " ".join(map(str, args))
                return func(msg)

            return wrapper

        func = getattr(self.logger, level)
        return deco(func)


if __name__ == '__main__':
    pass
