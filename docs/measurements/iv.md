---
layout: default
title: IV
parent: Measurements
nav_order: 10
---

# IV

IV ramp using Bias SMU for measurements.

Measurement type: `iv`

Instruments: `Bias SMU`

## Parameters

| Parameter                | Type    | Default | Description |
|--------------------------|---------|---------|-------------|
|`hv_channels`             |`list`   |`[]`     |             |
|`voltage_begin`           |`volt`   |`0 V`    |Start voltage (`-1000 V` to `0 V`). |
|`voltage_end`             |`volt`   |`0 V`    |End voltage (`-1000 V` to `0 V`). |
|`voltage_step`            |`volt`   |`0 V`    |Step voltage (`-100 V` to `+100 V`). |
|`waiting_time`            |`seconds`|`1 s`    |Waiting time after setting voltage and before measuring current. |
|`compliance`              |`ampere` |required |Current compliance. |

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

## Example configuration

```yaml
- type: iv
  name: IV
  enabled: true
  parameters:
    hv_channels: [A1, B1, C2]
    voltage_begin: 0 V
    voltage_end: -1000 V
    voltage_step: -10 V
    waiting_time: 1 s
    compliance: 25 uA
```
