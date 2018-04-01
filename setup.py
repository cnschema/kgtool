from setuptools import setup


def readme():
    with open('README.rst') as f:
        return f.read()


setup(name='kgtool',
      version='0.0.2',
      description='simple knowledge graph tools with minimal dependency',
      long_description=readme(),
      classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 2.7',
        'Topic :: Text Processing',
      ],
      url='http://github.com/cnschema/kgtool',
      author='Li Ding',
      author_email='lidingpku@gmail.com',
      license='Apache 2.0',
      packages=['kgtool'],
      install_requires=[
        'xlrd', 'xlwt'
      ],
      test_suite='nose.collector',
      tests_require=['nose'],
      zip_safe=False)
