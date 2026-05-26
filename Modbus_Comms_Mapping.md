# SMA Sunny Central — Modbus Comms Block Mapping
**Target:** PPC_Controller [DB39], UDT `Inverter_controller`  
**Connection:** Modbus TCP, Unit ID = 3 (grid management unit)  
**Register file:** `SMA\SCADA_Modbus_Register_Map_SMA_SunnyCentral_ENUMS_Ramps_RideThrough_PPC_RO.xlsx`

---

## 1. Conventions

| Item | Value |
|---|---|
| Modbus protocol | TCP/IP |
| Unit (Slave) ID | 3 |
| Register bit-width | 32-bit values, each occupies **2 consecutive 16-bit Modbus registers** |
| Addressing | 1-based (register 1 = Modbus address 0x0000) |
| Write function code | FC16 (Write Multiple Registers) |
| Read function code | FC04 (Read Input Registers) for measurements; FC03 (Read Holding Registers) for writable params |
| Endianness | Big-endian (high word first) |
| Cycle | Read and write every OB30 scan (100 ms), or batched per inverter |

**Scaling formats:**
| Format | Meaning | Example |
|---|---|---|
| FIX0 | Integer, scaling = 1, value in physical units | WSpt: 500 → 500 kW |
| FIX4 | Integer × 10000, value in pu | WAval: 8500 → 0.8500 pu |

---

## 2. WRITE to SMA Inverter (PLC → Inverter)

The comms block reads these UDT fields each cycle and writes them to the corresponding SMA holding registers via **FC16**.

| UDT Field | SMA Register Name | Reg Address¹ | Type | Scaling | ENUM Values | Written by FC |
|---|---|---|---|---|---|---|
| `OperMode` | `InvOpMod` | See manual | DInt | ENUM | 308 = Operation, 303 = Stop | FaultHandler |
| *(derived)* `RemRdy` | `GriMng.RemRdy` | See manual | DInt | ENUM | 308 = Ready, 303 = Standby | **Comms block only** — NOT in UDT |
| `WMode` | `GriMng.WMod` | See manual | DInt | ENUM | 1079 = WCtlCom, 303 = Off | PowerDistribution |
| `WSpt` | `GriMng.WNom` | See manual | DInt | FIX0 (kW) | — | PowerDistribution |
| `VArMode` | `GriMng.VArMod` | See manual | DInt | ENUM | 1072 = VArCtlCom, 1075 = PFCtlCom, 303 = Off | ReactiveControl |
| `VArSpt` | `GriMng.VArNom` | See manual | DInt | FIX0 (kVAr) | — | ReactiveControl |
| `PFSpt` | `GriMng.PFNom` | See manual | DInt | FIX4 (×10000) | 9500 = PF 0.950, 10000 = PF 1.000 | ReactiveControl |
| `ErrClr` | `FltRst` | **Holding reg 8** | DInt | — | 26 = Ackn (one-shot); 0 = idle | FaultHandler |

> ¹ Look up exact addresses in `SMA\SCADA_Modbus_Register_Map_SMA_SunnyCentral_ENUMS_Ramps_RideThrough_PPC_RO.xlsx`

### Critical write sequencing — SMA interlock rules

The comms block **must** enforce these sequences. Writing out of order will be rejected or cause unexpected inverter behaviour.

**START (OperMode → 308):**
1. Write `GriMng.RemRdy = 308` (Ready)
2. Wait one Modbus transaction (or same frame if multi-write supported)
3. Write `InvOpMod = 308` (Operation)

**STOP (OperMode → 303):**
1. Write `GriMng.RemRdy = 303` (Standby)
2. Write `InvOpMod = 303` (Stop)

**When the comms block sees `OperMode = 303` in the UDT, it must write RemRdy=303 before InvOpMod=303.**  
**When it sees `OperMode = 308`, it must write RemRdy=308 before InvOpMod=308.**

> `RemRdy` is NOT in the `Inverter_controller` UDT. The comms block derives it from `OperMode` internally.

### ErrClr one-shot

`ErrClr` in the UDT will be **26** for exactly one OB30 scan (100 ms), then returns to **0**.  
The comms block must write Holding Register 8 = 26 **in the scan where ErrClr ≠ 0** and write 0 otherwise.  
Do NOT continuously write 26 — the SMA inverter requires a rising edge (0 → 26) to acknowledge a fault.

