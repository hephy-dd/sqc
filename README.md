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
python -m sqc
```

## Run Emulators

Run comet socket instrument emulators specified in `emulators.yaml` file.

```bash
python -m comet.emulators -f emulators.yaml
```
