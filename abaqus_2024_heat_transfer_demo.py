"""Abaqus 2024 pure heat-transfer demo.

Run with Abaqus/CAE 2024, for example:

    abaqus cae noGUI=abaqus_2024_heat_transfer_demo.py

The script creates a tiny 3D block model, applies a transient temperature
difference, submits the job, waits for completion, reads the ODB, and writes
key thermal indicators to JSON and CSV files.
"""

from __future__ import print_function

import csv
import json
import math
import os


REQUIRED_ABAQUS_YEAR = "2024"
MODEL_NAME = "HeatTransferDemo2024"
JOB_NAME = "heat_transfer_demo_2024"
OUTPUT_DIR = "abaqus_heat_demo_output"


def _import_abaqus_modules():
    try:
        from abaqus import mdb, session
        from abaqusConstants import (
            ANALYSIS,
            CARTESIAN,
            CONSTANT_THROUGH_THICKNESS,
            DC3D8,
            DEFAULT,
            DEFORMABLE_BODY,
            FROM_SECTION,
            MIDDLE_SURFACE,
            ON,
            PERCENTAGE,
            SINGLE,
            STANDARD,
            THREE_D,
            UNIFORM,
        )
        import mesh
        from odbAccess import openOdb
    except ImportError:
        print(
            "This script must be run inside Abaqus/CAE 2024 Python, for example:\n"
            "    abaqus cae noGUI=abaqus_2024_heat_transfer_demo.py"
        )
        raise

    return {
        "mdb": mdb,
        "session": session,
        "ANALYSIS": ANALYSIS,
        "CARTESIAN": CARTESIAN,
        "CONSTANT_THROUGH_THICKNESS": CONSTANT_THROUGH_THICKNESS,
        "DC3D8": DC3D8,
        "DEFAULT": DEFAULT,
        "DEFORMABLE_BODY": DEFORMABLE_BODY,
        "FROM_SECTION": FROM_SECTION,
        "MIDDLE_SURFACE": MIDDLE_SURFACE,
        "ON": ON,
        "PERCENTAGE": PERCENTAGE,
        "SINGLE": SINGLE,
        "STANDARD": STANDARD,
        "THREE_D": THREE_D,
        "UNIFORM": UNIFORM,
        "mesh": mesh,
        "openOdb": openOdb,
    }


def _detected_abaqus_version(session):
    candidates = []
    for name in ("productVersion", "kernelVersion", "_abaqusVersion"):
        if hasattr(session, name):
            try:
                candidates.append(str(getattr(session, name)))
            except Exception:
                pass
    return " ".join(candidates).strip()


def _require_abaqus_2024(session):
    detected = _detected_abaqus_version(session)
    if detected and REQUIRED_ABAQUS_YEAR not in detected:
        raise RuntimeError(
            "This demo is intended for Abaqus 2024. Detected version string: %s"
            % detected
        )
    if not detected:
        print("Abaqus version string was not exposed by session; continuing.")


