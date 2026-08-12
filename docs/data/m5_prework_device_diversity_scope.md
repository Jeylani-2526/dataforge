# M5 Pre-Work: Telemetry Device Diversity Scope

## Objective

Prepare the TELEMETRY generator for future device diversity testing in M5.

The planned change is to introduce 3–5 distinct `device_id` values so that generated telemetry data can represent multiple source devices instead of a single device identity.

## Scope

The future implementation should:

- Define 3–5 stable `device_id` values.
- Distribute generated TELEMETRY records across these device IDs.
- Preserve the existing TELEMETRY schema.
- Keep the change limited to the generator logic required for device diversity.
- Add or update tests if required during implementation.

## Out of Scope

No implementation is required as part of this pre-work task.

The M3-approved 50,000-record dataset will not be modified or regenerated as part of this task.

## M5 Follow-Up

Implementation can be performed during M5, followed by validation that:

- all configured device IDs appear in generated output,
- record generation remains schema-valid,
- existing generator behavior is not unintentionally affected.