---

## 3. READ from SMA Inverter (Inverter → PLC)

The comms block reads these SMA input registers via **FC04** and writes the values into the corresponding UDT fields each cycle.

| UDT Field | SMA Register Name | Reg Address¹ | Type | Scaling | Notes |
|---|---|---|---|---|---|
| `RemReady` | `OpStt` (bit decode) | See manual | DInt | ENUM | Set TRUE when OpStt = 308 (Operation) or 309 (Derating). FALSE otherwise. |
| `Error` | `ErrStt` | See manual | DInt | ENUM | Set TRUE when ErrStt ≠ 307 (307 = Ok). FALSE = no fault. |
| `Wactive` | `W` (AC active power output) | See manual | DInt | FIX0 (kW) | Measured output in kW |
| `Qactive` | `VAr` (AC reactive power output) | See manual | DInt | FIX0 (kVAr) | Measured reactive output |
| `WAval` | `GriMng.WAval` | See manual | DInt | **FIX4 (pu×10000)** | Available active power fraction. 10000 = 100% available. |
| `VArAval` | `GriMng.VArAval` | See manual | DInt | **FIX4 (pu×10000)** | Available reactive power fraction. |
| `PwrOffReas` | `PwrOffReas` | **Input reg 178** | DInt | ENUM / code | 0 = no event. Non-zero = disconnection reason code. 21626 = "Low Power SetPoint". |
| `DrtStt` | `DrtStt` | See manual | DInt | ENUM | 0 = no derating. Non-zero = derating active (thermal, frequency, etc.) |
| *(for SCADA)* | `ErrNo` | **Input reg 96** | DInt | ENUM | Fault code — not stored in UDT but should be logged by SCADA when `Error = TRUE`. |

### RemReady derivation

SMA does not expose a dedicated "remote ready" bit. Derive `RemReady` from `OpStt`:

| `OpStt` value | Meaning | `RemReady` |
|---|---|---|
| 308 | Operation — producing | TRUE |
| 309 | Derating | TRUE |
| 303 | Stop | FALSE |
| 307 | Ok (standby) | TRUE (ready, not yet operating) |
| 35 | Error | FALSE |
| Other | Unknown / initialising | FALSE |

> Adjust this table against the actual ENUM values in the SMA Modbus manual.

### Error derivation

`ErrStt` = 307 means "Ok" (no fault). Map `Error` as:
```
Error := (ErrStt <> 307)
```

---

## 4. Local PLC Fields — NOT from Modbus

These UDT fields are managed entirely within the PLC. The comms block must NOT overwrite them.

| UDT Field | Source | Description |
|---|---|---|
| `Enabled` | HMI / DB39 operator input | Set TRUE to include inverter in PPC. Set by operator, not by inverter. |
| `CommError` | Comms block itself | Set TRUE if no valid Modbus response within timeout (e.g. 3 consecutive failures). Cleared when comms recover. |

---

## 5. DB39 Fields Used by PPC Logic

These DB39 scalar fields are read/written by the FB and FCs. Some are set by SCADA or HMI (inputs to PPC); others are outputs mirrored for HMI display.

### Set by SCADA / HMI (inputs to PPC):

| DB39 Field | Type | Description | Source |
|---|---|---|---|
| `START_CONTROLLER` | Bool | Maps to `EN_PPC` FB input — master enable | HMI |
| `Targets_P` | Real | Active power setpoint from SCADA (kW) | SCADA (REMOTE) / HMI (LOCAL) |
| `Targets_Q` | Real | Reactive power setpoint (kVAr) | SCADA / HMI |
| `Targets_PF` | Real | Power factor setpoint | SCADA / HMI |
| `P_RampUp` | Real | Active power ramp-up rate (kW/s) | Engineering / HMI |
| `P_RampDown` | Real | Active power ramp-down rate (kW/s) | Engineering / HMI |
| `Q_Ramp` | Real | Reactive power ramp rate (kVAr/s) — used for both up and down² | Engineering / HMI |
| `WRtg_kW` | Real | Rated power per inverter (kW) — read from SMA register 184 at commissioning | Engineering |
| `Plant_P_meas` | Real | Plant-level active power measurement at PCC (kW) — written by energy meter comms | Meter |
| `Plant_Q_meas` | Real | Plant-level reactive power measurement at PCC (kVAr) | Meter |

