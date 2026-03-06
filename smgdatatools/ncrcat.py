import sys
import argparse
import math

import numpy as np
from mpi4py import MPI

import netCDF4
import cftime

# prototype search
## 1) use the first file provided
## 2) do the union of variables of all files provided

# time location
## 1) user param (default = "time")
## 2) CF search by units attr

# writer
## 1) write to single file
## 2) write to different files encompasing different time periods

# writting performance
## 1) serial
## 2) parallel hdf5

def never_uint8(dtype):
    if isinstance(dtype, str):
        if dtype.endswith("i8"):
            return np.dtype("i4")
    if isinstance(dtype, np.dtype):
        if dtype.name == "int64":
            return np.dtype("i4")
    return dtype

class Prototype:
    def __init__(self, time, times):
        self._time = time
        self._times = times

    def write(self, nc, fs):
        raise NotImplementedError

class FirstFilePrototype(Prototype):
    def __init__(self, time, times, chunk_sizes):
        super().__init__(time, times)
        self._chunk_sizes = chunk_sizes

    def write(self, nc, fs):
        p = fs[0]

        with netCDF4.Dataset(p, "r") as f:
            for attr in f.ncattrs():
                nc.setncattr(attr, f.getncattr(attr))

            for d in f.dimensions:
                if self._time == d:
                    nc.createDimension(
                            d,
                            len(self._times))
                else:
                    nc.createDimension(
                            d,
                            f.dimensions[d].size)

            # all variables
            for v in f.variables:
                if self._time == v or ("bounds" in f[TIME_VAR].ncattrs() and v == f[TIME_VAR].getncattr("bounds")):
                    continue

                if len(f[v].shape) <= 2:
                    nc.createVariable(
                            v,
                            never_uint8(f[v].dtype),
                            f[v].dimensions,
                            compression="zlib",
                            complevel=1,
                            fill_value=f[v].getncattr("_FillValue") if "_FillValue" in f[v].ncattrs() else None,
                            shuffle=True,
                            fletcher32=True)
                    for attr in f[v].ncattrs():
                        if not attr.startswith("_"):
                            nc[v].setncattr(attr, f[v].getncattr(attr))
                    nc[v][...] = f[v][...]
                else:
                    if v in self._chunk_sizes:
                        chunking = self._chunk_sizes[v]
                    else:
                        chunking = tuple([1]*len(f[v].shape[:-2]) + list(f[v].shape[-2:]))
                    nc.createVariable(
                            v,
                            never_uint8(f[v].dtype),
                            f[v].dimensions,
                            chunksizes=chunking,
                            compression="zlib",
                            complevel=1,
                            fill_value=f[v].getncattr("_FillValue") if "_FillValue" in f[v].ncattrs() else None,
                            shuffle=True,
                            fletcher32=True)
                    for attr in f[v].ncattrs():
                        if not attr.startswith("_"):
                            nc[v].setncattr(attr, f[v].getncattr(attr))

            # time variable
            nc.createVariable(
                    self._time,
                    never_uint8(f[self._time].dtype),
                    f[self._time].dimensions,
                    compression="zlib",
                    complevel=1,
                    fill_value=f[self._time].getncattr("_FillValue") if "_FillValue" in f[self._time].ncattrs() else None,
                    shuffle=True,
                    fletcher32=True)
            for attr in f[self._time].ncattrs():
                if not attr.startswith("_"):
                    nc[self._time].setncattr(attr, f[self._time].getncattr(attr))

            # time bounds
            if "bounds" in nc[TIME_VAR].ncattrs():
                bounds_name = nc[TIME_VAR].getncattr("bounds")
                nc.createVariable(
                        bounds_name,
                        never_uint8(nc[self._time].dtype),
                        f[bounds_name].dimensions,
                        compression="zlib",
                        complevel=1,
                        fill_value=f[bounds_name].getncattr("_FillValue") if "_FillValue" in f[bounds_name].ncattrs() else None,
                        shuffle=True,
                        fletcher32=True)
                for attr in f[bounds_name].ncattrs():
                    if not attr.startswith("_"):
                        nc[bounds_name].setncattr(attr, f[bounds_name].getncattr(attr))


