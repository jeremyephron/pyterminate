# pyterminate

Reliably run cleanup upon program termination.

## Quickstart

```python3
import signal

import pyterminate

@pyterminate.register(signals=(signal.SIGINT, signal.SIGTERM))
def cleanup():
    ...

# or

def cleanup(a, b):
    ...

pyterminate.register(cleanup, args=(None, 42))
```
