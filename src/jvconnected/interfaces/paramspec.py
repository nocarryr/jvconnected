from __future__ import annotations
from typing import List, Dict, Any, ClassVar, Iterator, Optional
from dataclasses import dataclass, field

from pydispatch import Dispatcher, Property, ListProperty

__all__ = (
    'ParameterGroupSpec', 'ExposureParams', 'PaintParams', 'TallyParams',
    'BaseParameterSpec', 'ParameterSpec', 'MultiParameterSpec',
    'Value', 'BoolValue', 'ChoiceValue',
)

@dataclass
class Value:
    """Base class for value definitions
    """
    py_type = str

@dataclass
class BoolValue(Value):
    """A boolean value definition
    """
    py_type = bool

@dataclass
class IntValue(Value):
    """A numeric value definition
    """
    py_type = int

    value_min: int = 0
    """Minimum value of the parameter"""

    value_max: int = 255
    """Maximum value of the parameter"""

    value_default: int = 0
    """Default or natural center of value range"""

@dataclass
class ChoiceValue(Value):
    """A string value definition with a defined set of choices
    """
    py_type = str
    choices: List[str] = field(default_factory=list)
    """The expected string values for the parameter"""


class BaseParameterSpec(Dispatcher):
    """Base Parameter Spec
    """

    def on_device_value_changed(self, param: 'ParameterSpec', value: Any):
        """Fired when the parameter value has changed on the device
        """

    _doc_field_names: ClassVar[List[str]] = []

    group_name: str = ''
    """The name of the :class:`~jvconnected.device.ParameterGroup` as accessed by
    the ``parameter_groups`` attribute of :class:`~jvconnected.device.Device`
    """

    name: str = ''
    """The parameter name, typically the same as :attr:`prop_name`"""

    full_name: str = ''
    """Combination of :attr:`group_name` and :attr:`name`"""

    setter_method: str = ''
    """Method name on the :class:`~jvconnected.device.ParameterGroup`
    used to set the parameter value (if available)
    """

    adjust_method: str = ''
    """Method name on the :class:`~jvconnected.device.ParameterGroup`
    used to increment/decrement the parameter value such as
    :meth:`jvconnected.device.ExposureParams.adjust_iris`
    """

    _events_ = ['on_device_value_changed']

    def __init__(self, **kwargs):
        self._param_group_spec = None
        self._device_param_group = None
        self.group_name = kwargs.get('group_name', '')
        self.name = kwargs.get('name', '')
        self.full_name = kwargs.get('full_name', '')
        self.setter_method = kwargs.get('setter_method', '')
        self.adjust_method = kwargs.get('adjust_method', '')

    @property
    def param_group_spec(self) -> Optional['ParameterGroupSpec']:
        """The parent :class:`ParameterGroupSpec` instance
        """
        return self._param_group_spec
    @param_group_spec.setter
    def param_group_spec(self, pgs: Optional['ParameterGroupSpec']):
        self._param_group_spec = pgs
        if pgs is None:
            self.device_param_group = None
        else:
            self.device_param_group = pgs.device_param_group

    @property
    def device_param_group(self) -> Optional['jvconnected.device.ParameterGroup']:
        """The :class:`jvconnected.device.ParameterGroup` bound to this instance
        """
        return self._device_param_group
    @device_param_group.setter
    def device_param_group(self, pg: Optional['jvconnected.device.ParameterGroup']):
        old = self.device_param_group
        if old is not None:
            old.unbind(self)
        self._device_param_group = pg
        if pg is not None:
            self._bind_to_param_group(pg)

    def _bind_to_param_group(self, pg: 'jvconnected.device.ParameterGroup'):
        pass

    def copy(self) -> 'BaseParameterSpec':
        kw = self._build_copy_kwargs()
        cls = self.__class__
        return cls(**kw)

    def _build_copy_kwargs(self) -> Dict:
        attrs = ['group_name', 'name', 'full_name', 'setter_method', 'adjust_method']
        return {attr:getattr(self, attr) for attr in attrs}

    async def increment_value(self):
        """Increment the device value
        """
        await self.adjust_param_value(True)

    async def decrement_value(self):
        """Decrement the device value
        """
        await self.adjust_param_value(False)

    async def adjust_value(self, direction: bool):
        """Increment or decrement the device value

        Arguments:
            direction (bool): If True, increment, otherwise decrement

        Raises:
            ValueError: If there is no :attr:`adjust_method` defined

        """
        pg = self.device_param_group
        if not self.adjust_method:
            raise ValueError(f'No adjust method for {self}')
        m = getattr(pg, self.adjust_method)
        await m(direction)

    def build_docstring_lines(self, indent=0):
        indent_str = ' ' * indent
        lines = []
        # attrs = ['full_name', 'prop_name', 'value_type', 'setter_method', 'adjust_method']
        for attr in self._doc_field_names:
            val = getattr(self, attr)
            if val is None or val == '':
                continue
            valstr = str(val)
            if attr == 'value_type':
                clsname = str(val.__class__).rstrip("'>").split('.')[-1]
                valstr = f':class:`{clsname}`'
                if isinstance(val, ChoiceValue):
                    valstr = f'{valstr}: ``choices={val.choices}``'
                elif isinstance(val, IntValue):
                    valstr = f'{valstr}: ``value_min={val.value_min}, value_max={val.value_max}``'
            else:
                valstr = f'``"{valstr}"``'
            s = f'{indent_str}* **{attr}**: {valstr}'
            lines.append(s)
        return lines

