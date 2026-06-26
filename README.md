# githubtest

This repository starts with a minimal Abaqus 2024 Python example for learning a basic GitHub workflow with Codex.

## Abaqus 2024 heat-transfer demo

Script:

```powershell
abaqus cae noGUI=abaqus_2024_heat_transfer_demo.py
```

What it does:

- creates a small 3D aluminum block;
- runs a pure transient heat-transfer analysis with `DC3D8` thermal elements;
- fixes one end at 100 C and the other at 20 C;
- waits for the Abaqus job to complete;
- opens the generated `.odb`;
- exports key final-frame metrics to `abaqus_heat_demo_output/metrics.json` and `abaqus_heat_demo_output/metrics.csv`.

The script is intentionally small and example-oriented. It is meant to be run with Abaqus/CAE 2024, not Abaqus 2022.
