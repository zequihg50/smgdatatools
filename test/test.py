import unittest

import netCDF4
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import QueuePool

from smgdatatools.collector.nc import NcCollector
from smgdatatools.collector.zarr import ZarrCollector
from smgdatatools.etl.h5vds import Common, NewCommon, New, Union
from smgdatatools.etl.jinja import JinjaEtl
from smgdatatools.model.model import Base, Store


def parse_coord_values_attr(coord_values_attr_spec, stores):
    values = set()

    if coord_values_attr_spec:
        for store in stores:
            for attr in store.attrs:
                if attr.name == coord_values_attr_spec:
                    values.add(attr.value)

    return list(values)


class TestGCSZarr(unittest.TestCase):
    def test_gcs_zarr_ensemble(self):
        datasets = [
            "gs://cmip6/CMIP6/CMIP/NCAR/CESM2-FV2/historical/r1i1p1f1/Amon/tas/gn/v20191120",
            "gs://cmip6/CMIP6/CMIP/NCAR/CESM2-FV2/historical/r2i1p1f1/Amon/tas/gn/v20200226",
            "gs://cmip6/CMIP6/CMIP/NCAR/CESM2-FV2/historical/r3i1p1f1/Amon/tas/gn/v20200226",
            "gs://cmip6/CMIP6/CMIP/NCAR/CESM2-FV2/historical/r1i1p1f1/Amon/pr/gn/v20191120",
            "gs://cmip6/CMIP6/CMIP/NCAR/CESM2-FV2/historical/r2i1p1f1/Amon/pr/gn/v20200226",
            "gs://cmip6/CMIP6/CMIP/NCAR/CESM2-FV2/historical/r3i1p1f1/Amon/pr/gn/v20200226",
        ]

        collector = ZarrCollector()

        engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            echo=False,
            future=True,
            poolclass=QueuePool,
            pool_size=1)
        Base.metadata.create_all(engine)
        session = Session(engine)

        for store in (collector.collect(x) for x in datasets):
            session.add(store)

        stores = session.query(Store).all()

        etl = JinjaEtl("gcs-cmip6.json.j2", dict())
        # etl = JinjaEtl("test.j2", dict())
        etl.run(
            "gcs.json",
            collector,
            stores,
            ["tas", "pr"])

        # import xarray
        # ds = xarray.open_dataset("reference://", decode_cf=False, engine="zarr", backend_kwargs={
        #     "consolidated": False,
        #     "storage_options": {"fo": 'test/gcs.json', "remote_protocol": "gs",
        #                         "remote_options": {"anon": True}}
        # })
        # print(ds)

    def test_gcs_zarr_ensemble2(self):
        datasets = [
            "gs://cmip6/CMIP6/ScenarioMIP/CSIRO/ACCESS-ESM1-5/ssp585/r1i1p1f1/Amon/tas/gn/v20210318",
            "gs://cmip6/CMIP6/ScenarioMIP/CSIRO/ACCESS-ESM1-5/ssp585/r2i1p1f1/Amon/tas/gn/v20210318",
            "gs://cmip6/CMIP6/ScenarioMIP/CSIRO/ACCESS-ESM1-5/ssp585/r1i1p1f1/Amon/pr/gn/v20210318",
            "gs://cmip6/CMIP6/ScenarioMIP/CSIRO/ACCESS-ESM1-5/ssp585/r2i1p1f1/Amon/pr/gn/v20210318",
        ]

        collector = ZarrCollector()
        stores = [collector.collect(x) for x in datasets]
        etl = JinjaEtl("gcs-cmip6.json.j2", dict())
        etl.run(
            "gcs.json",
            collector,
            stores,
            ["tas", "pr"])

    def test_gcs_zarr_ensemble3(self):
        datasets = [
            "gs://cmip6/CMIP6/CMIP/NCAR/CESM2-FV2/historical/r1i1p1f1/Amon/pr/gn/v20191120",
            "gs://cmip6/CMIP6/CMIP/NCAR/CESM2-FV2/historical/r1i1p1f1/Amon/ta/gn/v20191120",
            "gs://cmip6/CMIP6/CMIP/NCAR/CESM2-FV2/historical/r1i1p1f1/Amon/tas/gn/v20191120",
            "gs://cmip6/CMIP6/CMIP/NCAR/CESM2-FV2/historical/r1i1p1f1/Amon/zg/gn/v20191120",
            "gs://cmip6/CMIP6/CMIP/NCAR/CESM2-FV2/historical/r2i1p1f1/Amon/pr/gn/v20200226",
            "gs://cmip6/CMIP6/CMIP/NCAR/CESM2-FV2/historical/r2i1p1f1/Amon/ta/gn/v20200226",
            "gs://cmip6/CMIP6/CMIP/NCAR/CESM2-FV2/historical/r2i1p1f1/Amon/tas/gn/v20200226",
            "gs://cmip6/CMIP6/CMIP/NCAR/CESM2-FV2/historical/r2i1p1f1/Amon/zg/gn/v20200226",
            "gs://cmip6/CMIP6/CMIP/NCAR/CESM2-FV2/historical/r3i1p1f1/Amon/pr/gn/v20200226",
            "gs://cmip6/CMIP6/CMIP/NCAR/CESM2-FV2/historical/r3i1p1f1/Amon/ta/gn/v20200226",
            "gs://cmip6/CMIP6/CMIP/NCAR/CESM2-FV2/historical/r3i1p1f1/Amon/tas/gn/v20200226",
            "gs://cmip6/CMIP6/CMIP/NCAR/CESM2-FV2/historical/r3i1p1f1/Amon/zg/gn/v20200226",

        ]

        collector = ZarrCollector()
        stores = [collector.collect(x) for x in datasets]
        aggs = parse_coord_values_attr("variable_id", stores)
        etl = JinjaEtl("gcs-cmip6.json.j2", dict())
        etl.run(
            "gcs.json",
            collector,
            stores,
            aggs)


