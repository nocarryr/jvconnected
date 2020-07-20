from pathlib import Path
import pytest

import fakedevice

def build_fake_devices(num_devices: int):
    all_ports = set()
    all_serial_nums = set()
    devices = []
    for i in range(num_devices):
        device = fakedevice.FakeDevice()
        while device.hostport in all_ports:
            device.hostport += 1
        while device.serial_number in all_serial_nums:
            device.serial_number = str(int(device.serial_number) + 1)
        all_ports.add(device.hostport)
        all_serial_nums.add(device.serial_number)
        devices.append(device)
    return devices

@pytest.fixture
def fake_devices():
    return build_fake_devices(4)

@pytest.fixture
def config_tmpdir(tmpdir):
    base = Path(tmpdir)
    return base / 'config'
