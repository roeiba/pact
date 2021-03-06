import functools
import logbook
import sys
from logbook.utils import deprecated

import waiting
from waiting.exceptions import TimeoutExpired

from ._compat import reraise

_logger = logbook.Logger(__name__)


class PactBase(object):

    def __init__(self):
        super(PactBase, self).__init__()
        self._triggered = False # Make sure we only trigger 'then' once, even if using greenlets
        self._finished = False
        self._then = []
        self._during = []
        self._timeout_callbacks = []
        self._timeout_seconds = None
        _logger.debug("{0!r} was created", self)

    def _validate_can_add_callback(self):
        if self._finished:
            raise RuntimeError('Cannot append then callbacks after pact was finished')

    def get_timeout_exception(self, exc_info): # pylint: disable=no-self-use, unused-argument
        """Returns exception to be used when wait() times out. Default reraises waiting.TimeoutExpired.
        """
        return None

    def is_finished(self):
        """Returns whether or not this pact is finished
        """
        return self._finished

    def poll(self):
        """Checks all predicates to see if we're finished
        """
        if self._finished:
            return True

        for callback in self._during:
            callback()

        self._finished = self._is_finished()
        exc_info = None

        if self._finished and not self._triggered:
            self._triggered = True
            for callback in self._then:
                try:
                    callback()
                except Exception: # pylint: disable=broad-except
                    if exc_info is None:
                        exc_info = sys.exc_info()
                    _logger.debug("Exception thrown from 'then' callback {0!r} of {1!r}",
                                  callback, self, exc_info=True)
        if exc_info is not None:
            reraise(*exc_info)

        return self.is_finished()


    @deprecated('Use poll() and/or is_finished() instead')
    def finished(self):
        """Deprecated. Use poll() or is_finished() instead
        """
        self.poll()
        return self.is_finished()


    def then(self, callback, *args, **kwargs):
        """Calls ``callback`` when this pact is finished
        """
        assert callable(callback)
        self._validate_can_add_callback()
        self._then.append(functools.partial(callback, *args, **kwargs))
        return self

    def during(self, callback, *args, **kwargs):
        """Calls ``callback`` periodically while waiting for the pact to finish
        """
        assert callable(callback)
        self._validate_can_add_callback()
        self._during.append(functools.partial(callback, *args, **kwargs))
        return self

    def on_timeout(self, callback, *args, **kwargs):
        """Calls ``callback`` when a wait timeout is encountered
        """
        assert callable(callback)
        self._validate_can_add_callback()
        self._timeout_callbacks.append(functools.partial(callback, *args, **kwargs))
        return self

    def set_default_timeout(self, timeout_seconds):
        """ Sets the default timeout for the pact. It will be used when pact.wait() is called.
        """
        self._timeout_seconds = timeout_seconds

    def _is_finished(self):
        raise NotImplementedError()  # pragma: no cover

    def wait(self, timeout_seconds=None, **kwargs):
        """Waits for this pact to finish
        If timeout_seconds is set, it will be used as the timeout.
        Otherwise the last value set by set_default_timeout will be used.
        If not set at all, the wait will be executed with timeout_seconds=None and will have infinite wait.
        """
        if timeout_seconds is None:
            timeout_seconds = self._timeout_seconds

        _logger.debug("Waiting for {0!r}", self)
        try:
            waiting.wait(self.poll, waiting_for=self, timeout_seconds=timeout_seconds, **kwargs)
            _logger.debug("Finish waiting for {0!r}", self)
        except TimeoutExpired:
            exc_info = sys.exc_info()
            for timeout_callback in self._timeout_callbacks:
                timeout_callback()
            exc = self.get_timeout_exception(exc_info)
            if exc is None:
                reraise(*exc_info)
            else:
                raise exc # pylint: disable=raising-bad-type
        except Exception:
            _logger.debug("Exception was raised while waiting for {0!r}", self, exc_info=True)
            raise

    def __repr__(self):
        raise NotImplementedError() # pragma: no cover
