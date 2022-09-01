# Istrip

Strip measurement.

Type: `istrip`

## Configuration

- **name**: (str) name of node.
- **interval**: (int) strip interval. Default is `1`.
- **enabled**: (bool) enabled state. Default is `true`.
- **parameters**:
    - **hv_channels**: (list) list of high voltage channels. Default is `[]`.
    - **lv_channels**: (list) list of low voltage channels. Default is `[]`.
    - **istrip_i_minimum**: (metric) required minimum for `istrip_i` (see output). Default is `0 A`.
    - **istrip_i_maximum**: (metric) required maximum for `istrip_i` (see output). Default is `0 A`.
    - **n_samples**: (int) number of readings to be taken for median. Default is `5`.

## Example configuration

```yaml
- type: istrip
  name: Istrip
  interval: 4
  enabled: true
  parameters:
    hv_channels: [A1, B1, C2]
    lv_channels: [1A05]
    istrip_i_minimum: 5 pA
    istrip_i_maximum: 300 pA
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
|`istrip_i`                 |`float`  |Measured current in Ampere. |
