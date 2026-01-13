#!/usr/bin/env python3

import argparse
import json
import re
import sys

import pandas as pd
import requests
from natsort import natsort_keygen

INDEX_NODES = (
    "esgf-node.llnl.gov",
    "esgf-data.dkrz.de",
    "esgf.nci.org.au",
    "esg-dn1.nsc.liu.se",
    "esgf-index1.ceda.ac.uk",
    "esgf-node.ipsl.upmc.fr",
)


def parse_selection(sfile):
    query = {}
    with open(sfile, "r") as f:
        for line in f:
            if line == "\n" and query:
                yield query
                query = {}
            elif line != "\n":
                params = line.rstrip("\n").split()
                for param in params:
                    k = param.split("=")[0]
                    v = param.split("=")[1]
                    query[k] = v

        if query:
            yield query


def parse_query(query):
    queryd = {}
    params = query.replace("\n", " ").split()
    for param in params:
        k = param.split("=")[0]
        v = param.split("=")[1]
        queryd[k] = v

    return queryd


def range_search(endpoint, session, query, stop=None):
    payload = query.copy()

    # how many records?
    payload["limit"] = 0
    payload["format"] = "application/solr+json"
    r = session.get(endpoint, params=payload, timeout=120)
    print("Query results for {}".format(r.url), file=sys.stderr)
    n = r.json()["response"]["numFound"]
    print("Found {} for {}".format(n, r.url), file=sys.stderr)

    # if stop < n, restrict
    if stop is not None and stop < n:
        n = stop

    # small optimization
    limit = 9000  # theoretically it is 10_000 but sometimes it fails
    if n < limit:
        limit = n

    # clean payload and start searching
    payload = query.copy()
    i = 0
    while i < n:
        payload["limit"] = limit
        payload["format"] = "application/solr+json"
        payload["offset"] = i

        r = session.get(endpoint, params=payload, timeout=120)
        print(r.url, file=sys.stderr)
        docs = r.json()["response"]["docs"]
        for f in docs:
            i += 1
            yield f

            if i >= n:
                break


def standard_search(query, stop, index):
    s = requests.Session()
    endpoint = "https://{}/esg-search/search".format(index)
    if index == "esgf-ui.ceda.ac.uk":
        endpoint = "https://{}/proxy/search".format(index)
    for result in range_search(endpoint, s, query, stop):
        yield result
    s.close()


def nondistrib_search(query, stop):
    for index_node in INDEX_NODES:
        s = requests.Session()
        params = query.copy()
        params["distrib"] = "false"
        endpoint = "https://{}/esg-search/search".format(index_node)

        for result in range_search(endpoint, s, params, stop):
            yield result

        s.close()


def fix_result(result):
    new = dict()
    keys = result.keys()

    for k in keys:
        if k == "url":
            new[k] = result[k]
        elif isinstance(result[k], list):
            new[k] = result[k][0]
        elif isinstance(result[k], str) or isinstance(result[k], float) or isinstance(result[k], int):
            new[k] = result[k]
        else:
            new[k] = str(result[k])

    return new


class Formatter():
    def dump(self, item):
        print(json.dumps(item))

    def terminate(self):
        pass

    def fix_instance_id(self, item):
        title = item["title"]
        title = re.sub(r"\.nc_[0-9]+$", ".nc", title)
        title = re.sub(r"\.nc[0-9]+$", ".nc", title)
        instance_id = item["instance_id"]
        instance_id = re.sub(r"\.nc_[0-9]+$", ".nc", instance_id)
        instance_id = re.sub(r"\.nc[0-9]+$", ".nc", instance_id)
        if not title in instance_id:
            instance_id = ".".join([instance_id, title])

        # fuck cordex
        # if instance_id.split(".")[0].lower() == "cordex":
        #    parts = instance_id.split(".")
        #    parts[7] = "-".join([parts[3], parts[7]])
        #    instance_id = ".".join(parts)

        return instance_id


class Aria2cFormatter(Formatter):
    def __init__(self):
        self.store = {}

    def dump(self, item):
        instance_id = self.fix_instance_id(item)

        urls = filter(lambda x: x.endswith("HTTPServer"), item["url"])
        urls = [url.split("|")[0] for url in urls]

        checksum = ""
        checksum_type = ""
        if "checksum" in item and "checksum_type" in item:
            checksum = item["checksum"]
            checksum_type = item["checksum_type"].replace("SHA", "sha-").replace("MD5", "md5")

        if instance_id in self.store:
            self.store[instance_id]["urls"].extend(urls)
        else:
            self.store[instance_id] = {
                "urls": urls,
                "checksum": checksum,
                "checksum_type": checksum_type,
                "out": re.sub(r"\.nc$", "", instance_id).replace(".", "/") + ".nc"
            }

    def terminate(self):
        for instance_id in self.store:
            print("\t".join(self.store[instance_id]["urls"]))
            print("  checksum={}={}".format(
                self.store[instance_id]["checksum_type"],
                self.store[instance_id]["checksum"]))
            print("  out={}".format(self.store[instance_id]["out"]))


class Metalink4Formatter(Aria2cFormatter):
    def __init__(self):
        self.store = {}

    def terminate(self):
        print('<?xml version="1.0" encoding="UTF-8"?>')
        print('<metalink xmlns="urn:ietf:params:xml:ns:metalink">')
        for instance_id in self.store:
            print('  <file name="{}">'.format(self.store[instance_id]["out"]))
            print('    <hash type="{}">{}</hash>'.format(
                self.store[instance_id]["checksum_type"],
                self.store[instance_id]["checksum"]))
            for url in self.store[instance_id]["urls"]:
                print('    <url priority="1">{}</url>'.format(url))
            print('  </file>')
        print('</metalink>')