class NFieldsFirstFilePrototype(Prototype):
    def __init__(self, time, times):
        self._ffp = FirstFilePrototype(time, times)
        self._time = time

    def write(self, nc, fs):
        self._ffp.write(nc, fs)
        ignore = [] # these are to be ignored
        with netCDF4.Dataset(fs[0], "r") as f:
            for v in f.variables:
                ignore.append(v)
        # 1) only consider field variables that are concatenated over record dimension?
        # 2) ineffient but ...
        for f in fs:
            src = netCDF4.Dataset(f, "r")
            for v in src.variables:
                if v in ignore:
                    continue
                ignore.append(v)

                if len(src[v].dimensions) >= 3 and src[v].dimensions[0] == self._time:
                    nc.createVariable(
                            v,
                            never_uint8(src[v].dtype),
                            src[v].dimensions,
                            chunksizes=src[v].chunking(),
                            compression="zlib",
                            complevel=1,
                            fill_value=src[v].getncattr("_FillValue") if "_FillValue" in src[v].ncattrs() else None,
                            shuffle=True,
                            fletcher32=True)
                    for attr in src[v].ncattrs():
                        if not attr.startswith("_"):
                            nc[v].setncattr(attr, src[v].getncattr(attr))
                else:
                    nc.createVariable(
                            v,
                            never_uint8(src[v].dtype),
                            src[v].dimensions,
                            compression="zlib",
                            complevel=1,
                            fill_value=src[v].getncattr("_FillValue") if "_FillValue" in src[v].ncattrs() else None,
                            shuffle=True,
                            fletcher32=True)
                    for attr in src[v].ncattrs():
                        if not attr.startswith("_"):
                            nc[v].setncattr(attr, src[v].getncattr(attr))
                    nc[v][...] = src[v][...]
            src.close()


class VariableWriter:
    def write(self, nc, fs):
        pass


