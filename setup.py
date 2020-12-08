from setuptools import setup

setup(
    entry_points={
        'console_scripts':[
            'jvconnected-ui = jvconnected.ui.main:run',
        ],
    },
)
