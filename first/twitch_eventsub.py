from first.twitch import AuthenticatedTwitch
from first.authdb import UserId
import json
import logging
import threading
import typing
import websockets
import websockets.sync.client

logger = logging.getLogger(__name__)

class TwitchEventSubWebSocketManager:
    """Zero or more Twitch's EventSub connections.

    Supports dynamically making new connections.

    This object is thread-safe.
    """

    _lock: threading.Lock
    _create_thread: typing.Callable[[AuthenticatedTwitch], "TwitchEventSubWebSocketThread"]

    # Protected by _lock:
    _threads: "typing.List[TwitchEventSubWebSocketThread]"
    _threads_which_failed_to_stop: "typing.List[TwitchEventSubWebSocketThread]"

    def __init__(self, factory: typing.Callable[[AuthenticatedTwitch], "TwitchEventSubWebSocketThread"]) -> None:
        self._lock = threading.Lock()
        self._create_thread = factory
        self._threads = []
        self._threads_which_failed_to_stop = []

    def create_new_connection(self, twitch: AuthenticatedTwitch) -> "TwitchEventSubWebSocketThread":
        """Create a TwitchEventSubWebSocketThread for the given
        authenticated user.

        The returned TwitchEventSubWebSocketThread has not started yet.
        You should call add_subscription then start_thread.
        """
        thread = self._create_thread(twitch)
        with self._lock:
            self._threads.append(thread)
        return thread

    def stop_connections_for_user(self, user_id: UserId) -> None:
        """Find existing connections authenticated with the given user and stop them.
        """
        with self._lock:
            threads_to_stop = []
            new_threads = []
            for thread in self._threads:
                if thread._twitch.get_self_user_id_fast() == user_id:
                    threads_to_stop.append(thread)
                else:
                    new_threads.append(thread)
            self._threads = new_threads
        for thread in threads_to_stop:
            self._stop_connection(thread)

    def stop_all_connections(self) -> None:
        # Stop threads one at a time. If a thread fails to stop,
        # remember it for debugging purposes and try to close the other
        # threads.
        while True:
            with self._lock:
                if not self._threads:
                    # We stopped all the threads.
                    break
                thread = self._threads.pop()
            try:
                self._stop_connection(thread)
            except Exception:
                logger.warning("failed to stop thread", exc_info=True)
                continue  # Try stopping the next thread.

    def _stop_connection(self, thread) -> None:
        """Precondition: thread has already been removed from self._threads.
        """
        with self._lock:
            assert thread not in self._threads

        try:
            thread.stop_thread()
        except BaseException:
            with self._lock:
                self._threads_which_failed_to_stop.append(thread)
            raise

    def get_all_threads_for_testing(self) -> "typing.List[TwitchEventSubWebSocketThread]":
        with self._lock:
            return list(self._threads)

class TwitchEventSubWebSocketThreadBase:
    _lock: threading.Lock
    _twitch: AuthenticatedTwitch

    def __init__(self, twitch: AuthenticatedTwitch) -> None:
        self._lock = threading.Lock()
        self._twitch = twitch

