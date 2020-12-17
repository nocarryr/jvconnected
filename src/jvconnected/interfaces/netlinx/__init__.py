from jvconnected.interfaces import registry

from .client import NetlinxClient

registry.register('netlinx', NetlinxClient)
