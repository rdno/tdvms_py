#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""A script to 'automatize' the data request from AFAD TDVMS

Ridvan Orsvuran, 2023
"""

import tdvms
import yaml
import argparse
import datetime
import os
import hashlib


def check_cur_state(name, filehash):
    """Returns number of requested batches"""
    state_filename = f"{name}_state.yml"
    if os.path.isfile(state_filename):
        with open(state_filename) as f:
            state = yaml.safe_load(f)

        # If config file changed, you might want to reset?
        if state["hash"] != filehash:
            ans = input("Config file seem to be changed! Do you want to reset the state? [y/n] ")  # NOQA
            if ans == "y":
                return 0
            else:
                print("Exiting...")
                exit(0)
        else:  # there is a save state, we ran with this config before.
            return state["requested"]
    else:
        return 0   # first run


def update_state(name, requested, filehash):
    state_filename = f"{name}_state.yml"
    with open(state_filename, "w") as f:
        yaml.safe_dump({"hash": filehash, "requested": requested}, f)


class DownloadConfig:
    def __init__(self,
                 networks, selection,
                 starttime, endtime,
                 data_format, batch_size):
        self.networks = networks
        self.circle_selection = None
        self.rectangle_selection = None
        self.name_selection = None
        if isinstance(selection, dict):
            for sel_type, args in selection.items():
                if sel_type == "circle":
                    if not isinstance(args, dict):
                        raise Exception("Circle selection needs latitude, longitude and dist_km arguments.")  # NOQA
                    try:
                        self.circle_selection = (args["latitude"],
                                                 args["longitude"],
                                                 args["dist_km"])
                    except KeyError as e:
                        raise Exception(f"Circle selection needs argument: {e}")  # NOQA
                elif sel_type == "rectangle":
                    if not isinstance(args, dict):
                        raise Exception("Rectangle selection needs latitude and longitude arguments.")  # NOQA
                    try:

                        self.rectangle_selection = (args["north_latitude"],
                                                    args["west_longitude"],
                                                    args["south_latitude"],
                                                    args["east_longitude"])
                    except KeyError as e:
                        raise Exception(f"Rectangle selection needs argument: {e}")  # NOQA
                elif sel_type == "name":
                    if not isinstance(args, list) or len(args) == 0:
                        raise Exception("Name selection should be a list of names")  # NOQA
                    self.name_selection = args
                else:
                    raise Exception(f"Unknown selection type: {sel_type}")
            self.selection = selection
        else:
            raise Exception("Malformed selection argument!")

        if not isinstance(starttime, datetime.datetime):
            raise Exception(f"starttime couldn't be parsed as date: {starttime}")  # NOQA
        if not isinstance(endtime, datetime.datetime):
            raise Exception(f"endtime couldn't be parsed as date: {endtime}")
        self.starttime = starttime
        self.endtime = endtime

        if isinstance(data_format, str):
            data_format = data_format.split(",")

        if isinstance(data_format, list):
            for f in data_format:
                if f not in tdvms.data_types:
                    raise Exception(f"Unrecognized data format: {f}")

            self.data_format = data_format
        else:
            raise Exception(f"Unrecognized data format: {data_format}")

        if isinstance(batch_size, int):
            self.batch_size = batch_size
        else:
            raise Exception(f"Batch size should be an integer: {batch_size}")

    def validate_networks(self):
        networks = tdvms.get_networks()
        network_codes = [net["code"] for net in networks]
        for net in self.networks:
            if net not in network_codes:
                raise Exception(f"Invalid network {net}")

    def select_stations(self):
        self.validate_networks()
        stations = tdvms.get_stations(self.networks)
        if self.circle_selection:
            stations = tdvms.filter_stations_by_distance(
                stations, *self.circle_selection)
        if self.rectangle_selection:
            stations = tdvms.filter_stations_by_rectangle(
                stations, *self.rectangle_selection)
        if self.name_selection:
            stations = tdvms.filter_stations_by_name(
                stations, self.name_selection)
        self.stations = stations
        batches = tdvms.split_into_batches(self.stations,
                                           self.batch_size)
        n_batches = len(batches)
        self.batch_data_formats = []
        self.batches = []
        for f in self.data_format:
            self.batch_data_formats.extend([f]*n_batches)
            self.batches.extend(batches)

    def plot_stations(self, *args, **kwargs):
        tdvms.plot_stations(self.stations, *args, **kwargs)

    def download(self, batch_id, email):
        tdvms.request_data(self.batches[batch_id],
                           str(self.starttime), str(self.endtime),
                           self.batch_data_formats[batch_id], email=email)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download data")
    parser.add_argument("filename", help="config file")
    parser.add_argument("email", help="email address")
    args = parser.parse_args()
    filename = args.filename
    with open(filename) as f:
        config = DownloadConfig(**yaml.safe_load(f))

    name = ".".join(args.filename.split("/")[-1].split(".")[:-1])
    # compute hash of the config file to detect possible changes
    with open(filename, "rb") as f:
        filehash = hashlib.sha256(f.read()).hexdigest()
    # check checkpoint file
    requested = check_cur_state(name, filehash)
    # fetch stations
    print("Downloading station list...")
    config.select_stations()
    # Print some info...
    n_batches = len(config.batches)
    print(f"Number of stations: {len(config.stations)}")
    print(f"Total batches: {n_batches}")
    print(f"Previously requested batches: {requested}, Remaining: {n_batches-requested}")  # NOQA
    # Plot the stations?
    should_plot = input("Plot Stations? [y/n] ")
    if should_plot == "y":
        config.plot_stations()

    while requested < n_batches:
        print("")
        input("Press enter to request the next batch! ")
        print("")
        print("Requesting...")
        config.download(requested, args.email)
        requested += 1
        update_state(name, requested, filehash)
