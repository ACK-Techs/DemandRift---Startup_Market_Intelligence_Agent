"""Payload-free structured diagnostics, with a closed list of public fields."""
import json
import logging
from uuid import UUID

_log = logging.getLogger('demandrift.runtime')
_FIELDS = {'user_id', 'project_id', 'research_id', 'job_id', 'stage', 'status',
           'requests', 'bytes', 'tokens', 'cost_usd', 'attempts', 'checkpoint'}

def record(event, **fields):
    if event not in ('stage', 'recovery', 'delivery', 'retention', 'dependency'):
        raise ValueError('Known runtime event required')
    if set(fields)-_FIELDS:
        raise ValueError('Public diagnostic fields only')
    value = {'event': event}
    for key, item in fields.items():
        if key.endswith('_id'):
            if type(item) is not UUID:
                raise ValueError('Resolved diagnostic identity required')
            item = str(item)
        elif key in ('stage', 'status'):
            if not isinstance(item, str) or len(item)>48 or any(c not in 'abcdefghijklmnopqrstuvwxyz_0123456789' for c in item):
                raise ValueError('Bounded diagnostic code required')
        elif key=='cost_usd':
            from decimal import Decimal
            if Decimal(item)<0: raise ValueError('Nonnegative cost required')
        elif type(item) is not int or item<0:
            raise ValueError('Nonnegative counter required')
        value[key] = item
    # WARNING is configured in both API and worker; bodies and exception strings
    # are deliberately excluded, including from failed recovery paths.
    _log.warning(json.dumps(value, separators=(',', ':')))
