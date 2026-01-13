from setuptools import setup, find_packages

setup(name='smgdatatools',
      version='0.3',
      description='Climate data utilities used by Santander Meteorology Group',
      author='zequihg50',
      author_email='ezequiel.cimadevilla@unican.es',
      url='https://github.com/SantanderMetGroup/smgdatatools',
      packages=find_packages(),
      package_dir={'smgdatatools': 'smgdatatools'},
      package_data={
          '': ['templates/*'],
      },
      install_requires=[
          'netCDF4',
          'h5py',
          'jinja2',
          'cftime',
          'pkgconfig',
          'numpy',
          'zarr',
          'sqlalchemy',
          'gcsfs',
          'requests',
          'natsort',
      ],
      scripts=[
          'smgdatatools/esgfsearch.py',
          'smgdatatools/etl.py',
          'smgdatatools/ncrcat.py',
          'smgdatatools/catalog.py'],
)
