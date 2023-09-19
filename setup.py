from setuptools import setup, find_packages

setup(
    name='blindb',
    version='1.0',
    packages=find_packages(),
    install_requires=[
        'rich'
    ],
    entry_points={
        "console_scripts": [
            "blindb = blindb.app:main",
        ]
    }
)