class ParameterSpec(BaseParameterSpec):
    """Specifications for a single parameter within a
    :class:`jvconnected.device.ParameterGroup`
    """

    _doc_field_names: ClassVar[List[str]] = [
        'full_name', 'prop_name', 'value_type',
        'setter_method', 'adjust_method',
    ]

    prop_name: str = ''
    """The Property/attribute name within the
    :class:`jvconnected.device.ParameterGroup` containing the parameter value
    """

    value_type: Value = field(default_factory=Value)
    """Specifications for the expected value of the attribute in
    :class:`~jvconnected.device.ParameterGroup`

    One of :class:`BoolValue`, :class:`IntValue`, or :class:`ChoiceValue`
    """

    value: Any = Property()
    """The current device value"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.prop_name = kwargs.get('prop_name', '')
        self.value_type = kwargs['value_type']
        if not len(self.prop_name):
            self.prop_name = self.name

    def _build_copy_kwargs(self) -> Dict:
        kw = super()._build_copy_kwargs()
        attrs = ['prop_name', 'value_type']
        kw.update({attr:getattr(self, attr) for attr in attrs})
        return kw

    def _bind_to_param_group(self, pg: 'jvconnected.device.ParameterGroup'):
        self.value = self.get_param_value()
        pg.bind(**{self.prop_name:self.on_device_prop_change})

    def on_device_prop_change(self, instance, value, **kwargs):
        if instance is not self.device_param_group:
            return
        prop = kwargs['property']
        assert prop.name == self.prop_name
        assert value == self.get_param_value()
        self.value = value
        self.emit('on_device_value_changed', self, self.value,
            prop_name=prop.name, value_type=self.value_type,
        )

    def get_param_value(self) -> Any:
        """Get the current device value
        """
        pg = self.device_param_group
        value = getattr(pg, self.prop_name)
        if value is not None:
            assert isinstance(value, self.value_type.py_type)
        return value

    async def set_param_value(self, value: Any):
        """Set the device value

        Raises:
            ValueError: If no :attr:`setter_method` is defined

        """
        pg = self.device_param_group
        if self.setter_method:
            m = getattr(pg, self.setter_method)
            await m(value)
        else:
            raise ValueError(f'No setter method for {self}')

class MultiParameterSpec(BaseParameterSpec):
    """Combines multiple :class:`ParameterSpec` definitions
    """

    _doc_field_names: ClassVar[List[str]] = [
        'full_name', 'prop_names', 'value_types',
        'setter_method', 'adjust_method',
    ]

    prop_names: List[str]# = field(default_factory=list)
    """The Property/attribute names within the
    :class:`jvconnected.device.ParameterGroup` containing the parameter values
    """

    value_types: List[Value]# = field(default_factory=list)
    """Specifications for the expected values of the attribute in
    :class:`~jvconnected.device.ParameterGroup`
    """

    value: List[Any] = ListProperty()
    """The current device value"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.prop_names = kwargs['prop_names']
        self.value_types = kwargs['value_types']
        self.value = [vt.py_type for vt in self.value_types]

    def _build_copy_kwargs(self) -> Dict:
        kw = super()._build_copy_kwargs()
        attrs = ['prop_name', 'value_type']
        kw.update({attr:getattr(self, attr) for attr in attrs})
        return kw

    def _bind_to_param_group(self, pg: 'jvconnected.device.ParameterGroup'):
        pg.bind(**{self.prop_name:self.on_device_prop_change})

    def on_device_prop_change(self, instance, value, **kwargs):
        if instance is not self.device_param_group:
            return
        prop = kwargs['property']
        assert prop.name == self.prop_name
        i = self.prop_names.index(prop.name)
        vtype = self.value_types[i]
        assert isinstance(value, vtype.py_type)
        self.value[i] = value
        self.emit('on_device_value_changed', self, self.value,
            prop_name=prop.name, value_type=vtype,
        )

    def get_param_value(self) -> List[Any]:
        """Get the current device value
        """
        pg = self.device_param_group
        value = [getattr(pg, key) for key in self.prop_names]
        for vtype, item in zip(self.value_types, value):
            assert isinstance(item, vtype)
        return value

    async def set_param_value(self, value: List[Any]):
        """Set the device value

        Raises:
            ValueError: If no :attr:`setter_method` is defined

        """
        pg = self.device_param_group
        if self.setter_method:
            m = getattr(pg, self.setter_method)
            await m(*value)
        else:
            raise ValueError(f'No setter method for {self}')


