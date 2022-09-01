# Idiel

Dielectric current strip measurement.

Type: `idiel`

## Configuration

- **name**: (str) name of node.
- **interval**: (int) strip interval. Default is `1`.
- **enabled**: (bool) enabled state. Default is `true`.
- **parameters**:
    - **hv_channels**: (list) list of high voltage channels. Default is `[]`.
    - **lv_channels**: (list) list of low voltage channels. Default is `[]`.
    - **smu_compliance**: (metric) in Ampere. Default is `1 uA`.
    - **smu_voltage**: (metric) in Volt. Default is `10 V`.
    - **idiel_i_minimum**: (metric) required minimum for `idiel_i` (see output). Default is `0 A`.
    - **idiel_i_maximum**: (metric) required maximum for `idiel_i` (see output). Default is `0 A`.
    - **n_samples**: (int) number of readings to be taken for median. Default is `5`.

## Example configuration

```yaml
- type: idiel
  name: Idiel
  interval: 4
  enabled: true
  parameters:
    hv_channels: [A1, B1, C2]
    lv_channels: [1D05, 1C07]
    smu_compliance: 1 uA
    smu_voltage: 10 V
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
|`idiel_i`                  |`float`  |Measured current in Ampere. |
