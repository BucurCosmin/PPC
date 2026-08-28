# DBScalesPower — Per-Inverter Active Power Scale Coefficients

Global DB (not optimised access required — keep default optimised).

## Purpose

Allows reducing the effective available power weight of individual inverters
in the proportional dispatch algorithm (FC_PPC_PowerDistribution) without
modifying hardware configuration or WAval reporting.

Used when an inverter consistently delivers less than its reported WAval —
for example due to a string fault, shadow, thermal derating, or degraded
modules — so the PPC does not over-allocate setpoints to it.

## Fields

| Name | Data type | Start value | Description |
|---|---|---|---|
| `P_Scale[0..9]` | Array of Real | `1.0` | Per-inverter scale coefficient. Index 0 = inverter 1, index 9 = inverter 10. |

## How it works

FC_PPC_PowerDistribution uses `P_Scale[i]` to weight each inverter's WAval
in both the capacity sum and the individual share:

```
effective_WAval_i = WAval_i × P_Scale[i]
share_i           = effective_WAval_i / Σ(effective_WAval_j)
WSpt_i            = Ramps_Pcmd × share_i
```

A coefficient of 0.7 means inverter i gets 70% of the share it would
normally get. The remaining 30% is redistributed to the other inverters
automatically via the scaled sum denominator.

The per-inverter `maxWSpt` clamp (WSpt ≤ WAval × WRtg_kW / 10000) is
unchanged — it is a physical safety limit and is not scaled.

## Defaults

All coefficients initialised to `1.0` by `FC_PPC_InitData` (called from
OB100 and on SCADA ResetToDefaults). Values are NOT retained — they reset
on every CPU restart or defaults call.

If you need them to survive a restart, set the `Retain` flag on the
`P_Scale` array in TIA Portal and remove the InitData writes.

## Tuning

| Situation | Action |
|---|---|
| Inverter 10 delivers ~70% of its share | `P_Scale[9] := 0.7` |
| Inverter 3 completely excluded | `P_Scale[2] := 0.0` |
| Restore to normal | `P_Scale[i] := 1.0` |

Setting a coefficient to 0.0 effectively excludes the inverter from the
proportional distribution (it receives WSpt = 0) without taking it offline.
The inverter remains in WCtlCom mode and will respond if its coefficient
is raised later.

## Note

This DB is separate from `PPC_Controller` (DB39) by design — it groups
site-specific calibration values that may need adjustment during
commissioning or after hardware changes, without touching the main
controller parameter DB.
