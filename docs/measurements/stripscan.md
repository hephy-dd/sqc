# Stripscan

Applies a bias voltage and performs a list of `strip_measurements`.

Type: `stripscan`

## Configuration

- **name**: (str) name of node.
- **strips**: (str) range of strips to be measured. Default is an empty string.
- **enabled**: (bool) enabled state. Default is `true`.
- **auto_disable**: (bool) auto disable on success. Default is `true`.
- **parameters**:
    - **hv_channels**: (list) list of high voltage channels. Default is `[]`.
    - **bias_voltage**: (metric) bias voltage to be applied. Required.
    - **bias_compliance**: (metric) bias current compliance. Required.
    - **waiting_time**: (metric) waiting time in seconds between voltage change and readings. Default is `1 s`.
- **strip_measurements**: strip measurements.

## Example configuration

```yaml
- type: stripscan
  name: Stripscan
  strips: "1-1920"
  enabled: true
  auto_disable: false
  parameters:
    hv_channels: [A1, B1, C2]
    bias_voltage: -600 V
    bias_compliance: 25 uA
  strip_measurements: {}
```
