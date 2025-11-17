import logging

import h5py

from smgdatatools.collector.lib import Collector
from smgdatatools.etl.lib import Etl, convert_times
from smgdatatools.model.model import Store, Variable, Dimension

logger = logging.getLogger(__name__)

NOT_A_VAR = "This is a netCDF dimension but not a netCDF variable.    "


def create_char_attr(o, k, v):
    try:
        o.attrs.create(k, v, dtype="S" + str(len(v)))
    except UnicodeEncodeError:
        # logger.warning("Error setting char attribute, o: {}, k: {}, v: {}.".format(o.name, k, v))
        pass


def create_attr(o, k, v):
    if isinstance(v, str):
        create_char_attr(o, k, v)
    else:
        o.attrs[k] = v


def create_dimension(o, name, size, dtype=None):
    if dtype:
        o.create_dataset(name, (size,), dtype=dtype)
    else:
        o.create_dataset(name, (size,), dtype="S1")
    o[name].make_scale(name)
    create_char_attr(o[name], "NAME", NOT_A_VAR + name)


def create_virtual_variable(f: h5py.File, v: Variable):
    shape = tuple([d.size for d in sorted(v.dimensions, key=lambda x: x.index)])
    layout = h5py.VirtualLayout(
        shape=shape,
        dtype=h5py.string_dtype() if not v.dtype else v.dtype)
    vsource = h5py.VirtualSource(v.store.name, v.name, shape=shape)

    # be careful with scalar variables
    if shape == tuple():
        layout[()] = vsource
    else:
        layout[...] = vsource

    f.create_virtual_dataset(v.name, layout)
    attrs = {attr.name: attr.value for attr in v.attrs}
    for attr in attrs:
        if not (attr == "CLASS" or attr == "NAME" or attr.startswith("_")):
            create_attr(f[v.name], attr, attrs[attr])


class Union(Etl):
    def run(self, dest: str, collector: Collector, stores: list, aggregations: list[str]):
        f: h5py.File = h5py.File(dest, "w")

        variables = list()
        for store in stores:
            variables.extend(store.variables)

        # create dimensions (scales not present as variables)
        scales = [scale
                  for store in stores
                  for variable in store.variables
                  for dimension in variable.dimensions
                  for scale in dimension.scales]
        variable_names = [variable.name for variable in variables]
        for scale in scales:
            if scale.name not in variable_names and scale.name not in f:
                create_dimension(f, scale.name, scale.dimension.size)

        # dimension scales
        for v in variables:
            if v.name in f:
                continue
            elif v.name in [scale.name for scale in scales]:
                create_virtual_variable(f, v)
                f[v.name].make_scale(v.name)

        # virtual variables
        for v in variables:
            if v.name in f:
                continue
            else:
                create_virtual_variable(f, v)
                for dimension in v.dimensions:
                    for scale in dimension.scales:
                        f[v.name].dims[dimension.index].attach_scale(f[scale.name])

        f.close()


