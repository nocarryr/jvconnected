from loguru import logger

from typing import List, Tuple, Dict, Any, ClassVar, Iterator, Optional
from dataclasses import dataclass, field

from pydispatch import Dispatcher, Property, ListProperty

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
    """

    :Events:
        .. event:: on_device_value_changed(param: ParameterSpec, value)

            Fired when the parameter value has changed on the device

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

    :Properties:

        value: The current device value

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

    value = Property()

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


class PropertyGuard:
    class GuardContext:
        def __init__(self, parent: 'PropertyGuard', prop: str):
            self.parent = parent
            self.prop = prop
        def __enter__(self):
            self.parent._acquire(self.prop)
            return self
        def __exit__(self, *args):
            self.parent._release(self.prop)

    def __init__(self):
        self.__props = {}
    def is_acquired(self, prop: str) -> bool:
        n = self.__props.get(prop, 0)
        return n > 0
    def _acquire(self, prop: str):
        if prop not in self.__props:
            self.__props[prop] = 1
        else:
            self.__props[prop] += 1
    def _release(self, prop: str):
        self.__props[prop] -= 1
    def __call__(self, prop: str):
        return self.GuardContext(self, prop)

class ParameterRangeMap(BaseParameterSpec):
    """Remaps the value range of another :class:`ParameterSpec`

    This can be useful to scale the range of a parameter such as iris position
    to within a usable range. Typically one doesn't need to close the iris
    down past a certain value. Instead, a wider range of motion on a physical
    control (say, a fader) is desired for smoother operation.

    The affected parameter is specified by its :attr:`~BaseParameterSpec.name`
    and therefore the :attr:`~BaseParameterSpec.group_name` must match.

    This is only possible with parameters using :class:`IntValue` as their
    :attr:`~ParameterSpec.value_type` since it uses the :attr:`~IntValue.value_min`
    and :attr:`~IntValue.value_max` for scaling.

    The :attr:`value_min_adj` and :attr:`value_max_adj` properties are then used
    to set the desired range and the :attr:`value` property reflects the scaled
    parameter value.


    :Properties:

        value (int): The current value of the parameter, scaled to be within
            the effective range
        value_min_adj (int): The remapped minimum value
        value_max_adj (int): The remapped maximum value

    """

    parameter_name: str
    """The :attr:`~BaseParameterSpec.name` of the affected parameter within
    this instance's group
    """

    value = Property()
    value_min_adj = Property(0)
    value_max_adj = Property(0)

    _doc_field_names: ClassVar[List[str]] = [
        'full_name', 'parameter_name', 'value_min_adj', 'value_max_adj',
    ]

    def __init__(self, **kwargs):
        self._parameter = None
        self.__reset_guard = PropertyGuard()
        super().__init__(**kwargs)
        self.parameter_name = kwargs.get('parameter_name')

    @property
    def parameter(self) -> Optional[ParameterSpec]:
        p = self._parameter
        if p is None:
            p = self._parameter = self._find_parameter_obj()
            if p is not None:
                self._bind_to_parameter(p)
        return p
    @parameter.setter
    def parameter(self, p: ParameterSpec):
        assert isinstance(p, ParameterSpec)
        if p is self._parameter:
            return
        self._validate_parameter_obj(p)
        self._parameter = p
        self._bind_to_parameter(p)

    def get_parameter_obj(self):
        if self._parameter is not None:
            return
        p = self._find_parameter_obj()
        if p is not None:
            self.parameter = p

    def _find_parameter_obj(self) -> Optional[ParameterSpec]:
        pgs = self.param_group_spec
        if pgs is None:
            return None
        p = pgs.parameters.get(self.parameter_name)
        if p is not None:
            self._validate_parameter_obj(p)
        return p

    def _validate_parameter_obj(self, p: ParameterSpec):
        if p.group_name != self.group_name:
            raise ValueError(f'Group name mismatch for {self.full_name} and parameter {p.full_name}')
        if p.name != self.parameter_name:
            raise ValueError(f'Parameter name mismatch for {self.full_name} and parameter {p.full_name}')
        if not isinstance(p.value_type, IntValue):
            raise ValueError(f'{self.__class__.__name__} "{self.full_name}" parameter type mismatch ({p.full_name} = {p.value_type!r})')

    @property
    def value_type(self):
        return self.parameter.value_type

    @property
    def parameter_range(self) -> Optional[Tuple[int, int]]:
        p = self.parameter
        if p is None:
            return None, None
        return p.value_type.value_min, p.value_type.value_max

    @property
    def effective_range(self) -> Tuple[int, int]:
        # pmin, pmax = self.parameter_range
        # return pmin + self.value_min_adj, pmax - self.value_max_adj
        return self.value_min_adj, self.value_max_adj

    def _build_copy_kwargs(self) -> Dict:
        kw = super()._build_copy_kwargs()
        attrs = ['parameter_name', 'value_min_adj', 'value_max_adj']
        kw.update({attr:getattr(self, attr) for attr in attrs})
        return kw

    @logger.catch
    def _bind_to_parameter(self, p: ParameterSpec):
        pmin, pmax = self.parameter_range
        self.value_min_adj, self.value_max_adj = pmin, pmax
        # self._validate_min_adj()
        # self._validate_max_adj()
        self._on_parameter_value(p, p.get_param_value())
        p.bind(value=self._on_parameter_value)
        self.bind(
            value_min_adj=self._on_value_min_adj,
            value_max_adj=self._on_value_max_adj,
        )

    def _scale_to_param(self, value: int) -> int:
        min_adj, max_adj = self.effective_range
        # if min_adj == max_adj:
        #     return min_adj
        range_adj = max_adj - min_adj

        pmin, pmax = self.parameter_range
        prange = pmax - pmin

        result = (value - pmin) / prange * range_adj + min_adj
        result = int(round(result))
        assert min_adj <= result <= max_adj
        return result

    def _scale_from_param(self, value: int) -> int:
        pmin, pmax = self.parameter_range
        prange = pmax - pmin

        min_adj, max_adj = self.effective_range
        # if min_adj == max_adj:
        #     return min_adj
        range_adj = max_adj - min_adj

        result = (value - min_adj) / range_adj * prange + pmin
        result = int(round(result))
        # assert pmin <= result <= pmax
        if result > pmax:
            result = pmax
        elif result < pmin:
            result = pmin
        return result

    def get_param_value(self) -> Optional[int]:
        """Get the current device value scaled within the current range
        """
        p = self.parameter
        if p is None:
            return None
        value = p.get_param_value()
        if value is not None:
            value = self._scale_from_param(value)
        return value

    async def set_param_value(self, value: int):
        p = self.parameter
        value = self._scale_to_param(value)
        await p.set_param_value(value)

    @logger.catch
    def _on_parameter_value(self, instance, value, **kwargs):
        if instance is not self.parameter:
            return
        if value is None:
            return
        value = self._scale_from_param(value)
        assert value == self.get_param_value()
        self.value = value
        self.emit('on_device_value_changed', self, self.value,
            prop_name=self.name, value_type=instance.value_type,
        )

    def __reset_range(self, prop_name, value):
        # assert prop_name not in self.__resetting_ranges
        assert not self.__reset_guard.is_acquired(prop_name)
        # self.__resetting_ranges.add(prop_name)
        with self.__reset_guard(prop_name):
            setattr(self, prop_name, value)
        # self.__resetting_ranges.discard(prop_name)

    # def _validate_min_adj(self):
    #     min_adj, max_adj = self.value_min_adj, self.value_max_adj
    #     if min_adj == 0:
    #         return
    #     elif min_adj < 0:
    #         self.__reset_range('value_min_adj', 0)
    #         return
    #
    #     pmin, pmax = self.parameter_range
    #     if pmin is None:
    #         return
    #     eff_min, eff_max = pmin + min_adj, pmax - max_adj
    #     if eff_min > pmax:
    #         new_min = min_adj - (eff_min - pmax)        # reset min to top of param range
    #         assert pmin <= pmin+new_min <= pmax
    #         self.__reset_range('value_min_adj', new_min)
    #     elif eff_min > eff_max:
    #         new_max = max_adj + (eff_min - eff_max)
    #         if new_max <= pmax:                         # increase upper range
    #             assert pmin <= pmax-new_max <= pmax
    #             self.value_max_adj = new_max
    #         else:
    #             new_min = min_adj - (eff_min - eff_max) # reset min to top of adjusted range
    #             assert pmin <= pmin+new_min <= pmax
    #             self.__reset_range('value_min_adj', new_min)
    #
    # def _validate_max_adj(self):
    #     min_adj, max_adj = self.value_min_adj, self.value_max_adj
    #     if max_adj == 0:
    #         return
    #     elif max_adj < 0:
    #         self.__reset_range('value_max_adj', 0)
    #         return
    #
    #     pmin, pmax = self.parameter_range
    #     if pmin is None:
    #         return
    #     eff_min, eff_max = pmin + min_adj, pmax - max_adj
    #     if eff_max < pmin:
    #         new_max = pmax + (pmax - pmin)              # reset max to bottom of param range
    #         assert pmin <= pmax-new_max <= pmax
    #         self.__reset_range('value_max_adj', new_max)
    #     elif eff_max < eff_min:
    #         new_min = min_adj - (eff_min - eff_max)
    #         if new_min >= pmin:
    #             assert pmin <= pmin+new_min <= eff_max
    #             self.value_min_adj = new_min            # decrease lower range
    #         else:
    #             new_max = max_adj + (eff_min - eff_max) # reset max to top of adjusted range
    #             assert pmin <= pmax-new_max <= pmax
    #             self.__reset_range('value_max_adj', new_max)

    @logger.catch
    def _on_value_min_adj(self, instance, value, **kwargs):
        if self.__reset_guard.is_acquired('value_min_adj'):
            logger.debug(f'value_min_adj lock acquired: {value=}, {self.value_min_adj=}')
            return
        # if 'value_min_adj' in self.__resetting_ranges:
        #     return
        # self._validate_min_adj()
        logger.debug(f'value_min_adj: orig={value}, validated={self.value_min_adj}, {self.effective_range=}')
        self.value = self.get_param_value()

    @logger.catch
    def _on_value_max_adj(self, instance, value, **kwargs):
        if self.__reset_guard.is_acquired('value_max_adj'):
            return
        # if 'value_max_adj' in self.__resetting_ranges:
        #     return
        # self._validate_max_adj()
        logger.debug(f'value_max_adj: orig={value}, validated={self.value_max_adj}, {self.effective_range=}')
        self.value = self.get_param_value()


class MultiParameterSpec(BaseParameterSpec):
    """Combines multiple :class:`ParameterSpec` definitions

    :Properties:

        value(list): The current device value

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

    value = ListProperty()

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

    :Events:
        .. event:: on_device_value_changed(group: ParameterGroupSpec, param: ParameterSpec, value)

            Fired when the value of a parameter has changed on the device

    """

    name: ClassVar[str]
    parameter_list: ClassVar[List[ParameterSpec]]
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

        ranged_params = [p for p in self.parameters.values() if isinstance(p, ParameterRangeMap)]
        for param in ranged_params:
            param.get_parameter_obj()

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
        ParameterRangeMap(
            name='iris_scaled',
            parameter_name='iris_pos',
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