def build_model(api):
    mdb = api["mdb"]

    if MODEL_NAME in mdb.models:
        del mdb.models[MODEL_NAME]
    model = mdb.Model(name=MODEL_NAME)

    length = 0.10
    width = 0.02
    height = 0.02

    sketch = model.ConstrainedSketch(name="block_profile", sheetSize=0.2)
    sketch.rectangle(point1=(0.0, 0.0), point2=(length, width))
    part = model.Part(
        name="AluminumBlock",
        dimensionality=api["THREE_D"],
        type=api["DEFORMABLE_BODY"],
    )
    part.BaseSolidExtrude(sketch=sketch, depth=height)

    material = model.Material(name="Aluminum_demo")
    material.Density(table=((2700.0,),))
    material.Conductivity(table=((205.0,),))
    material.SpecificHeat(table=((900.0,),))

    model.HomogeneousSolidSection(name="SolidSection", material="Aluminum_demo")
    cells = part.Set(cells=part.cells[:], name="AllCells")
    part.SectionAssignment(
        region=cells,
        sectionName="SolidSection",
        offset=0.0,
        offsetType=api["MIDDLE_SURFACE"],
        offsetField="",
        thicknessAssignment=api["FROM_SECTION"],
    )

    part.seedPart(size=0.01, deviationFactor=0.1, minSizeFactor=0.1)
    elem_type = api["mesh"].ElemType(
        elemCode=api["DC3D8"],
        elemLibrary=api["STANDARD"],
    )
    part.setElementType(regions=(part.cells[:],), elemTypes=(elem_type,))
    part.generateMesh()

    assembly = model.rootAssembly
    assembly.DatumCsysByDefault(api["CARTESIAN"])
    instance = assembly.Instance(name="AluminumBlock-1", part=part, dependent=api["ON"])
    assembly.regenerate()

    model.HeatTransferStep(
        name="HeatSoak",
        previous="Initial",
        timePeriod=60.0,
        maxNumInc=100,
        initialInc=1.0,
        minInc=1.0e-5,
        maxInc=5.0,
        deltmx=20.0,
    )


    all_instance_nodes = assembly.Set(name="AllNodes", nodes=instance.nodes[:])
    model.Temperature(
        name="InitialTemperature",
        createStepName="Initial",
        region=all_instance_nodes,
        distributionType=api["UNIFORM"],
        crossSectionDistribution=api["CONSTANT_THROUGH_THICKNESS"],
        magnitudes=(20.0,),
    )

    hot_face = assembly.Set(
        name="HotFace",
        faces=instance.faces.findAt(((0.0, width / 2.0, height / 2.0),)),
    )
    cold_face = assembly.Set(
        name="ColdFace",
        faces=instance.faces.findAt(((length, width / 2.0, height / 2.0),)),
    )
    model.TemperatureBC(
        name="HotSide_100C",
        createStepName="HeatSoak",
        region=hot_face,
        magnitude=100.0,
    )
    model.TemperatureBC(
        name="ColdSide_20C",
        createStepName="HeatSoak",
        region=cold_face,
        magnitude=20.0,
    )

    if JOB_NAME in mdb.jobs:
        del mdb.jobs[JOB_NAME]
    job = mdb.Job(
        name=JOB_NAME,
        model=MODEL_NAME,
        description="Tiny Abaqus 2024 pure heat-transfer demo",
        type=api["ANALYSIS"],
        memory=90,
        memoryUnits=api["PERCENTAGE"],
        explicitPrecision=api["SINGLE"],
        nodalOutputPrecision=api["SINGLE"],
    )
    return job


def submit_and_wait(job):
    print("Submitting Abaqus job: %s" % job.name)
    job.submit(consistencyChecking=False)
    job.waitForCompletion()
    print("Job finished: %s" % job.name)


def _field_values_as_scalars(field_output):
    values = []
    for item in field_output.values:
        data = item.data
        try:
            values.append(float(data))
        except (TypeError, ValueError):
            components = [float(x) for x in data]
            if len(components) == 1:
                values.append(components[0])
            else:
                total = 0.0
                for x in components:
                    total += x * x
                values.append(math.sqrt(total))
    return values

def read_odb_metrics(api, odb_path):
    odb = api["openOdb"](path=odb_path, readOnly=True)
    try:
        step = odb.steps["HeatSoak"]
        last_frame = step.frames[-1]

        temperatures = _field_values_as_scalars(last_frame.fieldOutputs["NT11"])
        hfl_values = []
        if "HFL" in last_frame.fieldOutputs:
            hfl_values = _field_values_as_scalars(last_frame.fieldOutputs["HFL"])

        metrics = {
            "job_name": JOB_NAME,
            "odb_path": os.path.abspath(odb_path),
            "step_name": step.name,
            "final_time_s": float(last_frame.frameValue),
            "node_count": len(temperatures),
            "temperature_min_c": min(temperatures),
            "temperature_max_c": max(temperatures),
            "temperature_average_c": sum(temperatures) / len(temperatures),
        }
        if hfl_values:
            metrics["heat_flux_magnitude_max_w_per_m2"] = max(hfl_values)
            metrics["heat_flux_magnitude_average_w_per_m2"] = (
                sum(hfl_values) / len(hfl_values)
            )
        return metrics
    finally:
        odb.close()


def write_metrics(metrics):
    if not os.path.isdir(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    json_path = os.path.join(OUTPUT_DIR, "metrics.json")
    csv_path = os.path.join(OUTPUT_DIR, "metrics.csv")

    with open(json_path, "w") as stream:
        json.dump(metrics, stream, indent=2, sort_keys=True)

    with open(csv_path, "w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["metric", "value"])
        for key in sorted(metrics):
            writer.writerow([key, metrics[key]])

    print("Wrote metrics:")
    print("  %s" % os.path.abspath(json_path))
    print("  %s" % os.path.abspath(csv_path))


def main():
    api = _import_abaqus_modules()
    _require_abaqus_2024(api["session"])
    job = build_model(api)
    submit_and_wait(job)

    odb_path = JOB_NAME + ".odb"
    if not os.path.exists(odb_path):
        raise RuntimeError("Expected ODB was not created: %s" % odb_path)

    metrics = read_odb_metrics(api, odb_path)
    write_metrics(metrics)
    print(json.dumps(metrics, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()





