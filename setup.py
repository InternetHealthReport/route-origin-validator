from setuptools import setup, find_packages

with open('README.md') as f:
    readme = f.read()

setup(
    version = '0.0.1',
    name = 'rov',
    description="Offline Internet route origin validation using RPKI, IRR, and RIRs delegated databases",
    long_description=readme,
    long_description_content_type="text/markdown",
    packages = find_packages(),
    install_requires=[
        'appdirs',
        'py-radix',
        'portion',
    ],
    entry_points={'console_scripts':
            ['rov = ihr.rov:main']},
)
