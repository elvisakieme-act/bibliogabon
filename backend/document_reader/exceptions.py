class ReaderError(Exception):
    pass


class ReaderAccessDenied(ReaderError):
    pass


class ReaderSessionInactive(ReaderError):
    pass


class ReaderPageUnavailable(ReaderError):
    pass
