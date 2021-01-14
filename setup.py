from setuptools import setup

setup(
    entry_points={
        'console_scripts':[
            'jvconnected-ui = jvconnected.ui.main:run',
        ],
        'distutils.commands':[
            'build_qrc = jvconnected.ui.tools.build_qrc:BuildQRC',
        ],
    },
)
