# Rpoly

Strip measurement.

Type: `rpoly`

## Configuration

Note: this measurements requires an additional low-voltage switch setting
`lv_channels_istrip` for measuring additional strip current.

- **name**: (str) name of node.
- **interval**: (int) strip interval. Default is `1`.
- **enabled**: (bool) enabled state. Default is `true`.
- **parameters**:
    - **hv_channels**: (list) list of high voltage channels. Default is `[]`.
    - **lv_channels**: (list) list of low voltage channels. Default is `[]`.
    - **lv_channels_istrip**: (list) list of low voltage channels for reading `istrip_i`. Default is `[]`.
    - **rpoly_r_minimum**: (metric) required minimum for `rpoly_r` (see output). Default is `0 ohm`.
    - **rpoly_r_maximum**: (metric) required maximum for `rpoly_r` (see output). Default is `0 ohm`.
    - **n_samples**: (int) number of readings to be taken for median. Default is `5`.

## Example configuration

```yaml
- type: rpoly
  name: Rpoly
  interval: 4
  enabled: true
  parameters:
    hv_channels: [A1, B1, C1]
    lv_channels: [1C05]
    lv_channels_istrip: [1A05]
    rpoly_r_minimum: 1 Mohm
    rpoly_r_maximum: 2 Mohm
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
|`rpoly_r`                  |`float`  | |
|`rpoly_i`                  |`float`  | |
|`rpoly_istrip_i`           |`float`  |Measured strip current in Ampere. |
|`rpoly_u`                  |`float`  | |
