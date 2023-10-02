# CV

CV ramp using Bias SMU and LCR for measurements.

Type: `cv`

### Configuration

- **name**: (str) name of node.
- **enabled**: (bool) enabled state. Default is `true`.
- **auto_disable**: (bool) auto disable on success. Default is `true`.
- **parameters**:
    - **hv_channels**: (list) list of high voltage channels. Default is `[]`.
    - **voltage_begin**: (metric) start voltage in Volt (`-1000 V` to `0 V`). Required.
    - **voltage_end**: (metric) end voltage in Volt (`-1000 V` to `0 V`). Required.
    - **voltage_step**: (metric) step voltage Volt (`-100 V` to `+100 V`). Required.
    - **waiting_time**: (metric) waiting time in seconds between voltage change and readings. Default is `1 s`.
    - **compliance**: (metric) current compliance for bias source. Required.
    - **lcr_amplitude**: (metric) LCR amplitude in Volt. Default is `1 V`.
    - **lcr_frequency**: (metric) LCR frequency in Hertz. Default is `1 kHz`.

### Example configuration

```yaml
- type: cv
  name: CV
  enabled: true
  auto_disable: true
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

### Output

| Column                    | Type    | Description |
|---------------------------|---------|-------------|
|`timestamp`                |`float`  |Timestamp in seconds. |
|`temperature`              |`float`  |Chuck temperature in degree Celcius. |
|`humidity`                 |`float`  |Relative box humidity in percent. |
|`index`                    |`int`    |Index for sorting. |
|`bias_voltage`             |`float`  |Voltage level applied in Volt. |
|`bias_smu_v`               |`float`  |Voltage reading in Volt. |
|`bias_smu_i`               |`float`  |Current redaing in Ampere. |
|`lcr_cp`                   |`float`  |CP reading in Farad. |
|`lcr_rp`                   |`float`  |RP reading in Ohm. |
