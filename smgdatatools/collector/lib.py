import re


class Collector:
    def __init__(self, drs=None):
        self.drs = drs

    def collect(self, resources):
        raise NotImplementedError

    def read_variable(self, store, variable):
        raise NotImplementedError

    def read_attributes(self, store, obj=None):
        raise NotImplementedError

    def parse_drs(self, name):
        drs = dict()
        if self.drs:
            p = re.compile(self.drs)
            matches = p.search(name)
            drs = matches.groupdict()

        return drs

    def ignored_attrs(self):
        return (
            "REFERENCE_LIST",
            # "CLASS",
            "DIMENSION_LIST",
            # "NAME",
            # "_Netcdf4Dimid",
            # "_Netcdf4Coordinates",
            # "_nc3_strict",
            # "_NCProperties",
        )
