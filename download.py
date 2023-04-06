#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""A script to 'automatize' the data request from AFAD TDVMS

Ridvan Orsvuran, 2023
"""

import tdvms
import utils
import argparse
import datetime
import os
import hashlib
import time


def check_cur_state(name, filehash):
    """Returns number of requested batches"""
    state_filename = f"{name}_state.yml"
    if os.path.isfile(state_filename):
        state = utils.load_yaml(state_filename)
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
    utils.dump_yaml(state_filename, {"hash": filehash, "requested": requested})


def _get_cached_values(use_cache, filename, download_func, *args, **kwargs):
    if use_cache and os.path.isfile(filename):
        return utils.load_json(filename)
    else:
        data = download_func(*args, **kwargs)
        utils.dump_json(filename, data)
        return data


def get_stations(networks, use_cache=True):
    return _get_cached_values(use_cache, "./stations.json",
                              tdvms.get_stations, networks)


def get_networks(use_cache=True):
    return _get_cached_values(use_cache, "./networks.json",
                              tdvms.get_networks)


class DownloadConfig:
    def __init__(self,
                 networks, selection,
                 starttime, endtime,
                 data_format, batch_size):
        self.networks = networks
        self.circle_selection = None
        self.rectangle_selection = None
        self.name_selection = None
        self.device_type_selection = None
        if isinstance(selection, dict):
            for sel_type, args in selection.items():
                if sel_type == "circle":
                    if not isinstance(args, dict):
                        raise Exception("Circle selection needs latitude, longitude, min_dist_km, and max_dist_km arguments.")  # NOQA
                    try:
                        self.circle_selection = (args["latitude"],
                                                 args["longitude"],
                                                 args["min_dist_km"],
                                                 args["max_dist_km"])
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
                elif sel_type == "device_type":
                    if not isinstance(args, list) or len(args) == 0:
                        raise Exception("Device type selection should be a list")  # NOQA
                    for d in args:
                        if d not in "HLN":
                            raise Exception(f"Unknown device type: {d}")
                    self.device_type_selection = args
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

    def validate_networks(self, use_cache=True):
        networks = get_networks(use_cache)
        network_codes = [net["code"] for net in networks]
        for net in self.networks:
            if net not in network_codes:
                raise Exception(f"Invalid network {net}")

    def select_stations(self, use_cache=True):
        self.validate_networks(use_cache)
        stations = get_stations([net["code"] for net in get_networks()],
                                use_cache)
        if self.circle_selection:
            stations = tdvms.filter_stations_by_circle(
                stations, *self.circle_selection)
        if self.rectangle_selection:
            stations = tdvms.filter_stations_by_rectangle(
                stations, *self.rectangle_selection)
        if self.name_selection:
            stations = tdvms.filter_stations_by_name(
                stations, self.name_selection)
        if self.device_type_selection:
            stations = tdvms.filter_stations_by_device_type(
                stations, self.device_type_selection)
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
    parser.add_argument("--plot", action="store_true",
                        help="Plot stations before downloading")
    parser.add_argument("--use-imap-email", metavar="creds.yml",
                        help="Use IMAP to check your e-mails.")
    parser.add_argument("--refresh-stations", action="store_true",
                        help="Download stations even if a local copy exists.")
    args = parser.parse_args()
    filename = args.filename
    config = DownloadConfig(**utils.load_yaml(filename))

    name = ".".join(args.filename.split("/")[-1].split(".")[:-1])
    # compute hash of the config file to detect possible changes
    with open(filename, "rb") as f:
        filehash = hashlib.sha256(f.read()).hexdigest()
    # check checkpoint file
    requested = check_cur_state(name, filehash)
    # fetch stations
    print("Constructing station list...")
    config.select_stations(not args.refresh_stations)
    # Print some info...
    n_batches = len(config.batches)
    print(f"Number of stations: {len(config.stations)}")
    print(f"Total batches: {n_batches}")
    print(f"Previously requested batches: {requested}, Remaining: {n_batches-requested}")  # NOQA
    update_state(name, requested, filehash)

    # Plot the stations?
    if args.plot:
        config.plot_stations()

    # Use IMAP E-mail checking?
    if args.use_imap_email is not None:
        imap_settings = utils.IMAPSettings(**utils.load_yaml(args.use_imap_email))
        use_imap_email = True
    else:
        use_imap_email = False

    while requested < n_batches:
        if not use_imap_email:
            print("")
            input("Press enter to request the next batch! ")
            print("")
        print("Requesting...")
        try:
            config.download(requested, args.email)
            requested += 1
            update_state(name, requested, filehash)
            if use_imap_email:
                utils.check_imap_email(imap_settings)
        except tdvms.TDVMSException as e:
            print("ERROR occured:", e)
            print("Waiting for a minute.")
            time.sleep(60)
