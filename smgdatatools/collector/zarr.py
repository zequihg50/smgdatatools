import logging
import math

import gcsfs
import zarr

from smgdatatools.collector.lib import Collector
from smgdatatools.model.model import Store, Variable, Attribute, Dimension, ChunkShape, Scale, Chunk, \
    GlobalAttribute, Compressor, CompressorProperty


class ZarrCollector(Collector):
    def __init__(self, drs=None):
        super().__init__(drs)

    def collect(self, resource):
        logging.warning("Collecting from {}".format(resource))

        fs = gcsfs.GCSFileSystem(token="anon")
        mapper = fs.get_mapper(resource)
        f = zarr.open(mapper)
        store = Store(name=resource, size=0)

        # global attrs
        attrs = dict(f.attrs)
        for attr in attrs:
            if attr in self.ignored_attrs():
                continue
            elif isinstance(attrs[attr], str):
                attribute = GlobalAttribute(
                    name=attr,
                    value=attrs[attr],
                    store_id=store.id)
                store.attrs.append(attribute)

        for v in f:
            variable = Variable(
                name=v,
                dtype=f[v].dtype.str,
                fillvalue=f[v].fill_value,
                store_id=store.id)

            # compressor
            if f[v].compressor:
                comp_config = f[v].compressor.get_config()
                comp = Compressor()
                for k in comp_config:
                    if k != "id":
                        comp.properties.append(CompressorProperty(
                            name=k,
                            value=comp_config[k]))
                variable.compressor = comp

            # filters
            if f[v].filters:
                pass

            # attrs
            attrs = dict(f[v].attrs)
            for attr in attrs:
                if attr in self.ignored_attrs():
                    continue
                elif isinstance(attrs[attr], str):
                    attribute = Attribute(
                        name=attr,
                        value=attrs[attr],
                        variable_id=variable.id)
                    variable.attrs.append(attribute)

            # dimensions
            for i, dim in enumerate(f[v].shape):
                dimension = Dimension(
                    index=i,
                    size=f[v].shape[i],
                    chunk_count=math.ceil(f[v].shape[i] / f[v].chunks[i]),
                    variable_id=variable.id)
                chunk_shape = ChunkShape(
                    dimension_id=dimension.id,
                    shape=f[v].chunks[i],
                    index=i)
                dimension.chunk_shapes.append(chunk_shape)

                # scales
                if "_ARRAY_DIMENSIONS" in attrs:
                    scale = Scale(
                        name=attrs["_ARRAY_DIMENSIONS"][i],
                        dimension_id=dimension.id,
                        variable_id=variable.id)
                    dimension.scales.append(scale)
                    variable.scales.append(scale)

                variable.dimensions.append(dimension)

            for i in range(f[v].nchunks):
                chunk = Chunk(
                    location=0,
                    size=0,  # referenceFS reads whole object if size is zero
                    index=i,
                    variable_id=variable.id)
                variable.chunks.append(chunk)

            store.variables.append(variable)

        return store

    def read_variable(self, store, variable):
        pass

    def read_attributes(self, store, obj=None):
        fs = gcsfs.GCSFileSystem(token="anon")
        mapper = fs.get_mapper(store)
        f = zarr.open(mapper)
        if obj:
            attrs = dict(f[obj].attrs)
        else:
            attrs = dict(f.attrs)

        return attrs

    def compressor(self, store, v):
        fs = gcsfs.GCSFileSystem(token="anon")
        mapper = fs.get_mapper(store)
        f = zarr.open(mapper)
        compressor = f[v].compressor

        return compressor