if __name__ == "__main__":
    # parallel
    comm = MPI.COMM_WORLD
    size = comm.Get_size()
    rank = comm.Get_rank()
    TIME_VAR = "time"

    if rank == 0:
        parser = argparse.ArgumentParser(description="Python version of ncrcat - netCDF Record Concatenator ")
        parser.add_argument("-i", "--input-file",
                            type=str,
                            required=False,
                            default="-",
                            help="Read netCDF files from file instead of stdin.")
        parser.add_argument("-d", "--dest",
                            type=str,
                            required=True,
                            help="Destination netCDF file.")
        parser.add_argument("-c", "--chunks",
                            nargs="*",
                            type=str,
                            required=False,
                            default={},
                            help="Chunk sizes: -c var1:1x180x360 var2:2x90x180")
        args = vars(parser.parse_args())

        # time info
        dates = []
        dates_files_counts = []
        dates_files_names  = []

        vars_files = {}

        dst = netCDF4.Dataset(args["dest"], "w")

        #for line in sys.stdin:
        if args["input_file"] == "-":
            inpt = sys.stdin
        else:
            inpt = open(args["input_file"], "r")

        #chunk sizes
        chunk_sizes = {}
        for c in args["chunks"]:
            parts = c.split(":")
            v = parts[0]
            sizes = tuple([int(x) for x in parts[1].split("x")])
            chunk_sizes[v] = sizes

        global_time_units = None
        global_time_calendar = None
        for i,line in enumerate(inpt):
            l = line.rstrip("\n")
            with netCDF4.Dataset(l) as f:
                v = f[TIME_VAR]
                units = v.getncattr("units")
                calendar = v.getncattr("calendar")
                if global_time_units is None:
                    global_time_units = units
                    global_time_calendar = calendar
                vs = cftime.num2date(v[...], units, calendar)

                dates.extend(vs)
                dates_files_counts.append(len(vs))
                dates_files_names.append(l)

                for v in f.variables:
                    if v not in vars_files:
                        vars_files[v] = set()
                    vars_files[v].add(i)

        if args["input_file"] != "-":
            inpt.close()

        prototype = FirstFilePrototype(TIME_VAR, dates, chunk_sizes)
        #prototype = NFieldsFirstFilePrototype(TIME_VAR, dates) # currently not working
        prototype.write(dst, dates_files_names)

        dst.close()
    else:
        args = None
        dates_files_names = None
        dates_files_counts = None
        vars_files = None

    args = comm.bcast(args, root=0)
    dates_files_names = comm.bcast(dates_files_names, root=0)
    dates_files_counts = comm.bcast(dates_files_counts, root=0)
    vars_files = comm.bcast(vars_files, root=0)

    dst = netCDF4.Dataset(args["dest"], "a", parallel=True, comm=comm)
    # write variable values in parallel
    vwriter = VariableWriter()
    vwriter.write(dst, dates_files_names)

    for v in dst.variables:
        # set collective - required to write compressed data
        # https://unidata.github.io/netcdf4-python/#parallel-io
        ncv = dst[v]
        ncv.set_collective(True)
        # i have commented this "if" because time values are copied currently in the "prototype"
        if v == TIME_VAR or ("bounds" in dst[TIME_VAR].ncattrs() and v == dst[TIME_VAR].getncattr("bounds")):
            # locate the files that contain this variable
            fs = [dates_files_names[i] for i in vars_files[v]]
            # each file is processed in parallel
            for i in range(0, len(fs), size):
                j = min(i + rank, len(fs) - 1)
                # the "counts" array is useful now to now how many time steps I need to write to dest
                counts = np.array([0] + dates_files_counts)
                counts_sum = counts.cumsum()
                with netCDF4.Dataset(fs[j]) as src:
                    frm = counts_sum[j]
                    to  = counts_sum[j+1]
                    ncv[frm:to] = cftime.date2num(
                        cftime.num2date(
                            src[v][...],
                            src[TIME_VAR].getncattr("units"),
                            src[TIME_VAR].getncattr("calendar")),
                        dst[TIME_VAR].getncattr("units"),
                        dst[TIME_VAR].getncattr("calendar"))

        if len(ncv.shape) >= 3:
            # locate the files that contain this variable
            fs = [dates_files_names[i] for i in vars_files[v]]
            # each file is processed in parallel
            for i in range(0, len(fs), size):
                j = min(i + rank, len(fs) - 1)
                # the "counts" array is useful now to now how many time steps I need to write to dest
                counts = np.array([0] + dates_files_counts)
                counts_sum = counts.cumsum()
                with netCDF4.Dataset(fs[j]) as src:
                    frm = counts_sum[j]
                    to  = counts_sum[j+1]
                    #ncv[frm:to] = src[v][...]
                    TAMANIO = 500
                    local_iters = math.ceil((to - frm) / TAMANIO)
                    max_iters = comm.allreduce(local_iters, op=MPI.MAX)
                    frm_k = frm
                    to_k = min(frm_k + TAMANIO, to)
                    max_k = 0
                    for k in range(max_iters): # esto lo q hace es escribir sin parar en la misma region para dar el mismo numero de iteraciones
                        #print(f"(rank {rank}: Write chunk {frm_k}-{to_k} from file {fs[j]} (max_iters={max_iters}, local_iters={local_iters}, k={k}, frm_k={frm_k}, to_k={to_k}).", flush=True)
                        try:
                            ncv[frm_k:to_k] = src[v][TAMANIO*max_k:min(TAMANIO*(max_k+1), src[v].shape[0])]
                        except:
                            #print(f"exception: rank {rank}", flush=True)
                            raise
                        #print(f"(rank {rank}: Done chunk {frm_k}-{to_k} from file {fs[j]}.", flush=True)
                        if k < local_iters-1:
                            frm_k += TAMANIO
                            to_k = min(to_k + TAMANIO, to)
                            max_k += 1
    comm.Barrier()
    dst.close()
