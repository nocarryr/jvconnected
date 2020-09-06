from typing import List, Dict, Any, ClassVar, Iterator
from dataclasses import dataclass, field

from pydispatch import Dispatcher

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


@dataclass
class BaseParameterSpec:
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

@dataclass
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

    def __post_init__(self):
        if not len(self.prop_name):
            self.prop_name = self.name

    def get_param_value(self, param_group_spec: 'ParameterGroupSpec') -> Any:
        pg = param_group_spec.device_param_group
        value = getattr(pg, self.prop_name)
        assert isinstance(value, self.value_type.py_type)
        return value

    async def set_param_value(self, param_group_spec: 'ParameterGroupSpec', value: Any):
        pg = param_group_spec.device_param_group
        if self.setter_method:
            m = getattr(pg, self.setter_method)
            await m(value)
        else:
            raise ValueError(f'No setter method for {self}')

@dataclass
class MultiParameterSpec(BaseParameterSpec):
    """Combines multiple :class:`ParameterSpec` definitions
    """

    _doc_field_names: ClassVar[List[str]] = [
        'full_name', 'prop_names', 'value_types',
        'setter_method', 'adjust_method',
    ]

    prop_names: List[str] = field(default_factory=list)
    """The Property/attribute names within the
    :class:`jvconnected.device.ParameterGroup` containing the parameter values
    """

    value_types: List[Value] = field(default_factory=list)
    """Specifications for the expected values of the attribute in
    :class:`~jvconnected.device.ParameterGroup`
    """

    def get_param_value(self, param_group_spec: 'ParameterGroupSpec') -> List[Any]:
        pg = param_group_spec.device_param_group
        value = [getattr(pg, key) for key in self.prop_names]
        for vtype, item in zip(self.value_types, value):
            assert isinstance(item, vtype)
        return value

    async def set_param_value(self, param_group_spec: 'ParameterGroupSpec', value: List[Any]):
        pg = param_group_spec.device_param_group
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

    :Events:
        .. event:: on_device_value_changed(group: ParameterGroupSpec, param: ParameterSpec, value)

            Fired when the value of a parameter has changed on the device

    """

    # class attributes
    name: str
    parameter_list: List[ParameterSpec]
    parameters: Dict[str, ParameterSpec]

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
        single_params = [p.prop_name for p in self.parameters.values() if not isinstance(p, MultiParameterSpec)]
        multi_params = [p for p in self.parameters.values() if isinstance(p, MultiParameterSpec)]
        self.multi_params = {}
        for param in multi_params:
            for prop in param.prop_names:
                self.multi_params[prop] = param
        all_props = set(single_params) | set(self.multi_params.keys())
        self.device_param_group.bind(**{k:self._on_device_param_group_prop for k in all_props})
        # self.device_param_group.bind(
        #     **{k:self._on_device_multi_param_group_prop for k in self.multi_params.keys()},
        # )


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
        return param.get_param_value(self)

    async def set_param_value(self, name: str, value: Any):
        """Set the device value for the given parameter

        Arguments:
            name (str): The :class:`ParameterSpec` name
            value: The value to set

        Raises:
            ValueError: If there is no setter method for the :class:`ParameterSpec`

        """
        param = self.parameters[name]
        await param.set_param_value(self, value)

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
        pg = self.device_param_group
        if not param.adjust_method:
            raise ValueError(f'No adjust method for {param}')
        m = getattr(pg, param.adjust_method)
        await m(direction)

    def _on_device_param_group_prop(self, instance, value, **kwargs):
        if instance is not self.device_param_group:
            return
        prop = kwargs['property']
        param = self.parameters.get(prop.name)
        if param is not None:
            assert isinstance(value, param.value_type.py_type)
            self.emit('on_device_value_changed', self, param, value)
        if prop.name in self.multi_params:
            self._on_device_multi_param_group_prop(instance, value, **kwargs)

    def _on_device_multi_param_group_prop(self, instance, value, **kwargs):
        if instance is not self.device_param_group:
            return
        prop = kwargs['property']
        param = self.multi_params[prop.name]
        i = param.prop_names.index(prop.name)
        vtype = param.value_types[i]
        assert isinstance(value, vtype.py_type)
        self.emit('on_device_value_changed', self, param, value,
            prop_name=prop.name, value_type=vtype,
        )

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