class ParameterGroupSpec(Dispatcher):
    """A group of :class:`ParameterSpec` definitions for a
    :class:`jvconnected.device.ParameterGroup` that can be attached to an
    existing :class:`~jvconnected.device.Device` instance.

    Arguments:
        device (jvconnected.device.Device): A :class:`~jvconnected.device.Device`
            instance to attach to

    Attributes:
        name (str): The name of the :class:`jvconnected.device.ParameterGroup`
            within its parent :attr:`device`
        device: Instance of :class:`jvconnected.device.Device`
        device_param_group: The :class:`jvconnected.device.ParameterGroup`
            associated with this instance
    """

    name: ClassVar[str]
    parameter_list: ClassVar[List[ParameterSpec]]
    parameters: Dict[str, ParameterSpec]

    def on_device_value_changed(
        self, group: 'ParameterGroupSpec', param: ParameterSpec, value: Any
    ):
        """Fired when the value of a parameter has changed on the device
        """

    _events_ = ['on_device_value_changed']

    def __init_subclass__(cls):
        super().__init_subclass__()
        doc_lines = cls.__doc__.splitlines()
        doc_lines.extend([
            '',
            ':Parameter Definitions:',
        ])
        for param in cls.parameter_list:
            param.group_name = cls.name
            param.full_name = f'{cls.name}.{param.name}'
            param_lines = [
                f'    {param.name}',
            ]
            param_lines.extend(param.build_docstring_lines(8))
            param_lines.append('')
            doc_lines.extend(param_lines)

        cls.parameters = {p.name:p for p in cls.parameter_list}
        cls.__doc__ = '\n'.join(doc_lines)

    def __init__(self, device: 'jvconnected.device.Device'):
        self.device = device
        self.device_param_group = device.parameter_groups[self.name]

        self.parameter_list = [p.copy() for p in self.parameter_list]
        self.parameters = {p.name:p for p in self.parameter_list}
        for p in self.parameter_list:
            p.param_group_spec = self
            p.bind(on_device_value_changed=self.on_param_spec_value_changed)

        multi_params = [p for p in self.parameters.values() if isinstance(p, MultiParameterSpec)]
        self.multi_params = {}
        for param in multi_params:
            for prop in param.prop_names:
                self.multi_params[prop] = param

    @classmethod
    def all_parameter_group_cls(cls) -> Iterator['ParameterGroupSpec']:
        """Iterate through all ParameterGroupSpec subclasses
        """
        def iter_subcls(_cls):
            if _cls is not ParameterGroupSpec:
                yield _cls
            for subcls in _cls.__subclasses__():
                yield from iter_subcls(subcls)
        # return [c for c in iter_subcls(ParameterGroupSpec)]
        yield from iter_subcls(ParameterGroupSpec)

    @classmethod
    def find_parameter_group_cls(cls, name: str) -> 'ParameterGroupSpec':
        """Search for a ParameterGroupSpec class by its :attr:`name`
        """
        for _cls in cls.all_parameter_group_cls():
            if _cls.name == name:
                return _cls
        raise KeyError(f'No subclass found for "{name}"')

    def get_param_value(self, name: str) -> Any:
        """Get the current device value for the given parameter

        Arguments:
            name (str): The :class:`ParameterSpec` name

        """
        param = self.parameters[name]
        return param.get_param_value()

    async def set_param_value(self, name: str, value: Any):
        """Set the device value for the given parameter

        Arguments:
            name (str): The :class:`ParameterSpec` name
            value: The value to set

        Raises:
            ValueError: If there is no setter method for the :class:`ParameterSpec`

        """
        param = self.parameters[name]
        await param.set_param_value(value)

    async def increment_param_value(self, name: str):
        """Increment the device value for the given parameter

        Arguments:
            name (str): The :class:`ParameterSpec` name

        """
        await self.adjust_param_value(name, True)

    async def decrement_param_value(self, name: str):
        """Decrement the device value for the given parameter

        Arguments:
            name (str): The :class:`ParameterSpec` name

        """
        await self.adjust_param_value(name, False)

    async def adjust_param_value(self, name: str, direction: bool):
        """Increment or decrement the device value for the given parameter

        Arguments:
            name (str): The :class:`ParameterSpec` name
            direction (bool): If True, increment, otherwise decrement

        Raises:
            ValueError: If there is no :attr:`~ParameterSpec.adjust_method` defined

        """
        param = self.parameters[name]
        await param.adjust_value(direction)

    def on_param_spec_value_changed(self, param: 'BaseParameterSpec', value: Any, **kwargs):
        self.emit('on_device_value_changed', self, param, value, **kwargs)

    def __getitem__(self, key):
        return self.parameters[key]

