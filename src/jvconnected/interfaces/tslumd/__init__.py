"""Implementation of the `UMDv5.0 Protocol`_ by `TSL Products`_ for tally
and other production display/control purposes.

.. _UMDv5.0 Protocol: https://tslproducts.com/media/1959/tsl-umd-protocol.pdf
.. _TSL Products: https://tslproducts.com
"""
from jvconnected.interfaces import registry
from .common import TallyColor, TallyType, TallyState
from .umd_io import UmdIo, Tally
registry.register('tslumd', UmdIo)
