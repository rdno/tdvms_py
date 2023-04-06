# A client for downloading continuous data from AFAD TDVMS

Python scripts for downloading data from [AFAD TDVMS](https://tdvms.afad.gov.tr/continuous_data).

You can find an example usage in `example.py`.

## Install required packages

```console
$ pip install -r requirements.txt
```

## Download Script (`download.py`)

Download script attempts to ease the data request stage. Uses
configuration file and keeps track of the progress. Example
configuration file (`maras.yml`) requests 40 minutes seismograms from
TK network stations within the 200 km of the epicenter.

Usage:

```console
$ ./download.py config_file.yml me@university.edu
```

To avoid the possible bans, data requests are manual. Pressing enter
submits the request. After you get the e-mail with the link, you can
press enter again to submit the next request.

Number of requested batches are recorded in the `*_state.yml` for every config file.


### Configuration file


`starttime` and `endtime` format: `YYYY-MM-DD HH:MM:SS`

`data_format`: `mseed`, `fseed`, `inventory`. Multiple format can be selected using comma as a separator (e.g. "mseed,inventory").

`networks`: networks codes (`TK`, `KO`, etc.)
All networks can be selected like this:

```yaml
networks:
 - "GZ"
 - "KO"
 - "TB"
 - "TK"
 - "TU"
```

`selection`: can be one or multiple of `circle`,`rectangle`, `name`, and `device_type`.

Examples:
```yaml
selection:
  circle:
    latitude: 37.224
    longitude: 37.4700
    min_dist_km: 0
    max_dist_km: 200
```

```yaml
selection:
  rectangle:
    north_latitude: 39.8183
    west_longitude: 34.7887
    south_latitude: 37.4961
    east_longitude: 43.8576
```

```yaml
selection:
  name:
    - "TK.3140"
    - "TK.3141"
    - "TK.3143"
```

```yaml
selection:
  device_type:
    - "H"
    - "L"
    - "N"
```

`batch_size`: number of station to request at once. 50 is recommended.


### Auto download from the e-mail

You can also use `IMAP` to check your e-mail and download the linked
zip file automatically using `utils.check_imap_email` function.

`download.py` can also take a yaml file which includes the login credentials.

Example:
```yaml
imap_url: "imap.university.edu"
username: "me@university.edu"
password: "mysecretpassword"
```

If you are using Gmail you might need to create `App Password`
password. More info [here](https://support.google.com/accounts/answer/185833).


## Notes

There seems to be a server side limitation to requests. You might want
to request only 50 stations at a time. You can submit another request
after you get the data via e-mail.
