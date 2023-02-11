#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""AFAD TDVMS Continuous data client
https://tdvms.afad.gov.tr/continuous_data

Ridvan Orsvuran, 2023
"""

import json
import requests

import matplotlib.pyplot as plt
try:
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature
except ImportError:
    import warnings
    warnings.warn("cartopy is not installed, plot functions might not work!")


from obspy.geodetics import calc_vincenty_inverse


data_types = ("mseed", "fseed", "inventory")


def get_networks():
    """Returns a list of networks with their `code` name and `description`"""
    r = requests.get("https://tdvms.afad.gov.tr/api/Data/GetNetworks")
    if r.status_code == 200:
        return json.loads(r.content.decode())
    else:
        raise Exception(f"Fetching networks failed with status code: {r.status_code}")  # NOQA


def get_stations(networks):
    """Returns a list of stations based on list of network codes"""
    r = requests.post("https://tdvms.afad.gov.tr/api/Data/GetStations",
                      json={"netcodes": networks, "deviceCode": "",
                            "component": ""})

    if r.status_code == 200:
        return json.loads(r.content.decode())
    else:
        raise Exception(f"Fetching stations failed with status code: {r.status_code}")  # NOQA


def plot_stations(stations, fig=None, ax=None,
                  point_size=100, marker="v",
                  color="blue",
                  show=None,
                  **plot_args):
    """Plot stations"""
    if fig is None or ax is None:
        fig, ax = plt.subplots(subplot_kw={"projection": ccrs.PlateCarree()})
        if show is None:
            show = True
        ax.coastlines()
        ax.add_feature(cfeature.BORDERS)
        ax.set_extent([25, 45, 34, 43])

    lons = [sta["longitude"] for sta in stations]
    lats = [sta["latitude"] for sta in stations]
    ax.scatter(lons, lats, point_size, marker=marker, color=color,
               **plot_args)

    if show:
        plt.show()
    return fig, ax


def filter_stations_by_distance(stations, origin_latitude, origin_longitude,
                                dist_km):
    """Filter stations in a circle defined by
    an origin point and maximum distance (km)"""
    new_stations = []
    for sta in stations:
        sta_dist_m, _, _ = calc_vincenty_inverse(
            origin_latitude, origin_longitude,
            sta["latitude"], sta["longitude"])
        sta_dist_km = sta_dist_m / 1000.0
        if sta_dist_km <= dist_km:
            new_stations.append(sta)

    return new_stations


def filter_stations_by_rectangle(stations, north_latitude, west_longitude,
                                 south_latitude, east_longitude):
    """Filter stations based on a rectangle which is defined by
    its North-West and South-East points
    """
    new_stations = []
    for sta in stations:
        if west_longitude <= sta["longitude"] <= east_longitude:
            if south_latitude <= sta["latitude"] <= north_latitude:
                new_stations.append(sta)
    return new_stations


def split_into_batches(stations, batch_size=50):
    """Split the stations into batches to request the data by parts"""
    total_length = len(stations)
    n = total_length // 50 + 1
    k, m = divmod(total_length, n)
    return [stations[i * k + min(i, m):(i + 1) * k + min(i + 1, m)]
            for i in range(n)]


def request_data(stations, starttime, endtime, data_type, email):
    """Request data by e-mail

    time format %Y-%m-%d %H:%M:%S
    data_types: ("mseed", "fseed", "inventory")
    """

    networks = [sta["network"] for sta in stations]
    station_names = [sta["code"] for sta in stations]
    locations = [None for sta in stations]
    device_codes = []
    for sta in stations:
        code = ""
        if sta["deviceH"]:
            code = "H"
        elif sta["deviceL"]:
            code = "L"
        elif sta["deviceN"]:
            code = "N"
        else:
            raise Exception(f"Device type couldn't be figured out for {sta['code']}")  # NOQA
        device_codes.append(code)
    components = [["Z", "N", "E"] for sta in stations]
    if data_type not in data_types:
        raise Exception(f"data_type should one of {data_types}.")

    data = {"start_time": starttime,
            "end_time":  endtime,
            "data_type": data_type,
            "instrument": data_type == "inventory",
            "networks": networks,
            "stations": station_names,
            "location": locations,
            "device_codes": device_codes,
            "components": components,
            "e_mail": email}

    r = requests.post("https://tdvmservis.afad.gov.tr/GetData",
                      json=data)

    if r.status_code == 200:
        print("Response:")
        print(r.content)
        data = json.loads(r.content.decode())
        if data["Result"] == 111:
            raise Exception("You might need to wait for your previous request!")  # NOQA
        elif data["Result"] == 110:
            raise Exception("General Error")
        else:
            print("You might get an e-mail soon.")
    else:
        raise Exception(f"Data request failed with status code: {r.status_code}")  # NOQA
