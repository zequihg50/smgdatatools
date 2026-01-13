import os
import logging
import netCDF4

from smgdatatools.collector.lib import Collector
from smgdatatools.model.model import Store, Variable, Dimension, GlobalAttribute, Attribute, Scale


class NcCollector(Collector):
    def __init__(self, drs=None):
        super().__init__(drs)

    def read_variable(self, store, variable):
        with netCDF4.Dataset(store) as f:
            return f[variable][...]

    def read_attributes(self, store, obj=None):
        attrs = {}
        with netCDF4.Dataset(store) as f:
            if obj:
                attrs = {attr: f[obj].getncattr(attr) for attr in f[obj].ncattrs()}
            else:
                attrs = {attr: f.getncattr(attr) for attr in f.ncattrs()}

        return attrs

    def collect(self, resource):
        store = Store(name=resource)

        if os.path.isfile(resource):
            store.size = os.stat(resource).st_size

        logging.warning("Collecting from {}".format(store))
        f = netCDF4.Dataset(resource)

        # global attributes
        attrs = {attr: f.getncattr(attr) for attr in f.ncattrs()}
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

        # variables
        for v in f.variables:
            # .dtype may return a python type rather than a numpy dtype
            try:
                dtype = f[v].dtype.str
            except AttributeError:
                dtype = None

            variable = Variable(
                name=v,
                dtype=dtype,
                store_id=store.id)

            # attrs
            attrs = {attr: f[v].getncattr(attr) for attr in f[v].ncattrs()}
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
                elif attr == "_FillValue":
                    attribute = Attribute(
                        name="_FillValue",
                        value=attrs["_FillValue"],
                        variable_id=variable.id
                    )
                    variable.attrs.append(attribute)

            # dimensions
            for i, dim in enumerate(f[v].dimensions):
                if isinstance(f[v].chunking(), list):
                    dimension = Dimension(
                        index=i,
                        size=f[v].shape[i],
                        variable_id=variable.id)
                else:
                    dimension = Dimension(
                        index=i,
                        size=f[v].shape[i],
                        variable_id=variable.id)

                scale = Scale(
                    name=dim,
                    dimension_id=dimension.id,
                    variable_id=variable.id)
                dimension.scales.append(scale)
                variable.scales.append(scale)

                variable.dimensions.append(dimension)
            store.variables.append(variable)
        f.close()

        return store
