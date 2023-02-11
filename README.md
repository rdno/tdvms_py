# A client for downloading continous data from AFAD TDVMS

Python function for downloading data from [AFAD TDVMS](https://tdvms.afad.gov.tr/continuous_data).

You can find an example usage in `example.py`.

## Notes

There seems to be a server side limitation to requests. You might want
to request only 50 stations at a time. You can submit another request
after you get the data via e-mail.
