# jvconnected

Python library to communicate with JVC [Connected Cam] devices

**Currently a work in progress**

## Description

Use the [JVC Camcorder Web API](http://pro.jvc.com/pro/attributes/ip/manual/JvcCamcorderApiReferenceV114_public.pdf) to communicate with compatible
cameras. Devices are automatically discovered on the network using [zeroconf](https://en.wikipedia.org/wiki/Zero-configuration_networking).  Controllable parameters
can be found in the documentation linked below.

## Links

|               |                                              |
| -------------:|:-------------------------------------------- |
| Project Home  | https://github.com/nocarryr/jvconnected      |
| Documentation | https://jvconnected.readthedocs.io           |


## Installation

Since this project is not yet packaged for distribution, it is not available
for installation with [pip](https://pip.pypa.io/) and must be installed from
source code.

### Download Source

The source code can be downloaded either as a snapshot archive:
https://github.com/nocarryr/jvconnected/archive/master.zip
or by using git:

```bash
git clone https://github.com/nocarryr/jvconnected.git
```

### Setup

Using a [virtual environment](https://docs.python.org/3.8/library/venv.html) is
recommended:

```bash
cd jvconnected
python -m venv venv
source venv/bin/activate
```

Then install in [development mode](https://pip.pypa.io/en/stable/reference/pip_install/#editable-installs) (including all "extra" dependencies)

```bash
pip install -e .[ui,midi]
```

If using the UI, the Qt resource files need to be created:

```bash
python setup.py build_qrc
```

## Running the UI

If the virtual environment is active, the UI can be launched with

```bash
jvconnected-ui
```

or directly from the entry point script within the virtual environment's `bin` directory

```bash
<project-path>/venv/bin/jvconnected-ui
```


[Connected Cam]: http://pro.jvc.com/pro/attributes/ip/clips/connectedcam_workflow.jsp
