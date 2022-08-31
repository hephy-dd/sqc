---
layout: default
title: CV
parent: Measurements
nav_order: 20
---

# CV

CV ramp using Bias SMU and LCR for measurements.

Measurement type: `cv`

Instruments: `Bias SMU`, `LCR Meter`

## Parameters

| Parameter                | Type    | Default | Description |
|--------------------------|---------|---------|-------------|
|`hv_channels`             |`list`   |`[]`     |             |
|`voltage_begin`           |`volt`   |`0 V`    |Start voltage (`-1000 V` to `0 V`). |
|`voltage_end`             |`volt`   |`0 V`    |End voltage (`-1000 V` to `0 V`). |
|`voltage_step`            |`volt`   |`0 V`    |Step voltage (`-100 V` to `+100 V`). |
|`waiting_time`            |`seconds`|`1 s`    |Waiting time after setting voltage and before measuring current. |
|`compliance`              |`ampere` |required |Current compliance. |
|`lcr_amplitude`           |`volt`   |`1 V`    | |
|`lcr_frequency`           |`herz`   |`1 kHz`  | |

## Data format (JSON)

| Column                    | Type    | Description |
|---------------------------|---------|-------------|
|`timestamp`                |`second` |Timestamp in seconds. |
|`temperature`              |`degC`   |Chuck temperature in degree Celcius. |
|`humidity`                 |`percent`|Relative box humidity in percent. |
|`index`                    |`int`    | |
|`bias_voltage`             |`volt`   | |
|`bias_smu_v`               |`volt`   | |
|`bias_smu_i`               |`volt`   | |
|`lcr_cp`                   |`farad`  | |
|`lcr_rp`                   |`ohm`    | |

## Example configuration

```yaml
- type: cv
  name: CV
  enabled: true
  parameters:
    hv_channels: [A2, B2, C2]
    voltage_begin: 0 V
    voltage_end: -600 V
    voltage_step: -5 V
    waiting_time: 1 s
    compliance: 25 uA
    lcr_amplitude: 1 V
    lcr_frequency: 1 kHz
```
