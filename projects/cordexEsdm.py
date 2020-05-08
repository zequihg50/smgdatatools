# https://gitlab.com/scds/tds-content/-/issues/4

import os
import pandas as pd
from ncml.reader import NetcdfMetadataReader
from ncml.adapter import Adapter as NcmlAdapter
from catalog.adapter import BaseAdapter as CatalogAdapter

class InterimCordexEsdmCatalogAdapter(CatalogAdapter):
	def __init__(self):
		self.template = 'cordexEsdm/cordexEsdm.xml.j2'
		self.rtemplate = 'cordexEsdm/root.xml.j2'

	def group(self, file):
		basename = os.path.basename(file)
		name, ext = os.path.splitext(basename)
		facets = name.split('_')

		if ext == ".ncml":
			grouper = [facets[i] for i in [1,2]]
		else:
			grouper = [facets[i] for i in [2,3]]

		return '/'.join(grouper)

class EcearthCordexEsdmCatalogAdapter(CatalogAdapter):
	def __init__(self):
		self.template = 'cordexEsdm/cordexEsdm.xml.j2'
		self.rtemplate = 'cordexEsdm/root.xml.j2'

	def group(self, file):
		basename = os.path.basename(file)
		name, ext = os.path.splitext(basename)
		facets = name.split('_')

		if ext == ".ncml":
			grouper = [facets[i] for i in [1,2,4,3]]
		else:
			grouper = [facets[i] for i in [2,3,5,4]]

		return '/'.join(grouper)

class CordexEsdmNcmlAdapter(NcmlAdapter):
	def filter_fx(self, df):
		return df

	def get_fxs(self, df, facets, values):
		return pd.DataFrame(columns=df.columns)

	def get_time_values(self, df):
		return df

	def preprocess(self, df):
		return df

	def test(self, df, ncml):
		pass

class EcearthCordexEsdmNcmlAdapter(CordexEsdmNcmlAdapter):
	def __init__(self):
		self.reader = EcearthCordexEsdmMetadataReader()
		self.template = 'cordexEsdm/cordexEsdm.ncml.j2'
		self.groupby = ['project', 'model', 'run', 'experiment', 'domain']
		self.name = '{project}_{model}_{run}_{experiment}_{domain}.ncml'

class InterimCordexEsdmNcmlAdapter(CordexEsdmNcmlAdapter):
	def __init__(self):
		self.reader = InterimCordexEsdmMetadataReader()
		self.template = 'cordexEsdm/cordexEsdm.ncml.j2'
		self.groupby = ['institution', 'model' ,'domain']
		self.name = '{institution}_{model}_{domain}.ncml'

# nc example: hus@1000_CMIP5_EC-EARTH_r12i1p1_rcp85_EUR.nc4
class EcearthCordexEsdmMetadataReader(NetcdfMetadataReader):
	def read(self, file):
		attrs = super().read(file)
		basename = os.path.splitext(os.path.basename(file))[0]
		facets = basename.split('_')

		attrs['GLOBALS']['variable'] = facets[0].replace('@', '')
		attrs['GLOBALS']['project'] = facets[1]
		attrs['GLOBALS']['model'] = facets[2]
		attrs['GLOBALS']['run'] = facets[3]
		attrs['GLOBALS']['experiment'] = facets[4]
		attrs['GLOBALS']['domain'] = facets[5]

		return attrs

# nc example: ta@1000_ECMWF_ERA-Interim-ESD_EUR.nc4
class InterimCordexEsdmMetadataReader(NetcdfMetadataReader):
	def read(self, file):
		attrs = super().read(file)
		basename = os.path.splitext(os.path.basename(file))[0]
		facets = basename.split('_')

		attrs['GLOBALS']['variable'] = facets[0].replace('@', '')
		attrs['GLOBALS']['institution'] = facets[1]
		attrs['GLOBALS']['model'] = facets[2]
		attrs['GLOBALS']['domain'] = facets[3]

		return attrs