class New(Etl):
    def __init__(self, name, attrs, values):
        self.name = name
        self.attrs = attrs
        self.values = values

    def run(self, dest: str, collector: Collector, stores: list, aggregations: list[str]):
        f: h5py.File = h5py.File(dest, "w")

        # need to include only one ensemble from one "aggregation variable"
        aggregation_stores = [store
                              for store in sorted(stores, key=lambda x: x.name)
                              for v in store.variables
                              if ((v.name == aggregations[0]) and
                                  ({attr.name: attr.value for attr in store.attrs}[self.name] == self.values[0]))]
        proto_aggregation: Variable = [v
                                       for s in aggregation_stores
                                       for v in s.variables if v.name == aggregations[0]][0]

        proto_store: Store = proto_aggregation.store

        # virtual variables
        for store in stores:
            for v in store.variables:
                if v.name in f:
                    # ToDo: warning
                    continue

                if v.name not in aggregations:
                    attrs = {attr.name: attr.value for attr in v.attrs}
                    if "CLASS" in attrs and attrs["CLASS"] == "DIMENSION_SCALE":
                        if attrs["NAME"].startswith(NOT_A_VAR):
                            create_dimension(f, v.name, v.dimensions[0].size)
                        else:
                            create_virtual_variable(f, v)
                            f[v.name].make_scale(v.name)
                    else:
                        create_virtual_variable(f, v)

        f.create_dataset(
            self.name,
            (len(self.values),),
            dtype=h5py.string_dtype("utf-8", None),
            chunks=True,
            compression="gzip",
            compression_opts=1)
        f[self.name][:] = self.values
        f[self.name].make_scale(self.name)
        for attr in self.attrs:
            create_attr(f[self.name], attr, self.attrs[attr])

        for aggregation in aggregations:
            aggregation_subset = [store
                                  for store in sorted(stores, key=lambda x: x.name)
                                  for v in store.variables
                                  if v.name == aggregation]
            proto = [v for v in aggregation_subset[0].variables if v.name == aggregation][0]
            proto_dimensions = sorted(proto.dimensions, key=lambda x: x.index)

            layout = h5py.VirtualLayout(
                shape=tuple(
                    [len(self.values)] +
                    [d.size for d in proto_dimensions]),
                dtype=proto.dtype)

            for ncoord, coord in enumerate(self.values):
                subset = [store
                          for store in aggregation_subset
                          if {attr.name: attr.value for attr in store.attrs}[self.name] == coord]
                proto = [v for v in subset[0].variables if v.name == aggregation][0]
                proto_dimensions = sorted(proto.dimensions, key=lambda x: x.index)

                i = 0
                for store in subset:
                    current = [v for v in store.variables if v.name == aggregation][0]
                    current_dimensions = sorted(current.dimensions, key=lambda x: x.index)

                    vsource = h5py.VirtualSource(
                        store.name,
                        aggregation,
                        tuple([d.size for d in current_dimensions]))

                    frm, to = i, i + current_dimensions[0].size
                    layout[ncoord, frm:to] = vsource
                    i += int(current_dimensions[0].size)

            # ToDo: need to include fill_value
            f.create_virtual_dataset(aggregation, layout)
            attrs = collector.read_attributes(proto.store.name, proto.name)
            for attr in attrs:
                create_attr(f[aggregation], attr, attrs[attr])

            # Dimension scales
            f[aggregation].dims[0].attach_scale(f[self.name])
            for d in proto_dimensions:
                f[aggregation].dims[d.index + 1].attach_scale(f[d.scales[0].name])

        # global attributes
        attrs = collector.read_attributes(proto_store.name)
        for attr in attrs:
            create_attr(f, attr, attrs[attr])

        f.close()