class TwitchEventSubWebSocketThread(TwitchEventSubWebSocketThreadBase):
    """A single WebSocket connection for Twitch's EventSub API.

    This object is thread-safe.

    Documentation for the websockets package:
    https://websockets.readthedocs.io/en/stable/reference/sync/client.html
    """

    # Protected by _lock:
    _subscriptions: "typing.List[_Subscription]"
    _thread: typing.Optional[threading.Thread] = None
    _should_stop: bool = False

    # Protected by _lock; assignable only by background thread:
    _client: typing.Optional[websockets.sync.client.ClientConnection] = None

    def __init__(self, twitch: AuthenticatedTwitch) -> None:
        super().__init__(twitch)
        self._subscriptions = []

    class _Subscription(typing.NamedTuple):
        type: str
        version: str
        condition: typing.Any

    def add_subscription(self, type: str, version: str, condition) -> None:
        """Add an EventSub subscription when the WebSocket connects.

        Precondition: The thread must not be running. (Dynamic
        subscriptions are not yet implemented.)
        """
        with self._lock:
            if self._thread is not None:
                raise NotImplemented("dynamic subscriptions are not yet implemented")
            self._subscriptions.append(self._Subscription(type=type, version=version, condition=condition))

    def start_thread(self) -> None:
        """Start a Python thread which connects to Twitch EventSub.

        Precondition: There must have been at least one subscription
        registered with add_subscription.

        Precondition: The thread must not be running.
        """
        with self._lock:
            assert self._subscriptions, "at least one subscription is required"
            assert self._thread is None or not self._thread.is_alive(), "thread must not be already running"
            self._thread = threading.Thread(target=self._run_thread)
            self._thread.start()

    def stop_thread(self) -> None:
        """Stop the Python thread which connects to Twitch EventSub.

        If the thread is not running, this function does nothing.
        """
        logger.info("stopping thread...")
        with self._lock:
            self._should_stop = True

            client = self._client
        if client is not None:
            # This should raise websockets.ConnectionClosedOK on the
            # running thread.
            # TODO(strager): Untested.
            client.close()

        with self._lock:
            thread = self._thread
        if thread is not None:
            thread.join()

    def _run_thread(self) -> None:
        while True:
            client = self._maybe_create_client()
            if client is None:
                # The user asked us to stop.
                break
            try:
                self._handle_client(client)
            finally:
                client.close()
                with self._lock:
                    self._client = None

    def _maybe_create_client(self) -> None:
        with self._lock:
            assert self._client is None
            if self._should_stop:
                return None

        client = websockets.sync.client.connect("wss://eventsub.wss.twitch.tv/ws")

        with self._lock:
            assert self._client is None
            if self._should_stop:
                # The user asked us to stop while we were connecting.
                client.close()
                return None
            self._client = client

        return client

    def _handle_client(self, client: websockets.sync.client.ClientConnection) -> None:
        while True:
            try:
                message = client.recv()
            except websockets.ConnectionClosedOK:
                logger.info("WebSocket disconnected")
                # TODO(strager): Backoff.
                return
            except websockets.ConnectionClosedError:
                logger.info("WebSocket closed with an error", exc_info=True)
                # FIXME(strager): What should we do here?
                return
            self._handle_raw_message(message)

    def _handle_raw_message(self, message: typing.Union[str, bytes]) -> None:
        if isinstance(message, str):
            # TODO(strager): What should we do on JSON parse error?
            self._handle_json_message(json.loads(message))
        else:
            raise TypeError(f"unsupported message type: {type(message)}")

    def _handle_json_message(self, message) -> None:
        logger.info("incoming message: %s", message)
        if message["metadata"]["message_type"] == "session_welcome":
            session_id = message['payload']['session']['id']
            with self._lock:
                subscriptions = list(self._subscriptions)
            for subscription in subscriptions:
                self._twitch.request_eventsub_subscription({
                    "type": subscription.type,
                    "version": subscription.version,
                    "condition": subscription.condition,
                    "transport": {
                        "method": "websocket",
                        "session_id": session_id,
                    },
                })

class FakeTwitchEventSubWebSocketThread(TwitchEventSubWebSocketThreadBase):
    """Like TwitchEventSubWebSocketThread, but with behavior stubbed out
    for testing.
    """

    # Protected by _lock:
    _thread_is_running: bool = False

    def add_subscription(self, type: str, version: str, condition) -> None:
        pass

    def start_thread(self) -> None:
        with self._lock:
            self._thread_is_running = True

    def stop_thread(self) -> None:
        with self._lock:
            self._thread_is_running = False

    @property
    def running(self) -> bool:
        with self._lock:
            return self._thread_is_running