class ExposureParams(ParameterGroupSpec):
    """:class:`ParameterGroupSpec` definition for :class:`jvconnected.device.ExposureParams`
    """
    name = 'exposure'
    parameter_list = [
        ParameterSpec(
            name='mode',
            value_type=ChoiceValue(
                choices=['Auto', 'Manual', 'IrisPriority', 'ShutterPriority'],
            ),
        ),
        ParameterSpec(
            name='iris_mode',
            value_type=ChoiceValue(
                choices=['Manual', 'Auto', 'AutoAELock'],
            ),
        ),
        ParameterSpec(
            name='iris_pos',
            value_type=IntValue(),
            setter_method='set_iris_pos',
        ),
        ParameterSpec(
            name='gain_mode',
            value_type=ChoiceValue(
                choices=[
                    'ManualL', 'ManualM', 'ManualH', 'AGC',
                    'AlcAELock', 'LoLux', 'Variable',
                ],
            ),
        ),
        ParameterSpec(
            name='gain_pos',
            value_type=IntValue(value_min=-6, value_max=24, value_default=0),
            adjust_method='adjust_gain',
        ),
        ParameterSpec(
            name='shutter_mode',
            value_type=ChoiceValue(
                choices=['Off', 'Manual', 'Step', 'Variable', 'Eei'],
            ),
        ),
        ParameterSpec(
            name='master_black_pos',
            value_type=IntValue(value_min=-50, value_max=50, value_default=0),
            adjust_method='adjust_master_black',
        ),
    ]

class PaintParams(ParameterGroupSpec):
    """:class:`ParameterGroupSpec` definition for :class:`jvconnected.device.PaintParams`
    """
    name = 'paint'
    parameter_list = [
        ParameterSpec(
            name='white_balance_mode',
            value_type=ChoiceValue(
                choices=[
                    'Preset', 'A', 'B', 'Faw', 'FawAELock',
                    'Faw', 'Awb', 'OnePush', '3200K', '5600K', 'Manual',
                ],
            ),
        ),
        ParameterSpec(
            name='red_normalized',
            value_type=IntValue(value_min=-32, value_max=32, value_default=0),
            setter_method='set_red_pos',
        ),
        ParameterSpec(
            name='blue_normalized',
            value_type=IntValue(value_min=-32, value_max=32, value_default=0),
            setter_method='set_blue_pos',
        ),
        # MultiParameterSpec(
        #     name='wb_pos',
        #     prop_names = ['red_normalized', 'blue_normalized'],
        #     value_types=[
        #         IntValue(value_min=-32, value_max=32, value_default=0),
        #         IntValue(value_min=-32, value_max=32, value_default=0),
        #     ],
        #     setter_method='set_wb_pos',
        # ),
        ParameterSpec(
            name='detail_pos',
            value_type=IntValue(value_min=-10, value_max=10, value_default=0),
            adjust_method='adjust_detail',
        ),
    ]

class TallyParams(ParameterGroupSpec):
    """:class:`ParameterGroupSpec` definition for :class:`jvconnected.device.TallyParams`
    """
    name = 'tally'
    parameter_list = [
        ParameterSpec(name='program', value_type=BoolValue(), setter_method='set_program'),
        ParameterSpec(name='preview', value_type=BoolValue(), setter_method='set_preview'),
        ParameterSpec(
            name='tally_status',
            value_type=ChoiceValue(
                choices=['Off', 'Program', 'Preview'],
            ),
        ),
    ]
