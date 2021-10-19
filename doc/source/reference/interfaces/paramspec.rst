:mod:`jvconnected.interfaces.paramspec`
=======================================

.. module:: jvconnected.interfaces.paramspec

This module contains specifications to assist with interface implementations.
The :class:`~pydispatch.properties.Property` values associated with
:class:`jvconnected.device.ParameterGroup` subclasses are defined here with
any information necessary for getting/setting values as well as the types and
ranges of values.


ParameterGroupSpec
------------------

.. autoclass:: ParameterGroupSpec
    :members:

.. autoclass:: ExposureParams
    :members:

.. autoclass:: PaintParams
    :members:

.. autoclass:: TallyParams
    :members:

ParameterSpec
-------------

.. autoclass:: BaseParameterSpec
    :members:

.. autoclass:: ParameterSpec
    :members:

.. autoclass:: ParameterRangeMap
    :members:

.. autoclass:: MultiParameterSpec
    :members:

Value Types
-----------

.. autoclass:: Value
    :members:

.. autoclass:: BoolValue
    :members:

.. autoclass:: IntValue
    :members:

.. autoclass:: ChoiceValue
    :members:
