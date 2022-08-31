---
layout: default
title: Home
nav_order: 1
permalink: /
---

# SQC

Sensor Quality Control for the CMS Tracker
{: .fs-6 .fw-300 }

## Getting started

### Install

Install using pip in a virtual environment.

```bash
pip install git+https://github.com/hephy-dd/sqc.git@<version>
```

### Run

```bash
sqc
```

### Setup

When running for the first time make sure to configure the VISA resource settings according to the individual setup by using `Edit` &rarr; `Resources`.

Also select the correct SMU instrument models (K2410, K2470, K2657A) in the preferences.

### Safety

**Note:** this software controls a highly complex, high voltage measurement setup in a laboratory environment. Always take care and double check the situation before taking actual measurements.