class Metalink4fFormatter(Aria2cFormatter):
    def __init__(self):
        self.store = {}

    def terminate(self):
        print('<?xml version="1.0" encoding="UTF-8"?>')
        print('<metalink xmlns="urn:ietf:params:xml:ns:metalink">')
        for instance_id in self.store:
            basename = self.store[instance_id]["out"].split("/")[-1]
            print('  <file name="{}">'.format(basename))
            print('    <hash type="{}">{}</hash>'.format(
                self.store[instance_id]["checksum_type"],
                self.store[instance_id]["checksum"]))
            for url in self.store[instance_id]["urls"]:
                print('    <url priority="1">{}</url>'.format(url))
            print('  </file>')
        print('</metalink>')


class Project():
    # Note that this also removes old versions
    def first_run(self, df):
        fcts = self.facets()
        fcts.remove(self.run_facet())
        ascending = [True] * len(fcts)

        # get the first member for each group
        first_members = (
            df[self.facets()]
            .sort_values(by=self.facets(), key=natsort_keygen())
            .drop_duplicates(fcts, keep="first"))

        # now merge with the original df to get the files for each "first member"
        first_members = first_members.merge(
            df,
            how="inner",
            on=self.facets())

        return first_members

    def facets(self):
        raise NotImplementedError

    def run_facet(self):
        raise NotImplementedError


class Cmip6(Project):
    def facets(self):
        return [
            "mip_era",
            "activity_id",
            "institution_id",
            "source_id",
            "experiment_id",
            "variant_label",
            "table_id",
            "variable_id",
            "grid_label",
        ].copy()

    def run_facet(self):
        return "variant_label"


class Cordex(Project):
    def facets(self):
        # "product" is excluded because it doesn't exist sometimes
        return [
            "project",
            "product",
            "domain",
            "driving_model",
            "experiment",
            "time_frequency",
            "ensemble",
            "rcm_name",
            "rcm_version",
            "variable"
        ].copy()

    def run_facet(self):
        return "ensemble"


class Cmip5(Project):
    def facets(self):
        return [
            "project",
            "product",
            "model",
            "experiment",
            "time_frequency",
            "cmor_table",
            "ensemble",
            "variable"
        ].copy()

    def run_facet(self):
        return "ensemble"


if __name__ == "__main__":
    # arguments
    parser = argparse.ArgumentParser(description="ESGF search utility.")
    parser.add_argument("--format",
                        type=str,
                        nargs="?",
                        default="json",
                        help="output file format.")
    parser.add_argument("--from",
                        type=str,
                        nargs="?",
                        default=None,
                        help="use an existing input file.")
    parser.add_argument("-i", "--index-node",
                        type=str,
                        nargs="?",
                        default="esgf-ui.ceda.ac.uk",
                        help="domain of the index node to query.")
    parser.add_argument("-q", "--query",
                        type=str,
                        nargs="?",
                        default=None,
                        help="inline query (eg: type=File project=CMIP6 variable_id=tas).")
    parser.add_argument("--local",
                        action="store_true",
                        help="query all ESGF nodes using distrib=False.")
    parser.add_argument("--stop",
                        type=int,
                        default=None,
                        help="retrieve limited number of items.")
    parser.add_argument("--first-run",
                        type=str,
                        default=None,
                        help="ESGF project (Cmip6, Cmip5, Cordex).")
    parser.add_argument("selections",
                        type=str,
                        nargs="*",
                        default=list(),
                        help="selection files.")
    args = vars(parser.parse_args())

    if args["format"] == "json":
        formatter = Formatter()
    elif args["format"] == "aria2c":
        formatter = Aria2cFormatter()
    elif args["format"] == "meta4":
        formatter = Metalink4Formatter()
    elif args["format"] == "meta4f":
        formatter = Metalink4fFormatter()
    else:
        print("Error: Unknown format '{}', exiting...".format(args["format"]), file=sys.stderr)
        sys.exit(1)

    # just convert and exit
    if args["from"] is not None:
        if args["first_run"]:
            project: Project = globals()[args["first_run"]]()
            df = pd.read_json(args["from"], lines=True)
            df = project.first_run(df)
            df.to_json(sys.stdout, orient="records", lines=True)
        else:
            with open(args["from"], "r") as f:
                for result in f:
                    formatter.dump(json.loads(result))

            # for formatters that store in memory
            formatter.terminate()
        sys.exit(0)

    # search query
    if args["query"]:
        if args["local"]:
            for result in nondistrib_search(parse_query(args["query"]), args["stop"]):
                formatter.dump(fix_result(result))
        else:
            for result in standard_search(parse_query(args["query"]), args["stop"], args["index_node"]):
                formatter.dump(fix_result(result))

    # search selections
    for selection in args["selections"]:
        for query in parse_selection(selection):
            if args["local"]:
                for result in nondistrib_search(query, args["stop"]):
                    formatter.dump(fix_result(result))
            else:
                for result in standard_search(query, args["stop"], args["index_node"]):
                    formatter.dump(fix_result(result))

    # for formatters that store in memory
    formatter.terminate()