class Common(Etl):
    def run(self, dest: str, collector: Collector, stores: list, aggregations: list[str]):
        f: h5py.File = h5py.File(dest, "w")

        aggregation_stores = [store
                              for store in sorted(stores, key=lambda x: x.name)
                              for v in store.variables if v.name == aggregations[0]]
        proto_aggregation: Variable = [v
                                       for s in aggregation_stores
                                       for v in s.variables if v.name == aggregations[0]][0]

        proto_store: Store = proto_aggregation.store
        proto_dim: Dimension = [d for d in proto_aggregation.dimensions if d.index == 0][0]
        proto_agg_var: Variable = [v for v in proto_store.variables if v.name == proto_dim.scales[0].name][0]

        # assume aggregation dimension is always a coordinate variable
        join_existing_dim_size: int = int(
            sum([d.size
                 for s in stores
                 for v in s.variables if v.name == aggregations[0]
                 for d in v.dimensions if d.index == 0]))

        # create the aggregation dimension
        f.create_dataset(
            proto_agg_var.name,
            (join_existing_dim_size,),
            proto_agg_var.dtype,
            chunks=True,
            compression="gzip",
            compression_opts=1,
            shuffle=True)
        f[proto_agg_var.name].make_scale(proto_agg_var.name)
        proto_agg_var_attrs = collector.read_attributes(proto_agg_var.store.name, proto_agg_var.name)
        for attr in proto_agg_var_attrs:
            create_attr(f[proto_agg_var.name], attr, proto_agg_var_attrs[attr])

        if "bounds" in proto_agg_var_attrs:
            create_dimension(f, "bnds", 2)
            f.create_dataset(
                proto_agg_var_attrs["bounds"],
                (join_existing_dim_size, 2),
                proto_agg_var.dtype,
                chunks=True,
                compression="gzip",
                compression_opts=1,
                shuffle=True)
            f[proto_agg_var_attrs["bounds"]].dims[0].attach_scale(f[proto_agg_var.name])
            f[proto_agg_var_attrs["bounds"]].dims[1].attach_scale(f["bnds"])

        # variable values
        i = 0
        for store in aggregation_stores:
            for v in store.variables:
                if v.name == proto_agg_var.name:
                    dim = [d for d in v.dimensions if d.index == 0][0]
                    frm, to = i, i + dim.size
                    attrs = {attr.name: attr.value for attr in v.attrs}
                    values = collector.read_variable(store.name, proto_agg_var.name)

                    if "calendar" in attrs and "units" in attrs:
                        if ((attrs["calendar"] != proto_agg_var_attrs["calendar"]) or
                                (attrs["units"] != proto_agg_var_attrs["units"])):
                            values = convert_times(
                                values,
                                attrs["units"],
                                attrs["calendar"],
                                proto_agg_var_attrs["units"],
                                proto_agg_var_attrs["calendar"])

                    f[proto_agg_var.name][frm:to] = values

                    if "bounds" in proto_agg_var_attrs and "bounds" in attrs:
                        bounds = [v for v in store.variables if v.name == attrs["bounds"]][0]
                        values = collector.read_variable(store.name, bounds.name)
                        if "calendar" in attrs and "units" in attrs:
                            if ((attrs["calendar"] != proto_agg_var_attrs["calendar"]) or
                                    (attrs["units"] != proto_agg_var_attrs["units"])):
                                values = convert_times(
                                    values,
                                    attrs["units"],
                                    attrs["calendar"],
                                    proto_agg_var_attrs["units"],
                                    proto_agg_var_attrs["calendar"])

                        f[bounds.name][frm:to, ...] = values.reshape((-1, 2))

                    i = to

        # virtual variables
        for aggregation in aggregations:
            subset = [v.store
                      for s in sorted(stores, key=lambda x: x.name)
                      for v in s.variables if v.name == aggregation]
            for v in subset[0].variables:
                if v.name in f:
                    # ToDo: warning
                    continue

                if v.name not in aggregations and v.name != proto_agg_var.name:
                    attrs = {attr.name: attr.value for attr in v.attrs}
                    if "CLASS" in attrs and attrs["CLASS"] == "DIMENSION_SCALE":
                        if attrs["NAME"].startswith(NOT_A_VAR):
                            create_dimension(f, v.name, v.dimensions[0].size)
                        else:
                            create_virtual_variable(f, v)
                            f[v.name].make_scale(v.name)
                    else:
                        create_virtual_variable(f, v)

        for aggregation in aggregations:
            subset = [v.store
                      for s in sorted(stores, key=lambda x: x.name)
                      for v in s.variables if v.name == aggregation]
            proto = [v for v in subset[0].variables if v.name == aggregation][0]
            proto_dimensions = sorted(proto.dimensions, key=lambda x: x.index)
            shape = [join_existing_dim_size] + [d.size for d in proto_dimensions[1:]]

            layout = h5py.VirtualLayout(
                shape=tuple(shape),
                dtype=proto.dtype)

            i = 0
            for store in subset:
                current = [v for v in store.variables if v.name == aggregation][0]
                current_dimensions = sorted(current.dimensions, key=lambda x: x.index)

                vsource = h5py.VirtualSource(
                    store.name,
                    aggregation,
                    tuple([d.size for d in current_dimensions]))

                frm, to = i, i + current_dimensions[0].size
                layout[frm:to] = vsource
                i += int(current_dimensions[0].size)

            # ToDo: need to include fill_value
            f.create_virtual_dataset(aggregation, layout)
            attrs = collector.read_attributes(proto.store.name, proto.name)
            for attr in attrs:
                create_attr(f[aggregation], attr, attrs[attr])

            # Dimension scales
            f[aggregation].dims[0].attach_scale(f[proto_agg_var.name])
            for d in proto_dimensions[1:]:
                f[aggregation].dims[d.index].attach_scale(f[d.scales[0].name])

        # global attributes
        attrs = collector.read_attributes(proto_store.name)
        for attr in attrs:
            create_attr(f, attr, attrs[attr])

        f.close()


