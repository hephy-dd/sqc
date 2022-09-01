# Cint

Strip measurement.

Type: `cint`

## Configuration

- **name**: (str) name of node.
- **interval**: (int) strip interval. Default is `1`.
- **enabled**: (bool) enabled state. Default is `true`.
- **parameters**:
    - **hv_channels**: (list) list of high voltage channels. Default is `[]`.
    - **lv_channels**: (list) list of low voltage channels. Default is `[]`.
    - **lcr_amplitude**: (metric) LCR amplitude in Volt. Default is `1 V`.
    - **lcr_frequency**: (metric) LCR frequency in Hertz. Default is `1 kHz`.
    - **cint_cp_minimum**: (metric) required minimum for `cint_cp` (see output). Default is `0 F`.
    - **cint_cp_maximum**: (metric) required maximum for `cint_cp` (see output). Default is `0 F`.
    - **soft_correction**: (bool) enables use of software open correction. Default is `true`.
    - **n_samples**: (int) number of readings to be taken for median. Default is `5`.

## Example configuration

```yaml
- type: cint
  name: Cint
  interval: 14
  enabled: true
  parameters:
    hv_channels: [A1, B1, C2]
    lv_channels: [1H05, 1G02]
    cint_cp_minimum: 0.5 pF
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
|`cint_cp`                  |`float`  |CP reading in Farad. |
|`cint_rp`                  |`float`  |RP reading in Ohm. |
