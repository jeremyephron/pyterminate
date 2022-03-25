import setuptools

setuptools.setup(
    name='pyterminate',
    version='0.0.1',
    url='https://github.com/jeremyephron/pyterminate',
    author='Jeremy Ephron',
    author_email='jeremye@cs.stanford.edu',
    description='Exit programs gracefully',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    packages=setuptools.find_packages(),
    install_requires=[],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.9',
        'License :: OSI Approved :: MIT License',
        'Operating System :: MacOS',
        'Operating System :: Unix',
    ],
)