### Written by PPC logic (outputs for HMI/SCADA):

| DB39 Field | Type | Description |
|---|---|---|
| `Plant_Mode` | Int | 0 = LOCAL, 1 = REMOTE_IEC, 2 = FALLBACK |
| `Plant_N_Online` | Int | Number of inverters currently online |
| `Limits_PmaxPlant` | Real | Total available active power (kW) |
| `Limits_QmaxPlant` | Real | Total available reactive power (kVAr) |
| `Ramps_Pcmd` | Real | Rate-limited active power command (kW) |
| `AnyFault` | Bool | TRUE = at least one inverter fault/comm error |
| `AnyDerating`³ | Bool | TRUE = at least one inverter is derated |
| `FaultMask`³ | Word | Bit i = inverter i has active fault or comm error |
| `Ramps_Qcmd`³ | Real | Rate-limited reactive power command (kVAr) |

---

## 6. DB39 Fields to Add in TIA Portal

The following fields are used by the current SCL code but are **not yet in DB39** (not in the exported PDF):

| Field | Type | Notes |
|---|---|---|
| `AnyDerating` | Bool | Mirrored from FaultHandler output |
| `FaultMask` | Word | Mirrored from FaultHandler output; bit i = inverter i |
| `Ramps_Qcmd` | Real | Mirrored ramped Q command for HMI trending |
| `Q_RampUp` | Real | If separate up/down ramp rates are needed; otherwise use existing `Q_Ramp` for both |
| `Q_RampDown` | Real | If separate up/down ramp rates are needed; otherwise use existing `Q_Ramp` for both |

> ² DB39 currently has a single `Q_Ramp` field. The SCL code references `Q_RampUp` and `Q_RampDown`. Either add both fields to DB39, or change the FB call to pass `Q_Ramp` for both parameters.

The `Inverter_controller` UDT also needs:

| Field | Type | Notes |
|---|---|---|
| `ErrClr` | DInt | Written by FaultHandler; comms block maps to SMA Holding Register 8 |

---

## 7. Per-Inverter Write Transaction Summary

Each OB30 cycle, the comms block performs the following **write** transaction for each online inverter (may be batched into a single FC16 call):

```
IF ErrClr <> 0 THEN
    Write FltRst (reg 8) = ErrClr        // Fault acknowledge one-shot
END_IF

IF OperMode changed THEN
    IF OperMode = 303 THEN               // Stop sequence
        Write GriMng.RemRdy = 303        // Step 1: remove remote permission
        Write InvOpMod = 303             // Step 2: stop
    ELSIF OperMode = 308 THEN            // Start sequence
        Write GriMng.RemRdy = 308        // Step 1: grant remote permission
        Write InvOpMod = 308             // Step 2: start
    END_IF
END_IF

Write GriMng.WMod  = WMode              // Active power control mode
Write GriMng.WNom  = WSpt               // Active power setpoint (kW)
Write GriMng.VArMod = VArMode           // Reactive control mode
Write GriMng.VArNom = VArSpt            // Reactive setpoint (kVAr)
Write GriMng.PFNom  = PFSpt             // PF setpoint (×10000)
```

## 8. Per-Inverter Read Transaction Summary

Each OB30 cycle, the comms block reads the following from each inverter (FC04):

```
Read OpStt     → derive RemReady (TRUE if OpStt ∈ {307, 308, 309})
Read ErrStt    → derive Error    (TRUE if ErrStt ≠ 307)
Read W         → Wactive  (kW, FIX0)
Read VAr       → Qactive  (kVAr, FIX0)
Read GriMng.WAval   → WAval   (pu×10000, FIX4)
Read GriMng.VArAval → VArAval (pu×10000, FIX4)
Read PwrOffReas (reg 178) → PwrOffReas
Read DrtStt           → DrtStt
// For SCADA alarm logging only (not in UDT):
Read ErrNo (reg 96)   → log when Error = TRUE
```

If a read transaction fails (timeout or exception response):
```
Set CommError := TRUE for this inverter
// Leave all other UDT fields at their last valid values
// CommError cleared when next successful read completes
```

---

> Register addresses marked "See manual" must be confirmed from:  
> `SMA\SCADA_Modbus_Register_Map_SMA_SunnyCentral_ENUMS_Ramps_RideThrough_PPC_RO.xlsx`
