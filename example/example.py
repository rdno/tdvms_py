#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import tdvms
import matplotlib.pyplot as plt

networks = tdvms.get_networks()
with open("networks.json", "w") as f:
    json.dump(networks, f, sort_keys=True, indent=2)


# with open("./networks.json") as f:
#     networks = json.load(f)

# get all network codes
network_codes = [net["code"] for net in networks]

stations = tdvms.get_stations(network_codes)
with open("stations.json", "w") as f:
    json.dump(stations, f, sort_keys=True, indent=2)

# with open("./stations.json") as f:
    # stations = json.load(f)

fig, ax = tdvms.plot_stations(stations, show=False)
ax.set_title("All Stations")

# You can either get stations only using their code or
#  fetch them all and filter them after

# use only TK stations
stations = [sta for sta in stations if sta["network"] == "TK"]
fig, ax = tdvms.plot_stations(stations, show=False)
ax.set_title("TK Stations")


origin_latitude = 37.5600
origin_longitude = 37.4700

stations = tdvms.filter_stations_by_circle(
    stations, origin_latitude, origin_longitude,
    min_dist_km=0, max_dist_km=200)
fig, ax = tdvms.plot_stations(stations, show=False)
ax.set_title("Stations after distance filtering")

# stations = tdvms.filter_stations_by_rectangle(
#     stations, 39.8183, 34.7887, 37.49619, 43.857630)
# fig, ax = tdvms.plot_stations(stations, show=False)
# ax.set_title("Stations after rectangle filtering")


# stations = tdvms.filter_stations_by_name(stations, ["TK.2308", "TK.4412", "TK.4631"])
# fig, ax = tdvms.plot_stations(stations, show=False)
# ax.set_title("Stations after name filtering")

batches = tdvms.split_into_batches(stations, batch_size=50)

for i, batch in enumerate(batches, 1):
    fig, ax = tdvms.plot_stations(batch, show=False)
    ax.set_title(f"Batch {i}")


plt.show()
email = "you@email.com"; raise Exception("Define your e-mail here.")
tdvms.request_data(batches[0], "2023-2-6 1:17:11", "2023-2-6 1:57:11",
                   "mseed", email=email)
