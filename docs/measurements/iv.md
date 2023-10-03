# IV

IV ramp using Bias SMU for measurements.

Type: `iv`

## Configuration

- **name**: (str) name of node.
- **enabled**: (bool) enabled state. Default is `true`.
- **auto_disable**: (bool) auto disable on success. Default is `true`.
- **parameters**:
    - **hv_channels**: (list) list of high voltage channels. Default is `[]`.
    - **voltage_begin**: (metric) start voltage (`-1000 V` to `0 V`). Required.
    - **voltage_end**: (metric) end voltage (`-1000 V` to `0 V`). Required.
    - **voltage_step**: (metric) step voltage (`-100 V` to `+100 V`). Required.
    - **waiting_time**: (metric) waiting time in seconds between voltage change and readings. Default is `1 s`.
    - **compliance**: (metric) current compliance for bias source in Ampere. Required.

## Example configuration

```yaml
- type: iv
  name: IV
  enabled: true
  auto_disable: true
  parameters:
    hv_channels: [A1, B1, C2]
    voltage_begin: 0 V
    voltage_end: -1000 V
    voltage_step: -10 V
    waiting_time: 1 s
    compliance: 25 uA
```

## Output

| Column                    | Type    | Description |
|---------------------------|---------|-------------|
|`timestamp`                |`float`  |Timestamp in seconds. |
|`temperature`              |`float`  |Chuck temperature in degree Celcius. |
|`humidity`                 |`float`  |Relative box humidity in percent. |
|`index`                    |`int`    |Index for sorting. |
|`bias_voltage`             |`float`  |Voltage level applied in Volt. |
|`bias_smu_v`               |`float`  |Voltage reading in Volt. |
|`bias_smu_i`               |`float`  |Current redaing in Ampere. |
