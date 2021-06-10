from setuptools import setup, find_packages

with open('README.md') as f:
    readme = f.read()

setup(
    version = '0.0.9',
    name = 'rov',
    author = 'Romain Fontugne',
    author_email = 'romain.fontugne@gmail.com',
    url = 'https://github.com/InternetHealthReport/route-origin-validator/',
    description="Offline Internet route origin validation using RPKI, IRR, and RIRs delegated databases",
    long_description=readme,
    long_description_content_type="text/markdown",
    keywords = ['RPKI', 'IRR', 'delegated', 'Internet', 'routing', 'route origin validation'],
    packages = find_packages(),
    install_requires=[
        'appdirs',
        'py-radix',
        'portion',
    ],
    entry_points={'console_scripts':
            ['rov = rov.__main__:main']},
)
