#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""AFAD TDVMS Continuous data client
https://tdvms.afad.gov.tr/continuous_data

Ridvan Orsvuran, 2023
"""

import datetime
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


class TDVMSException(Exception):
    pass


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
        stations = json.loads(r.content.decode())
        return expand_hybrid_stations(stations)
    else:
        raise Exception(f"Fetching stations failed with status code: {r.status_code}")  # NOQA


def expand_hybrid_stations(stations):
    """To request data multiple data type from hybrid stations, you
    need to act like they are different stations. This function
    expands the hybrid stations into their device_type counter parts.
    """
    devices = ["deviceH", "deviceL", "deviceN"]
    new_stations = []
    for sta in stations:
        number_of_device_types = sum(int(sta[d]) for d in devices)
        if number_of_device_types > 1:
            no_device_sta = sta.copy()
            for device in devices:
                no_device_sta[device] = False
                for c in "ZEN":
                    no_device_sta[device+c] = False

            for device in devices:
                if sta[device]:
                    new_sta = no_device_sta.copy()
                    new_sta[device] = True
                    for c in "ZEN":
                        new_sta[device+c] = True
                    new_stations.append(new_sta)
        else:
            new_stations.append(sta)
    return new_stations


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


def filter_stations_by_network(stations, networks):
    """Filter stations by network"""
    new_stations = []
    for sta in stations:
        if sta["network"] in networks:
            new_stations.append(sta)

    return new_stations


def filter_stations_by_circle(stations, origin_latitude, origin_longitude,
                              min_dist_km, max_dist_km):
    """Filter stations in a circle defined by
    an origin point, mininum and maximum distances"""
    new_stations = []
    for sta in stations:
        sta_dist_m, _, _ = calc_vincenty_inverse(
            origin_latitude, origin_longitude,
            sta["latitude"], sta["longitude"])
        sta_dist_km = sta_dist_m / 1000.0
        if min_dist_km <= sta_dist_km <= max_dist_km:
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


def filter_stations_by_name(stations, selected_station_names):
    """Filter stations based on the stations names
    Station names should be `network.station_code` (e.g., TK.3126, KO.DKL)
    """
    if not isinstance(selected_station_names, list):
        selected_station_names = [selected_station_names]

    new_stations = []
    for sta in stations:
        full_name = f"{sta['network']}.{sta['code']}"
        if full_name in selected_station_names:
            new_stations.append(sta)
    return new_stations


def filter_stations_by_device_type(stations, device_codes):
    """Filter station by device type:

    H => High Gain Seismometer
    L => Low Gain Seismometer
    N => Accelerometer
    """
    if not isinstance(device_codes, list):
        device_codes = [device_codes]

    new_stations = []
    for sta in stations:
        for code in device_codes:
            if sta["device"+code]:
                new_stations.append(sta)
    return new_stations


def split_into_batches(stations, batch_size=50):
    """Split the stations into batches to request the data by parts"""
    total_length = len(stations)
    n = total_length // batch_size + 1
    k, m = divmod(total_length, n)
    return [stations[i * k + min(i, m):(i + 1) * k + min(i + 1, m)]
            for i in range(n)]


def request_data(stations, starttime, endtime, data_type, email, timeout=None):
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

    if isinstance(starttime, datetime.datetime):
        starttime = starttime.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(endtime, datetime.datetime):
        endtime = endtime.strftime("%Y-%m-%d %H:%M:%S")

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

    try:
        r = requests.post("https://tdvmservis.afad.gov.tr/GetData",
                          json=data, timeout=timeout)
    except requests.exceptions.Timeout:
        print("Request timed out!")
        return
    except requests.exceptions.ConnectionError:
        raise TDVMSException("Connection Aborted!")

    if r.status_code == 200:
        # print("Response:")
        # print(r.content)
        data = json.loads(r.content.decode())
        if data["Result"] == 111:
            raise TDVMSException("You might need to wait for your previous request!")  # NOQA
        elif data["Result"] == 110:
            raise TDVMSException("General Error")
        else:
            print("Data request successful! You might get an e-mail soon.")
    else:
        raise TDVMSException(f"Data request failed with status code: {r.status_code}")  # NOQA
