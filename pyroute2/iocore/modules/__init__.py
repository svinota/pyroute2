from . import connect
from . import disconnect
from . import provide
from . import reload
from . import remove
from . import serve
from . import shutdown
from . import stop
from . import subscribe
from . import discover
from . import unsubscribe
from . import register

privileged = [connect,
              disconnect,
              provide,
              reload,
              remove,
              serve,
              shutdown,
              stop,
              subscribe,
              discover,
              unsubscribe,
              register]

user = [subscribe,
        discover,
        unsubscribe,
        register]
