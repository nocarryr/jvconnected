import asyncio

from jvconnected.config import Config

def test_indexing(fake_devices, config_tmpdir):
    conf_file = config_tmpdir / 'config.json'
    config = Config(conf_file)

    conf_devices = []
    for i, fake_device in enumerate(fake_devices):
        device = config.add_discovered_device(fake_device.zc_service_info)
        device.device_index = -1
        assert device.device_index == i
        conf_devices.append(device)

    # expected_indices = [0, 1, 2, 3]

    ix_change_from = 2
    ix_change_to = 0
    expected_indices = [1, 2, 0, 3]

    conf_devices[ix_change_from].device_index = ix_change_to

    for i, device in enumerate(conf_devices):
        assert device.device_index == expected_indices[i]

    for i, device in enumerate(conf_devices):
        device.device_index = None
        assert device.id not in config.indexed_devices
