# PPC_Controller DB (DB39) — Fields to Add

Add these rows to DB39 in TIA Portal.  
All new fields are at the **end** of the variable table — never insert in the middle of an existing optimised DB.

---

## New fields — Mode 4 / 5 (POC PF and Q closed-loop PI)

### SCADA-writable (operator or SCADA sets these)

| Name | Data type | Start value | Retain | Description |
|---|---|---|---|---|
| `PF_poc_target` | Real | `1.0` | ☐ | Target PF at POC. Signed: +0.95 = overexcited (inject vars), −0.95 = underexcited (absorb vars). Only used in Mode 4. |
| `PF_Kp` | Real | `0.0` | ☐ | PI proportional gain kVAr/kVAr. Start at 0 (pure integrator). Used in Mode 4 and 5. |
| `PF_Ki` | Real | `0.05` | ☐ | PI integral gain (1/s). Start at 0.05 (~30s settling). Too high → oscillation. Used in Mode 4 and 5. |
| `PF_Tt` | Real | `5.0` | ☐ | PI anti-windup tracking time constant (s). 0 = disable anti-windup. Used in Mode 4 and 5. |
| `PF_Reset` | Bool | `FALSE` | ☐ | One-shot: write TRUE to reset PI integrator. PLC clears it automatically the next cycle. |

### Diagnostics (SCADA reads these — do not write from SCADA)

| Name | Data type | Start value | Retain | Description |
|---|---|---|---|---|
| `Q_poc_required` | Real | `0.0` | ☐ | Target Q at POC (kVAr). In Mode 4: derived from P_poc and PF_poc_target. In Mode 5: equals Cmd_Q. |
| `Q_poc_error` | Real | `0.0` | ☐ | Q error at POC (kVAr) = Q_poc_required − Q_poc_measured. Zero when loop is closed. |
| `PF_poc_actual` | Real | `0.0` | ☐ | Actual PF at POC computed from grid meter P and Q. Unsigned (0–1). |

**Total: 8 new fields** (5 REAL + 1 BOOL writable, 3 REAL read-only diagnostic)

---

## Notes

- **Retain:** Leave unchecked for all new fields. They are re-initialised on startup by `FC_PPC_InitData` (called from OB100). Retaining them would preserve a stale integrator value across power cycles.
- **Optimised access:** DB39 already uses `S7_Optimized_Access = TRUE`. New fields added at the end are always safe — no offset shift for existing fields.
- **`PF_poc_target` name:** The `PF_` prefix is shared with Mode 4 and 5 parameters. In Mode 5 (POC Q PI), `PF_poc_target` is not used — only `Cmd_Q` (existing field) matters for the setpoint. The other parameters (`PF_Kp`, `PF_Ki`, `PF_Tt`) are shared between both modes.
- **`PF_Reset` self-clears:** Written TRUE by SCADA → FB_PPC_QCapability resets integrator → FB_PPC_Controller writes FALSE the same scan. SCADA will read FALSE on the next poll — this is correct, not a communication error.

---

## Existing fields used by Mode 4 / 5 (already in DB39 — no action needed)

These existing fields are read by the new modes — no changes required.

| Name | Used by Mode | How |
|---|---|---|
| `VArControl_Mode` | 4, 5 | Set to 4 or 5 to activate the respective closed-loop mode |
| `Cmd_Q` | 5 | Q setpoint at POC in kVAr (closed-loop target for Mode 5) |
| `Cmd_PF` | — | Not used by Modes 4/5. Used only by Cmd_VArMode=2 (per-inverter PF dispatch) |
| `PID_Reset` | — | Existing Mode 3 reset — separate from `PF_Reset` |
