# SantanderMetGroup/datatools

smgdatatools stands for data tools from [SantanderMetGroup](https://github.com/SantanderMetGroup).

## etl.py

Generate virtual datasets for climate data. Supports [Kerchunk](https://github.com/fsspec/kerchunk/), [HDF5 VDS](https://docs.h5py.org/en/stable/vds.html) and [NcML](https://www.unidata.ucar.edu/software/netcdf-java/v4.6/ncml/Tutorial.html).

### Kerchunk

#### EOBS

See a description of the dataset [here](https://surfobs.climate.copernicus.eu/dataaccess/access_eobs.php).

```bash
echo 'https://knmi-ecad-assets-prd.s3.amazonaws.com/ensembles/data/Grid_0.1deg_reg_ensemble/tg_ens_mean_0.1deg_reg_v27.0e.nc
https://knmi-ecad-assets-prd.s3.amazonaws.com/ensembles/data/Grid_0.1deg_reg_ensemble/tn_ens_mean_0.1deg_reg_v27.0e.nc
https://knmi-ecad-assets-prd.s3.amazonaws.com/ensembles/data/Grid_0.1deg_reg_ensemble/tx_ens_mean_0.1deg_reg_v27.0e.nc
https://knmi-ecad-assets-prd.s3.amazonaws.com/ensembles/data/Grid_0.1deg_reg_ensemble/rr_ens_mean_0.1deg_reg_v27.0e.nc
https://knmi-ecad-assets-prd.s3.amazonaws.com/ensembles/data/Grid_0.1deg_reg_ensemble/pp_ens_mean_0.1deg_reg_v27.0e.nc
https://knmi-ecad-assets-prd.s3.amazonaws.com/ensembles/data/Grid_0.1deg_reg_ensemble/hu_ens_mean_0.1deg_reg_v27.0e.nc
https://knmi-ecad-assets-prd.s3.amazonaws.com/ensembles/data/Grid_0.1deg_reg_ensemble/fg_ens_mean_0.1deg_reg_v27.0e.nc
https://knmi-ecad-assets-prd.s3.amazonaws.com/ensembles/data/Grid_0.1deg_reg_ensemble/qq_ens_mean_0.1deg_reg_v27.0e.nc' | etl.py --db test.sqlite --collector hdf5chunk --hdf5-driver ros3 --etl jinja -t kerchunk.json.j2 --dest test.json
```

#### ERA5 from Amazon S3

See a description of the dataset [here](https://registry.opendata.aws/ecmwf-era5/).

```bash
echo 'https://s3.amazonaws.com/era5-pds/2020/01/data/air_pressure_at_mean_sea_level.nc
https://s3.amazonaws.com/era5-pds/2020/02/data/air_pressure_at_mean_sea_level.nc
https://s3.amazonaws.com/era5-pds/2020/01/data/sea_surface_temperature.nc
https://s3.amazonaws.com/era5-pds/2020/02/data/sea_surface_temperature.nc' | \
etl.py --db test.sqlite --collector hdf5chunk --hdf5-driver ros3 --aggregations air_pressure_at_mean_sea_level sea_surface_temperature --etl jinja -t era5-s3.json.j2 --dest test.json
```

**You need to remove the last comma from the `test.json` file!**

```python
import xarray

ds = xarray.open_dataset("reference://", engine="zarr", backend_kwargs={
                    "consolidated": False,
                    "storage_options": {"fo": 'test.json', "remote_protocol": "s3","remote_options": {"anon": True}}
                    })
print(ds)
```

#### CMIP6 from Pangeo and Google Cloud

See a description of the dataset [here](https://console.cloud.google.com/marketplace/details/noaa-public/cmip6).

```bash
echo 'gs://cmip6/CMIP6/CMIP/NCAR/CESM2-FV2/historical/r2i1p1f1/Amon/tas/gn/v20200226
gs://cmip6/CMIP6/CMIP/NCAR/CESM2-FV2/historical/r1i1p1f1/Amon/tas/gn/v20191120
gs://cmip6/CMIP6/CMIP/NCAR/CESM2-FV2/historical/r2i1p1f1/Amon/pr/gn/v20200226
gs://cmip6/CMIP6/CMIP/NCAR/CESM2-FV2/historical/r1i1p1f1/Amon/pr/gn/v20191120' | \
etl.py --db test.sqlite --collector zarr --aggregations tas pr --etl jinja -t gcs-cmip6.json.j2 --dest test.json
```

**You need to remove the last comma from the `test.json` file!**

```python
import xarray

ds = xarray.open_dataset("reference://", engine="zarr", backend_kwargs={
                    "consolidated": False,
                    "storage_options": {"fo": 'test.json', "remote_protocol": "gs","remote_options": {"anon": True}}
                    })
print(ds)
```

Be careful with the following:

- Number of chunks does not match between ensemble members for the same variable. Check this against the SQL database (eg. `select count(*) from variable inner join chunk on variable.id = chunk.variable_id where variable.name = VARIABLE_NAME group by variable.id`).

Try it with lots of ensembles:

```bash
echo 'gs://cmip6/CMIP6/CMIP/EC-Earth-Consortium/EC-Earth3/historical/r104i1p1f1/day/tas/gr/v20200412
gs://cmip6/CMIP6/CMIP/EC-Earth-Consortium/EC-Earth3/historical/r105i1p1f1/day/tas/gr/v20200412
gs://cmip6/CMIP6/CMIP/EC-Earth-Consortium/EC-Earth3/historical/r106i1p1f1/day/tas/gr/v20200412
gs://cmip6/CMIP6/CMIP/EC-Earth-Consortium/EC-Earth3/historical/r108i1p1f1/day/tas/gr/v20200412
gs://cmip6/CMIP6/CMIP/EC-Earth-Consortium/EC-Earth3/historical/r110i1p1f1/day/tas/gr/v20200412
gs://cmip6/CMIP6/CMIP/EC-Earth-Consortium/EC-Earth3/historical/r111i1p1f1/day/tas/gr/v20200412
gs://cmip6/CMIP6/CMIP/EC-Earth-Consortium/EC-Earth3/historical/r112i1p1f1/day/tas/gr/v20200412
gs://cmip6/CMIP6/CMIP/EC-Earth-Consortium/EC-Earth3/historical/r113i1p1f1/day/tas/gr/v20200412
gs://cmip6/CMIP6/CMIP/EC-Earth-Consortium/EC-Earth3/historical/r114i1p1f1/day/tas/gr/v20200412
gs://cmip6/CMIP6/CMIP/EC-Earth-Consortium/EC-Earth3/historical/r115i1p1f1/day/tas/gr/v20200412
gs://cmip6/CMIP6/CMIP/EC-Earth-Consortium/EC-Earth3/historical/r117i1p1f1/day/tas/gr/v20200412
gs://cmip6/CMIP6/CMIP/EC-Earth-Consortium/EC-Earth3/historical/r118i1p1f1/day/tas/gr/v20200412
gs://cmip6/CMIP6/CMIP/EC-Earth-Consortium/EC-Earth3/historical/r119i1p1f1/day/tas/gr/v20200412
gs://cmip6/CMIP6/CMIP/EC-Earth-Consortium/EC-Earth3/historical/r120i1p1f1/day/tas/gr/v20200412
gs://cmip6/CMIP6/CMIP/EC-Earth-Consortium/EC-Earth3/historical/r123i1p1f1/day/tas/gr/v20200412
gs://cmip6/CMIP6/CMIP/EC-Earth-Consortium/EC-Earth3/historical/r124i1p1f1/day/tas/gr/v20200412
gs://cmip6/CMIP6/CMIP/EC-Earth-Consortium/EC-Earth3/historical/r125i1p1f1/day/tas/gr/v20200412
gs://cmip6/CMIP6/CMIP/EC-Earth-Consortium/EC-Earth3/historical/r126i1p1f1/day/tas/gr/v20200412
gs://cmip6/CMIP6/CMIP/EC-Earth-Consortium/EC-Earth3/historical/r127i1p1f1/day/tas/gr/v20200412
gs://cmip6/CMIP6/CMIP/EC-Earth-Consortium/EC-Earth3/historical/r129i1p1f1/day/tas/gr/v20200412
gs://cmip6/CMIP6/CMIP/EC-Earth-Consortium/EC-Earth3/historical/r130i1p1f1/day/tas/gr/v20200412
gs://cmip6/CMIP6/CMIP/EC-Earth-Consortium/EC-Earth3/historical/r131i1p1f1/day/tas/gr/v20200412
gs://cmip6/CMIP6/CMIP/EC-Earth-Consortium/EC-Earth3/historical/r132i1p1f1/day/tas/gr/v20200412
gs://cmip6/CMIP6/CMIP/EC-Earth-Consortium/EC-Earth3/historical/r133i1p1f1/day/tas/gr/v20200412
gs://cmip6/CMIP6/CMIP/EC-Earth-Consortium/EC-Earth3/historical/r134i1p1f1/day/tas/gr/v20200412
gs://cmip6/CMIP6/CMIP/EC-Earth-Consortium/EC-Earth3/historical/r135i1p1f1/day/tas/gr/v20200412
gs://cmip6/CMIP6/CMIP/EC-Earth-Consortium/EC-Earth3/historical/r136i1p1f1/day/tas/gr/v20200412
gs://cmip6/CMIP6/CMIP/EC-Earth-Consortium/EC-Earth3/historical/r137i1p1f1/day/tas/gr/v20200412
gs://cmip6/CMIP6/CMIP/EC-Earth-Consortium/EC-Earth3/historical/r138i1p1f1/day/tas/gr/v20200412
gs://cmip6/CMIP6/CMIP/EC-Earth-Consortium/EC-Earth3/historical/r139i1p1f1/day/tas/gr/v20200412
gs://cmip6/CMIP6/CMIP/EC-Earth-Consortium/EC-Earth3/historical/r141i1p1f1/day/tas/gr/v20200412
gs://cmip6/CMIP6/CMIP/EC-Earth-Consortium/EC-Earth3/historical/r142i1p1f1/day/tas/gr/v20200412
gs://cmip6/CMIP6/CMIP/EC-Earth-Consortium/EC-Earth3/historical/r143i1p1f1/day/tas/gr/v20200412
gs://cmip6/CMIP6/CMIP/EC-Earth-Consortium/EC-Earth3/historical/r144i1p1f1/day/tas/gr/v20200412
gs://cmip6/CMIP6/CMIP/EC-Earth-Consortium/EC-Earth3/historical/r147i1p1f1/day/tas/gr/v20200412
gs://cmip6/CMIP6/CMIP/EC-Earth-Consortium/EC-Earth3/historical/r148i1p1f1/day/tas/gr/v20200412
gs://cmip6/CMIP6/CMIP/EC-Earth-Consortium/EC-Earth3/historical/r149i1p1f1/day/tas/gr/v20200412
gs://cmip6/CMIP6/CMIP/EC-Earth-Consortium/EC-Earth3/historical/r150i1p1f1/day/tas/gr/v20200412' | etl.py --db test.sqlite --collector zarr --aggregations tas pr --etl jinja -t gcs-cmip6.json.j2 --dest test.json
```

### HDF5 Virtual Dataset

```bash
echo 'test/data/pr_Amon_ACCESS-ESM1-5_ssp585_r1i1p1f1_gn_201501-210012.nc
test/data/pr_Amon_ACCESS-ESM1-5_ssp585_r1i1p1f1_gn_210101-230012.nc
test/data/pr_Amon_ACCESS-ESM1-5_ssp585_r2i1p1f1_gn_201501-210012.nc
test/data/pr_Amon_ACCESS-ESM1-5_ssp585_r2i1p1f1_gn_210101-230012.nc
test/data/tas_Amon_ACCESS-ESM1-5_ssp585_r1i1p1f1_gn_201501-210012.nc
test/data/tas_Amon_ACCESS-ESM1-5_ssp585_r1i1p1f1_gn_210101-230012.nc
test/data/tas_Amon_ACCESS-ESM1-5_ssp585_r2i1p1f1_gn_201501-210012.nc
test/data/tas_Amon_ACCESS-ESM1-5_ssp585_r2i1p1f1_gn_210101-230012.nc' | etl.py --db test.sqlite --collector nc --aggregations tas pr --etl new-common --dest test.h5 --coord-name variant_label --coord-values-attr variant_label
```

Open the virtual dataset with xarray:

```python
import xarray

ds = xarray.open_dataset("test.h5")
ds[["tas", "pr"]].mean()
```

### NcML

```bash
echo 'test/data/pr_Amon_ACCESS-ESM1-5_ssp585_r1i1p1f1_gn_201501-210012.nc
test/data/pr_Amon_ACCESS-ESM1-5_ssp585_r1i1p1f1_gn_210101-230012.nc
test/data/pr_Amon_ACCESS-ESM1-5_ssp585_r2i1p1f1_gn_201501-210012.nc
test/data/pr_Amon_ACCESS-ESM1-5_ssp585_r2i1p1f1_gn_210101-230012.nc
test/data/tas_Amon_ACCESS-ESM1-5_ssp585_r1i1p1f1_gn_201501-210012.nc
test/data/tas_Amon_ACCESS-ESM1-5_ssp585_r1i1p1f1_gn_210101-230012.nc
test/data/tas_Amon_ACCESS-ESM1-5_ssp585_r2i1p1f1_gn_201501-210012.nc
test/data/tas_Amon_ACCESS-ESM1-5_ssp585_r2i1p1f1_gn_210101-230012.nc' | etl.py --db test.sqlite --collector nc --aggregations tas pr --etl jinja -t time-ensemble.ncml.j2 --dest test.ncml
```

Open the generated XML file with your favourite editor. You may also use [ToolsUI](https://docs.unidata.ucar.edu/netcdf-java/current/userguide/toolsui_ref.html) or [climate4R](https://github.com/SantanderMetGroup/climate4R).

#### CMIP6 DCCP

DCCP from CMIP6 is a [FMRC](https://docs.unidata.ucar.edu/netcdf-java/5.4/userguide/fmrc_ref.html).

```bash
echo 'test/data/psl_6hrPlevPt_MIROC6_dcppA-hindcast_s2009-r1i1p1f1_gn_200911010600-201001010000.nc
test/data/psl_6hrPlevPt_MIROC6_dcppA-hindcast_s2009-r2i1p1f1_gn_200911010600-201001010000.nc
test/data/psl_6hrPlevPt_MIROC6_dcppA-hindcast_s2010-r1i1p1f1_gn_201011010600-201101010000.nc
test/data/psl_6hrPlevPt_MIROC6_dcppA-hindcast_s2010-r2i1p1f1_gn_201011010600-201101010000.nc' | etl.py --etl jinja --template smgdatatools/templates/cmip6-dccp.ncml.j2 --collector nc --dest test.ncml --aggregations psl --drs '.*s(?P<subexperiment>[0-9]{4})-.*'
```
