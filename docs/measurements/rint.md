# Rint

Interstrip resistance measurement.

Type: `rint`

## Configuration

- **name**: (str) name of node.
- **interval**: (int) strip interval. Default is `1`.
- **enabled**: (bool) enabled state. Default is `true`.
- **parameters**:
    - **hv_channels**: (list) list of high voltage channels. Default is `[]`.
    - **lv_channels**: (list) list of low voltage channels. Default is `[]`.
    - **smu_voltage_begin**: (metric) SMU begin voltage. Default is `0 V`.
    - **smu_voltage_end**: (metric) SMU end voltage. Default is `5 V`.
    - **smu_voltage_step**: (metric) SMU step voltage. Default is `1 V`.
    - **smu_waiting_time**: (metric) waiting time in seconds between voltage change and readings. Default is `0 s`.
    - **smu_compliance**: (metric) SMU compliance. Default is `50 uA`.
    - **rint_r_minimum**: (metric) required minimum for `rint_r` (see output). Default is `0 ohm`.
    - **rint_r_maximum**: (metric) required maximum for `rint_r` (see output). Default is `0 ohm`.
    - **n_samples**: (int) number of readings to be taken for median. Default is `5`.

## Example configuration

```yaml
- type: rint
  name: Rint
  interval: 14
  enabled: true
  parameters:
    hv_channels: [A1, B1, C1, C2]
    lv_channels: [1A05, 1C02]
    rint_r_minimum: 5 Gohm
    rint_r_maximum: 2000 Gohm
```

## Output

| Column                    | Type    | Description |
|---------------------------|---------|-------------|
|`timestamp`                |`float`  |Timestamp in seconds. |
|`temperature`              |`float`  |Chuck temperature in degree Celcius. |
|`humidity`                 |`float`  |Relative box humidity in percent. |
|`index`                    |`int`    |Index for sorting. |
|`strip`                    |`str`    |Strip name. |
|`strip_index`              |`int`    |Strip index. |
|`rint_u`                   |`float`  | |
|`rint_i`                   |`float`  | |
|`rint_r`                   |`float`  | |
