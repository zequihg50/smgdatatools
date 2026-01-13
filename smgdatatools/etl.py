#!/usr/bin/env python

import argparse
import asyncio
import copy
import logging
import os
import sys

from sqlalchemy import select, create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import QueuePool

from smgdatatools.collector.h5 import Hdf5ChunkCollector
from smgdatatools.collector.nch5 import NcH5Collector
from smgdatatools.collector.nc import NcCollector
from smgdatatools.collector.zarr import ZarrCollector
from smgdatatools.etl.h5vds import Common, Union, NewCommon, New
from smgdatatools.etl.jinja import JinjaEtl
from smgdatatools.model.model import Store, GlobalAttribute, Base


def parse_key_value(key_value):
    kv = dict()

    if key_value:
        for attr in key_value.split(","):
            pair = attr.split("=")
            k, v = pair[0], pair[1]
            kv[k] = v

    return kv


def parse_coord_values_attr(coord_values_attr_spec, stores):
    values = set()

    if coord_values_attr_spec:
        for store in stores:
            for attr in store.attrs:
                if attr.name == coord_values_attr_spec:
                    values.add(attr.value)

    return list(values)


def sync_collect(f, collector):
    store = None
    try:
        store = collector.collect(f)
        return collector.collect(f)
    except:
        print("Error on store {}".format(store), file=sys.stderr)
        raise


async def collect(file, collector):
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, sync_collect, file, collector)
    return data


async def collect_all(stores, collector):
    tasks = []

    for store in stores:
        # Start reading file asynchronously
        task = asyncio.create_task(collect(store, collector))
        tasks.append(task)

    # Wait for all file reading tasks to complete
    results = await asyncio.gather(*tasks)

    return results


