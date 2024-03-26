# SQC

Sensor Quality Control for the CMS Tracker

![SQC switching scheme](docs/assets/sqc_switching_scheme_v3.0b.png)

## Install

Install SQC from from GitHub.

```bash
pip install git+https://github.com/hephy-dd/sqc.git@main
```

## Run SQC

```bash
sqc
```

## Run Data Browser

To run only the data browser use the `--browser [<path>]` command line flag.

```bash
sqc --browser
```

The command line flag accepts an optional path to show in the data browser.

```bash
sqc --browser /home/jdoe/sqc
```

## Run Emulators

Run comet socket instrument emulators specified in `emulators.yaml` file.

```bash
python -m comet.emulators -f emulators.yaml
```

## License

SQC is licensed under the [GNU General Public License Version 3](LICENSE).
