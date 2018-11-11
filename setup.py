from setuptools import setup, find_packages

setup(
    name='Pyjector',
    version='0.2.3',
    description='Control your projector over a serial port',
    author='John Brodie',
    author_email='john@brodie.me',
    url='http://www.github.com/JohnBrodie/pyjector',
    packages=find_packages(),
    install_requires=[
        'pyserial',
    ],
    package_data={
        'pyjector.cli': ['projector_configs/*.json'],
    },
    entry_points='''
        [console_scripts]
        pyjector_controller=pyjector.cli.pyjector_controller:main
    ''',
)