if __name__ == "__main__":
    # arguments
    parser = argparse.ArgumentParser(description="Data model and library for performing scientific ETLs.")
    parser.add_argument("--log-file",
                        type=str,
                        required=False,
                        default=None,
                        help="log file.")
    parser.add_argument("--log-level",
                        type=str,
                        required=False,
                        default="warn",
                        help="log level.")
    parser.add_argument("-d", "--dest",
                        type=str,
                        required=False,
                        help="destination file.")
    parser.add_argument("--db",
                        required=False,
                        type=str,
                        help="destination db file.")
    parser.add_argument("--from-db",
                        required=False,
                        type=str,
                        help="source db file (do not use if --db is used).")
    parser.add_argument("-t", "--template",
                        type=str,
                        required=False,
                        default="basic.ncml.j2",
                        help="jinja template for jinja ETLs.")
    parser.add_argument("-o", "--opts",
                        required=False,
                        default=dict(),
                        type=str,
                        help="Comma separated key=value pairs for additional variables in Jinja templates.")
    parser.add_argument("--drs",
                        type=str,
                        required=False,
                        help="regex of the DRS of the input files.")
    parser.add_argument("--from",
                        type=str,
                        required=False,
                        default="-",
                        help="read files from FILE instead of stdin.")
    parser.add_argument("--etl",
                        choices=["jinja", "common", "new-common", "new", "union"],
                        type=str,
                        required=False,
                        help="ETL to perform.")
    parser.add_argument("--collector",
                        choices=["nc", "zarr", "hdf5chunk", "nch5"],
                        required=True,
                        type=str,
                        help="collector.")
    parser.add_argument("--batch-size",
                        default=100,
                        type=int,
                        help="number of stores to harvest before commit to db.")
    parser.add_argument("--aggregations",
                        type=str,
                        nargs="*",
                        default=list(),
                        help="aggregation variables.")
    parser.add_argument("--aggregations-attr",
                        required=False,
                        type=str,
                        default=None,
                        help="aggregation variables detected by global attribute.")

    # arguments for hdf5chunk collector
    parser.add_argument("--hdf5-driver",
                        required=False,
                        default=None,
                        type=str,
                        help="HDF5 file driver.")
    parser.add_argument("-j", "--jobs",
                        type=int,
                        required=False,
                        default=5,
                        help="collector parallel jobs for chunked ETLs.")
    parser.add_argument("--chunk-size",
                        type=str,
                        required=False,
                        default=None,
                        help="for contiguous variables, emulate a chunked variable.")

    # arguments for join new
    parser.add_argument("--coord-attrs",
                        required=False,
                        default=None,
                        type=str,
                        help="Comma separated key=value pairs of attributes for joinNew ETLs.")
    parser.add_argument("--coord-name",
                        required=False,
                        default=None,
                        type=str,
                        help="Name of the coordinate for joinNew ETLs.")
    parser.add_argument("--coord-values",
                        required=False,
                        default=None,
                        type=str,
                        help="Comma separated values of the coordinate for joinNew ETLs.")
    parser.add_argument("--coord-values-attr",
                        required=False,
                        default=None,
                        type=str,
                        help="Global attribute of the store used to locate values of the coordinate for joinNew ETLs.")

    args = vars(parser.parse_args())

    logging.basicConfig(
        filename=args["log_file"],
        encoding='utf-8',
        level=getattr(logging, args["log_level"].upper()))

    # set up engine
    if args["from_db"]:
        db_url = "sqlite+pysqlite:///{}".format(args["from_db"])
    elif args["db"]:
        if os.path.isfile(args["db"]):
            os.remove(args["db"])
        db_url = "sqlite+pysqlite:///{}".format(args["db"])
    else:
        # in memory engine
        # raise ValueError("--db or --from-db must be used.")
        db_url = "sqlite+pysqlite:///:memory:"

    engine = create_engine(
        db_url,
        echo=False,
        future=True,
        poolclass=QueuePool,
        pool_size=args["jobs"])
    Base.metadata.create_all(engine)

    # set up collector
    if args["collector"] == "hdf5chunk":
        collector = Hdf5ChunkCollector(
            drs=args["drs"],
            driver=args["hdf5_driver"],
            chunk_size=args["chunk_size"])
    elif args["collector"] == "nc":
        collector = NcCollector(
            drs=args["drs"])
    elif args["collector"] == "nch5":
        collector = NcH5Collector(
            drs=args["drs"],
            driver=args["hdf5_driver"])
    elif args["collector"] == "zarr":
        collector = ZarrCollector(
            drs=args["drs"])
    else:
        raise ValueError("Invalid collector.")

    if not args["from_db"]:
        if args["from"] == "-":
            inputs = list(line.rstrip("\n") for line in sys.stdin)
        else:
            inputs = list(line.rstrip("\n") for line in open(args["from"], "r"))

        for i in range(0, len(inputs), args["batch_size"]):
            print("batch: {}".format(i), file=sys.stderr)
            session = Session(engine)
            stores = asyncio.run(collect_all(inputs[i:i+args["batch_size"]], collector))
            for store in stores:
                session.add(store)
            session.commit()
            session.close()

    # perform ETL
    if args["etl"]:
        # set up engine
        session = Session(engine)
        stores = session.query(Store).all()

        # set up ETL
        if args["etl"].lower() == "jinja":
            etl = JinjaEtl(
                args["template"],
                parse_key_value(args["opts"]))
        elif args["etl"].lower() == "common":
            etl = Common()
        elif args["etl"].lower() == "union":
            etl = Union()
        elif args["etl"].lower() == "new-common":
            if args["coord_values"]:
                coord_values = args["coord_values"].split(",")
            elif args["coord_values_attr"]:
                coord_values = parse_coord_values_attr(args["coord_values_attr"], stores)
            else:
                coord_values = list()

            etl = NewCommon(
                args["coord_name"],
                parse_key_value(args["coord_attrs"]),
                coord_values)
        elif args["etl"].lower() == "new":
            if args["coord_values"]:
                coord_values = args["coord_values"].split(",")
            elif args["coord_values_attr"]:
                coord_values = parse_coord_values_attr(args["coord_values_attr"], stores)
            else:
                coord_values = list()

            etl = New(
                args["coord_name"],
                parse_key_value(args["coord_attrs"]),
                coord_values)
        else:
            raise ValueError("Invalid ETL.")

        # drs
        global_attrs = session.execute(
            select(GlobalAttribute.name, GlobalAttribute.value)
        ).all()
        dest = args["dest"].format(**dict(global_attrs))

        # aggregations
        if args["aggregations_attr"]:
            aggregations = session.execute(
                select(GlobalAttribute.value).where(
                    GlobalAttribute.name == args["aggregations_attr"])).scalars().unique().all()
        else:
            aggregations = args["aggregations"]

        # etl
        os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
        etl.run(dest, collector, stores, aggregations)
        session.close()
        engine.dispose()
        print(dest)
