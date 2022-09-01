# Idark

Strip measurement.

Type: `idark`

## Configuration

- **name**: (str) name of node.
- **interval**: (int) strip interval. Default is `1`.
- **enabled**: (bool) enabled state. Default is `true`.
- **parameters**:
    - **hv_channels**: (list) list of high voltage channels. Default is `[]`.
    - **idark_i_minimum**: (metric) required minimum for `idark_i` (see output). Default is `0 A`.
    - **idark_i_maximum**: (metric) required maximum for `idark_i` (see output). Default is `0 A`.
    - **n_samples**: (int) number of readings to be taken for median. Default is `5`.

## Example configuration

```yaml
- type: idark
  name: Idark
  interval: 4
  enabled: true
  parameters:
    hv_channels: [A1, B1, C2]
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
|`idark_i`                  |`float`  | |
