import logging
import math

import h5py

from smgdatatools.collector.lib import Collector
from smgdatatools.model.model import Store, Variable, Dimension, Filter, GlobalAttribute, Attribute, Scale, Chunk, \
    ChunkShape, FilterProperty, Compressor, CompressorProperty


class NcH5Collector(Collector):
    def __init__(self, drs=None, driver=None):
        super().__init__(drs)
        self.driver = driver
        self.drs = drs

    def read_variable(self, store, variable):
        with h5py.File(store, driver=self.driver) as f:
            return f[variable][...]

    def read_attributes(self, store, obj=None):
        with h5py.File(store, driver=self.driver) as f:
            if obj:
                attrs = dict(f[obj].attrs)
            else:
                attrs = dict(f.attrs)

        return attrs

    def collect(self, resource):
        f = h5py.File(resource, driver=self.driver)

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
            elif isinstance(attrs[attr], bytes):
                attribute = GlobalAttribute(
                    name=attr,
                    value=attrs[attr].decode("utf-8"),
                    store_id=store.id)
                store.attrs.append(attribute)

        # drs
        drs = self.parse_drs(resource)
        for facet in drs:
            global_attribute = GlobalAttribute(
                name=facet,
                value=drs[facet],
                store_id=store.id)
            store.attrs.append(global_attribute)

        for v in list(f):
            variable = Variable(
                name=v,
                dtype=f[v].dtype.str,
                fillvalue=f[v].fillvalue or None,
                store_id=store.id)

            # compressor
            if f[v].compression:
                comp = Compressor()
                comp.properties.append(CompressorProperty(
                    name="id",
                    value=f[v].compression))
                comp.properties.append(CompressorProperty(
                    name="level",
                    value=f[v].compression_opts))
                variable.compressor = comp

            # filters
            if f[v].shuffle:
                filt = Filter(variable_id=variable.id)
                filt.properties.append(FilterProperty(
                    name="id",
                    value="shuffle"))
                for x in ["elementsize"]:
                    filt.properties.append(FilterProperty(
                        name=x,
                        value=f[v].dtype.itemsize))
                variable.filters.append(filt)
            if f[v].fletcher32:
                filt = Filter(variable_id=variable.id)
                filt.properties.append(FilterProperty(
                    name="id",
                    value="fletcher32"))
                for x in ["elementsize"]:
                    filt.properties.append(FilterProperty(
                        name=x,
                        value=f[v].dtype.itemsize))
                variable.filters.append(filt)

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
                elif isinstance(attrs[attr], bytes):
                    attribute = Attribute(
                        name=attr,
                        value=attrs[attr].decode("utf-8"),
                        variable_id=variable.id)
                    variable.attrs.append(attribute)

            # dimensions
            for i, dim in enumerate(f[v].dims):
                if f[v].chunks:
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
                else:
                    dimension = Dimension(
                        index=i,
                        size=f[v].shape[i],
                        variable_id=variable.id)

                if "CLASS" in attrs:
                    if attrs["CLASS"] == b"DIMENSION_SCALE":
                        scale = Scale(
                            name=attrs["NAME"].decode("utf-8"),
                            dimension_id=dimension.id,
                            variable_id=variable.id)
                        dimension.scales.append(scale)
                        variable.scales.append(scale)

                # ToDo: review the model of scales, this adds "This is a netCDF dimension.." to the database
                # for value in dim.keys():
                #     scale = Scale(
                #         name=value,
                #         dimension_id=dimension.id,
                #         variable_id=variable.id)
                for item in dim.items():
                    scale = Scale(
                        name=item[1].name.lstrip("/"),
                        dimension_id=dimension.id,
                        variable_id=variable.id)

                    dimension.scales.append(scale)
                    variable.scales.append(scale)

                variable.dimensions.append(dimension)

            store.variables.append(variable)

        f.close()

        return store
