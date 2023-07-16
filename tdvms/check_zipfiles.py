#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
from pathlib import Path
from zipfile import ZipFile

from . import download
from . import utils


def check_zipfiles(config_filename, zip_folder, *,
                   print_missing_stations=False,
                   write_missing_batches=False):
    config = download.DownloadConfig(**utils.load_yaml(config_filename))
    config.select_stations()
    batch_filenames = []
    for batch, df,  start, end in zip(config.batches,
                                      config.batch_data_formats,
                                      config.batch_starttimes,
                                      config.batch_endtimes):
        filenames = set()
        if df != "inventory":
            for sta in batch:
                device_type = None
                # TODO: Guess the deviceCode correctly, HH, BH, HN, EH, etc.
                for d in "HLN":
                    if sta[f"device{d}"]:
                        device_type = d
                        break
                if device_type is None:
                    raise Exception(f"Device type couldn't be found for {sta}")
                filenames.add(
                    f"{sta['network']}_{sta['code']}_{start:%d%m%Y_%H%M%S}_{end:%d%m%Y_%H%M%S}_H{device_type}.{df}")  # NOQA: E501
        else:
            raise NotImplementedError("StationXML checking is not implemented yet!")
        batch_filenames.append(filenames)

    zipfiles = set(sorted(zip_folder.glob("*.zip")))

    all_in_zip_filenames = {}
    for zip_filename in zipfiles:
        with ZipFile(zip_filename) as zf:
            all_in_zip_filenames[zip_filename] = set(zf.namelist())

    missing = []
    for i, filenames in enumerate(batch_filenames):
        zip_found = False
        for zip_filename, in_zip_filenames in all_in_zip_filenames.items():
            intersection = in_zip_filenames.intersection(filenames)
            if len(intersection) > 0:
                print(f"batch {i:3d} -> {zip_filename}")
                if print_missing_stations:
                    diff = filenames.difference(in_zip_filenames)
                    if len(diff) > 0:
                        print("  Missing Data:")
                        for d in diff:
                            print(f"    {d}")
                zip_found = zip_filename
                break
        if not zip_found:
            print(f"batch {i:3d} -> zip file couldn't be found.")
            missing.append(i)
        else:
            del all_in_zip_filenames[zip_found]

    if len(all_in_zip_filenames) > 0:
        print("Odd zip files:")
        for z in all_in_zip_filenames.keys():
            print(f"  {z}")

    print(f"Missing data for {len(missing)} batches.")
    if write_missing_batches:
        for i, m in enumerate(missing):
            stations = [f"{s['network']}.{s['code']}"
                        for s in config.batches[m]]
            data = {
                "batch_size": config.batch_size,
                "data_format": config.batch_data_formats[m],
                "starttime": config.batch_starttimes[m],
                "endtime": config.batch_endtimes[m],
                "networks": ["GZ", "KO", "TB", "TK", "TU"],
                "selection": {
                    "name": stations
                }
            }
            out_filename = f"{config_filename.stem}_missing_{i}.yml"
            print(f"Writing out config file for missing data {out_filename}")
            utils.dump_yaml(out_filename, data)


def check_zipfiles_command():
    parser = argparse.ArgumentParser(
        description="Check downloaded zip files for missing data")
    parser.add_argument("config_filename", help="Download config file")
    parser.add_argument("zip_folder",
                        help="Folder that contains the zip files")
    parser.add_argument("-p", "--print-missing-stations",
                        action="store_true",
                        help="print missing stations in the zip files")
    parser.add_argument("-w", "--write-missing-batches",
                        action="store_true",
                        help="Write out download config files for missing batches")  # NOQA: E501
    args = parser.parse_args()
    check_zipfiles(Path(args.config_filename), Path(args.zip_folder),
                   print_missing_stations=args.print_missing_stations,
                   write_missing_batches=args.write_missing_batches)


if __name__ == "__main__":
    check_zipfiles_command()