class TestEsgfVds(unittest.TestCase):
    def test_cmip6_common_etl(self):
        datasets = [
            "data/pr_Amon_MPI-ESM1-2-LR_historical_r1i1p1f1_gn_185001-186912.nc",
            "data/pr_Amon_MPI-ESM1-2-LR_historical_r1i1p1f1_gn_187001-188912.nc",
            "data/tas_Amon_MPI-ESM1-2-LR_historical_r1i1p1f1_gn_185001-186912.nc",
            "data/tas_Amon_MPI-ESM1-2-LR_historical_r1i1p1f1_gn_187001-188912.nc",
        ]

        collector = NcCollector()
        fname = "test.h5"

        stores = [collector.collect(x) for x in datasets]
        Common().run(
            fname,
            collector,
            stores,
            ["tas", "pr"])

        # test the vds
        ds = netCDF4.Dataset(fname)
        intervald = {(185001, 186912): (0, 240), (187001, 188912): (240, 480)}
        for interval in intervald:
            with netCDF4.Dataset(
                    f"data/tas_Amon_MPI-ESM1-2-LR_historical_r1i1p1f1_gn_{interval[0]}-{interval[1]}.nc") as reference:
                reference_mean = reference.variables["tas"][:].mean()
                test_mean = ds["tas"][intervald[interval][0]:intervald[interval][1]].mean()

                self.assertEqual(reference_mean, test_mean)

            with netCDF4.Dataset(
                    f"data/pr_Amon_MPI-ESM1-2-LR_historical_r1i1p1f1_gn_{interval[0]}-{interval[1]}.nc") as reference:
                reference_mean = reference.variables["pr"][:].mean()
                test_mean = ds["pr"][intervald[interval][0]:intervald[interval][1]].mean()

                self.assertEqual(reference_mean, test_mean)

        ds.close()

    def test_cmip6_ensemble_vds(self):
        datasets = [
            # r1i1p1f1, tas and pr, 1850-1869 and 1870-1889
            "data/pr_Amon_MPI-ESM1-2-LR_historical_r1i1p1f1_gn_185001-186912.nc",
            "data/pr_Amon_MPI-ESM1-2-LR_historical_r1i1p1f1_gn_187001-188912.nc",
            "data/tas_Amon_MPI-ESM1-2-LR_historical_r1i1p1f1_gn_185001-186912.nc",
            "data/tas_Amon_MPI-ESM1-2-LR_historical_r1i1p1f1_gn_187001-188912.nc",

            # r2i1p1f1, tas and pr, 1850-1869 and 1870-1889
            "data/pr_Amon_MPI-ESM1-2-LR_historical_r2i1p1f1_gn_185001-186912.nc",
            "data/pr_Amon_MPI-ESM1-2-LR_historical_r2i1p1f1_gn_187001-188912.nc",
            "data/tas_Amon_MPI-ESM1-2-LR_historical_r2i1p1f1_gn_185001-186912.nc",
            "data/tas_Amon_MPI-ESM1-2-LR_historical_r2i1p1f1_gn_187001-188912.nc",
        ]

        collector = NcCollector()
        fname = "test.h5"

        stores = [collector.collect(x) for x in datasets]
        NewCommon(
            "variant_label",
            {"_CoordinateAxisType": "Ensemble", "standard_name": "realization"},
            ["r1i1p1f1", "r2i1p1f1"]
        ).run(
            fname,
            collector,
            stores,
            ["tas", "pr"])

        # test the vds
        ds = netCDF4.Dataset(fname)
        vld = {"r1i1p1f1": 0, "r2i1p1f1": 1}
        intervald = {(185001, 186912): (0, 240), (187001, 188912): (240, 480)}
        for vl in vld:
            for interval in intervald:
                with netCDF4.Dataset(
                        f"data/tas_Amon_MPI-ESM1-2-LR_historical_{vl}_gn_{interval[0]}-{interval[1]}.nc") as reference:
                    reference_mean = reference.variables["tas"][:].mean()
                    test_mean = ds.variables["tas"][vld[vl], intervald[interval][0]:intervald[interval][1], :, :].mean()

                    self.assertEqual(reference_mean, test_mean)

                with netCDF4.Dataset(
                        f"data/pr_Amon_MPI-ESM1-2-LR_historical_{vl}_gn_{interval[0]}-{interval[1]}.nc") as reference:
                    reference_mean = reference.variables["pr"][:].mean()
                    test_mean = ds.variables["pr"][vld[vl], intervald[interval][0]:intervald[interval][1], :, :].mean()

                    self.assertEqual(reference_mean, test_mean)

        ds.close()

    def test_cmip6_fx_ensemble_vds(self):
        datasets = [
            "data/orog_fx_MPI-ESM1-2-LR_historical_r1i1p1f1_gn.nc",
            "data/sftlf_fx_MPI-ESM1-2-LR_historical_r2i1p1f1_gn.nc",
            "data/sftlf_fx_MPI-ESM1-2-LR_historical_r1i1p1f1_gn.nc",
            "data/orog_fx_MPI-ESM1-2-LR_historical_r2i1p1f1_gn.nc",
        ]

        collector = NcCollector()
        fname = "test.h5"

        stores = [collector.collect(x) for x in datasets]
        New(
            "variant_label",
            {"_CoordinateAxisType": "Ensemble", "standard_name": "realization"},
            ["r1i1p1f1", "r2i1p1f1"]
        ).run(
            fname,
            collector,
            stores,
            ["orog", "sftlf"])

        # test the vds
        ds = netCDF4.Dataset(fname)
        vld = {"r1i1p1f1": 0, "r2i1p1f1": 1}
        for vl in vld:
            with netCDF4.Dataset(
                    f"data/sftlf_fx_MPI-ESM1-2-LR_historical_{vl}_gn.nc") as reference:
                reference_mean = reference.variables["sftlf"][:].mean()
                test_mean = ds.variables["sftlf"][vld[vl], :, :].mean()

                self.assertEqual(reference_mean, test_mean)

            with netCDF4.Dataset(
                    f"data/orog_fx_MPI-ESM1-2-LR_historical_{vl}_gn.nc") as reference:
                reference_mean = reference.variables["orog"][:].mean()
                test_mean = ds.variables["orog"][vld[vl], :, :].mean()

                self.assertEqual(reference_mean, test_mean)

        ds.close()

    def test_cmip6_new_common_vds_year2300(self):
        datasets = [
            # r1i1p1f1, tas and pr, 1850-1869 and 1870-1889
            "data/pr_Amon_ACCESS-ESM1-5_ssp585_r1i1p1f1_gn_201501-210012.nc",
            "data/pr_Amon_ACCESS-ESM1-5_ssp585_r1i1p1f1_gn_210101-230012.nc",
            "data/tas_Amon_ACCESS-ESM1-5_ssp585_r1i1p1f1_gn_201501-210012.nc",
            "data/tas_Amon_ACCESS-ESM1-5_ssp585_r1i1p1f1_gn_210101-230012.nc",

            # r2i1p1f1, tas and pr, 1850-1869 and 1870-1889
            "data/pr_Amon_ACCESS-ESM1-5_ssp585_r2i1p1f1_gn_201501-210012.nc",
            "data/pr_Amon_ACCESS-ESM1-5_ssp585_r2i1p1f1_gn_210101-230012.nc",
            "data/tas_Amon_ACCESS-ESM1-5_ssp585_r2i1p1f1_gn_201501-210012.nc",
            "data/tas_Amon_ACCESS-ESM1-5_ssp585_r2i1p1f1_gn_210101-230012.nc",
        ]

        collector = NcCollector()
        fname = "test.h5"

        stores = [collector.collect(x) for x in datasets]
        NewCommon(
            "variant_label",
            {"_CoordinateAxisType": "Ensemble", "standard_name": "realization"},
            ["r1i1p1f1", "r2i1p1f1"]
        ).run(
            fname,
            collector,
            stores,
            ["tas", "pr"])

        # test the vds
        ds = netCDF4.Dataset(fname)
        vld = {"r1i1p1f1": 0, "r2i1p1f1": 1}
        intervald = {(201501, 210012): (0, 1032), (210101, 230012): (1032, 3432)}
        for vl in vld:
            for interval in intervald:
                with netCDF4.Dataset(
                        f"data/tas_Amon_ACCESS-ESM1-5_ssp585_{vl}_gn_{interval[0]}-{interval[1]}.nc") as reference:
                    reference_mean = reference.variables["tas"][:].mean()
                    test_mean = ds.variables["tas"][vld[vl], intervald[interval][0]:intervald[interval][1], :, :].mean()

                    self.assertEqual(reference_mean, test_mean)

                with netCDF4.Dataset(
                        f"data/pr_Amon_ACCESS-ESM1-5_ssp585_{vl}_gn_{interval[0]}-{interval[1]}.nc") as reference:
                    reference_mean = reference.variables["pr"][:].mean()
                    test_mean = ds.variables["pr"][vld[vl], intervald[interval][0]:intervald[interval][1], :, :].mean()

                    self.assertEqual(reference_mean, test_mean)

        ds.close()

    def test_union_ia(self):
        datasets = ["data/union/ia/tn_CORDEX-NAM_historical_mon_197001-200512.nc"]

        collector = NcCollector()
        fname = "test.h5"

        engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            echo=False,
            future=True,
            poolclass=QueuePool,
            pool_size=1)
        Base.metadata.create_all(engine)
        session = Session(engine)

        for store in (collector.collect(x) for x in datasets):
            session.add(store)

        stores = session.query(Store).all()

        Union().run(
            fname,
            collector,
            stores,
            list())

        session.close()
        engine.dispose()


if __name__ == "__main__":
    unittest.main()