class NewCommon(Etl):
    def __init__(self, name, attrs, values):
        self.name = name
        self.attrs = attrs
        self.values = values

    def run(self, dest: str, collector: Collector, stores: list, aggregations: list[str]):
        f: h5py.File = h5py.File(dest, "w")

        # need to include only one ensemble from one "aggregation variable"
        aggregation_stores = [store
                              for store in sorted(stores, key=lambda x: x.name)
                              for v in store.variables
                              if ((v.name == aggregations[0]) and
                                  ({attr.name: attr.value for attr in store.attrs}[self.name] == self.values[0]))]
        proto_aggregation: Variable = [v
                                       for s in aggregation_stores
                                       for v in s.variables if v.name == aggregations[0]][0]

        proto_store: Store = proto_aggregation.store
        proto_dim: Dimension = [d for d in proto_aggregation.dimensions if d.index == 0][0]
        proto_agg_var: Variable = [v for v in proto_store.variables if v.name == proto_dim.scales[0].name][0]

        # assume aggregation dimension is always a coordinate variable
        join_existing_dim_size: int = int(
            sum([d.size
                 for s in aggregation_stores
                 for v in s.variables if v.name == aggregations[0]
                 for d in v.dimensions if d.index == 0]))

        # create the aggregation dimension
        f.create_dataset(
            proto_agg_var.name,
            (join_existing_dim_size,),
            proto_agg_var.dtype,
            chunks=True,
            compression="gzip",
            compression_opts=1,
            shuffle=True)
        f[proto_agg_var.name].make_scale(proto_agg_var.name)
        proto_agg_var_attrs = collector.read_attributes(proto_agg_var.store.name, proto_agg_var.name)
        for attr in proto_agg_var_attrs:
            create_attr(f[proto_agg_var.name], attr, proto_agg_var_attrs[attr])

        if "bounds" in proto_agg_var_attrs:
            create_dimension(f, "bnds", 2)
            f.create_dataset(
                proto_agg_var_attrs["bounds"],
                (join_existing_dim_size, 2),
                proto_agg_var.dtype,
                chunks=True,
                compression="gzip",
                compression_opts=1,
                shuffle=True)
            f[proto_agg_var_attrs["bounds"]].dims[0].attach_scale(f[proto_agg_var.name])
            f[proto_agg_var_attrs["bounds"]].dims[1].attach_scale(f["bnds"])

        # variable values
        i = 0
        for store in aggregation_stores:
            for v in store.variables:
                if v.name == proto_agg_var.name:
                    dim = [d for d in v.dimensions if d.index == 0][0]
                    frm, to = i, i + dim.size
                    attrs = {attr.name: attr.value for attr in v.attrs}
                    values = collector.read_variable(store.name, proto_agg_var.name)

                    if "calendar" in attrs and "units" in attrs:
                        if ((attrs["calendar"] != proto_agg_var_attrs["calendar"]) or
                                (attrs["units"] != proto_agg_var_attrs["units"])):
                            values = convert_times(
                                values,
                                attrs["units"],
                                attrs["calendar"],
                                proto_agg_var_attrs["units"],
                                proto_agg_var_attrs["calendar"])

                    f[proto_agg_var.name][frm:to] = values

                    if "bounds" in proto_agg_var_attrs and "bounds" in attrs:
                        bounds = [v for v in store.variables if v.name == attrs["bounds"]][0]
                        values = collector.read_variable(store.name, bounds.name)
                        if "calendar" in attrs and "units" in attrs:
                            if ((attrs["calendar"] != proto_agg_var_attrs["calendar"]) or
                                    (attrs["units"] != proto_agg_var_attrs["units"])):
                                values = convert_times(
                                    values,
                                    attrs["units"],
                                    attrs["calendar"],
                                    proto_agg_var_attrs["units"],
                                    proto_agg_var_attrs["calendar"])

                        f[bounds.name][frm:to, ...] = values.reshape((-1, 2))

                    i = to

        # virtual variables
        for store in stores:
            for v in store.variables:
                if v.name in f:
                    # ToDo: warning
                    continue

                if v.name not in aggregations and v.name != proto_agg_var.name:
                    attrs = {attr.name: attr.value for attr in v.attrs}
                    if "CLASS" in attrs and attrs["CLASS"] == "DIMENSION_SCALE":
                        if attrs["NAME"].startswith(NOT_A_VAR):
                            create_dimension(f, v.name, v.dimensions[0].size)
                        else:
                            create_virtual_variable(f, v)
                            f[v.name].make_scale(v.name)
                    else:
                        create_virtual_variable(f, v)

        f.create_dataset(
            self.name,
            (len(self.values),),
            dtype=h5py.string_dtype("utf-8", None),
            chunks=True,
            compression="gzip",
            compression_opts=1)
        f[self.name][:] = self.values
        f[self.name].make_scale(self.name)
        for attr in self.attrs:
            create_attr(f[self.name], attr, self.attrs[attr])

        for aggregation in aggregations:
            aggregation_subset = [store
                                  for store in sorted(stores, key=lambda x: x.name)
                                  for v in store.variables
                                  if v.name == aggregation]
            proto = [v for v in aggregation_subset[0].variables if v.name == aggregation][0]
            proto_dimensions = sorted(proto.dimensions, key=lambda x: x.index)

            layout = h5py.VirtualLayout(
                shape=tuple(
                    [len(self.values)] +
                    [join_existing_dim_size] +
                    [d.size for d in proto_dimensions[1:]]),
                dtype=proto.dtype)

            for ncoord, coord in enumerate(self.values):
                subset = [store
                          for store in aggregation_subset
                          if {attr.name: attr.value for attr in store.attrs}[self.name] == coord]
                proto = [v for v in subset[0].variables if v.name == aggregation][0]
                proto_dimensions = sorted(proto.dimensions, key=lambda x: x.index)

                i = 0
                for store in subset:
                    current = [v for v in store.variables if v.name == aggregation][0]
                    current_dimensions = sorted(current.dimensions, key=lambda x: x.index)

                    vsource = h5py.VirtualSource(
                        store.name,
                        aggregation,
                        tuple([d.size for d in current_dimensions]))

                    frm, to = i, i + current_dimensions[0].size
                    layout[ncoord, frm:to] = vsource
                    i += int(current_dimensions[0].size)

            # ToDo: need to include fill_value
            f.create_virtual_dataset(aggregation, layout)
            attrs = collector.read_attributes(proto.store.name, proto.name)
            for attr in attrs:
                create_attr(f[aggregation], attr, attrs[attr])

            # Dimension scales
            f[aggregation].dims[0].attach_scale(f[self.name])
            f[aggregation].dims[1].attach_scale(f[proto_agg_var.name])
            for d in proto_dimensions[1:]:
                f[aggregation].dims[d.index + 1].attach_scale(f[d.scales[0].name])

        # global attributes
        attrs = collector.read_attributes(proto_store.name)
        for attr in attrs:
            create_attr(f, attr, attrs[attr])

        f.close()
