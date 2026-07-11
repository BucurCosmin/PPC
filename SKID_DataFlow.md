# SKID Modbus Communication ↔ FB_PPC_Controller Data Flow
**CEF Tandarei 46 MW PV Plant — PPC System**
*Siemens S7-1500, TIA Portal SCL*
Version: 2026-07-11

---

## 1. Architecture Overview

Each physical SMA SC 4600 UP inverter has a dedicated SKID DB (SKID1..SKID10).
The PPC controller maintains a 10-element `Inverter_controller` array inside `FB_PPC_Controller_DB`.
Two layers of code bridge between them every 100 ms OB30 scan:

```
SMA Inverter (Modbus TCP)
        │
        │  FC04 reads (two blocks per scan)
        ▼
SKIDx.db  ──────────────────────────────────────────────────
  Inverter  : Sunny_inverter      ← FC_InputReg10_L106  (regs 10–115)
  Params_Inputs : Skid_Parameters_Inputs  ← FC_InputReg116_L112 (regs 116–227)
  Params_Hold   : Skid_Parameters_Hold
  ConnectSettings : TCON_IP_v4
        │
        │  FC_PPC_SkidMapping (called 10× per scan, one per SKID)
        ▼
FB_PPC_Controller_DB.Inverters[0..9]  : Inverter_controller
        │
        ├─► FC_PPC_InverterMonitor  → PmaxPlant, QmaxPlant, N_Online
        ├─► FC_PPC_PowerDistribution → WSpt per inverter
        └─► FC_PPC_ReactiveControl  → VArSpt / PFSpt per inverter
        │
        │  FC_PPC_SkidMapping writes setpoints back to SKIDx.db
        ▼
SKIDx.db.Inverter (Sunny_inverter write fields)
        │
        │  FC_Pack_Write_Regs → FC16 writes per scan
        ▼
SMA Inverter (Modbus TCP)
```

**OB30 call order (critical):**
1. `FC_SkidElectricStatus` × 10 — DI status per skid → `FB_PPC_Controller_DB.Skids[0..9]`
2. `FC_PPC_SkidMapping` × 10 — SKID DB ↔ Inverter_controller (reads first, writes previous scan's setpoints)
3. `FB_PPC_Controller` (contains InverterMonitor → RampControl → FreqResponse → PowerDistribution → ReactiveControl → FaultHandler)

---

## 2. Modbus Read Blocks: SKID DB Population

Two FCs together cover the complete SMA SC 4600 UP input register map.
Both are called by `ReadInverterData` (FB15) once per scan per SKID.

### 2.1 FC_InputReg10_L106_To_Inputs — SMA registers 10–115

Array offset: `Reg[0]` = SMA register 10, `Reg[n]` = SMA register (10 + n).

| SMA Reg | Reg[] | Field | Scaling | Unit | UDT destination |
|---|---|---|---|---|---|
| 10..11 | [0..1] | DcMs.TotWatt | S32 FIX0 | W | Inps."DcMs.TotWatt" |
| 12..13 | [2..3] | InvMs.DclVol.Stk1 | S32 FIX1 ÷10 | V | Inps."InvMs.DclVol.Stk1" |
| 14..15 | [4..5] | InvMs.DclVol.Stk2 | S32 FIX1 ÷10 | V | Inps."InvMs.DclVol.Stk2" |
| 16..17 | [6..7] | InvMs.DclVol.Stk3 | S32 FIX1 ÷10 | V | Inps."InvMs.DclVol.Stk3" |
| 18..19 | [8..9] | InvMs.TotA.PhsA | S32 FIX0 | mA | Inps."InvMs.TotA.PhsA" |
| 22..23 | [12..13] | InvMs.TotA.PhsC | S32 FIX0 | mA | Inps."InvMs.TotA.PhsC" |
| 24..25 | [14..15] | InvMs.PF | S32 FIX4 ÷10000 | — | Inps."InvMs.PF" (Real) |
| 26..27 | [16..17] | InvMs.TotVA | S32 FIX0 | VA | Inv."InvMs.TotVA" |
| **28..29** | **[18..19]** | **InvMs.TotW** | **S32 FIX0** | **kW** | **Inv."InvMs.TotW"** |
| **30..31** | **[20..21]** | **InvMs.TotVAr** | **S32 FIX0** | **kVAr** | **Inv."InvMs.TotVAr"** |
| 32..33 | [22..23] | GriMs.V.PhsAB | S32 FIX1 ÷10 | V | Inps."GriMs.V.PhsAB" |
| 34..35 | [24..25] | GriMs.V.PhsBC | S32 FIX1 ÷10 | V | Inps."GriMs.V.PhsBC" |
| 36..37 | [26..27] | GriMs.V.PhsCA | S32 FIX1 ÷10 | V | Inps."GriMs.V.PhsCA" |
| **38..39** | **[28..29]** | **GriMs.Hz** | **S32 FIX2 ÷100** | **Hz** | **Inv."GriMs.Hz" (Real)** |
| 40..41 | [30..31] | TmpCab.Acc | S32 FIX1 ÷10 | °C | Inps."TmpCab.Acc" |
| 42..43 | [32..33] | TmpCab.Dcc | S32 FIX1 ÷10 | °C | Inps."TmpCab.Dcc" |
| 44..45 | [34..35] | TmpCab.Rio | S32 FIX1 ÷10 | °C | Inps."TmpCab.Rio" |
| 46..47 | [36..37] | TmpCab.Max | S32 FIX1 ÷10 | °C | Inps."TmpCab.Max" |
| 48..49 | [38..39] | TmpStk.IgbtMax | S32 FIX1 ÷10 | °C | Inps."TmpStk.IgbtMax" |
| 50..51 | [40..41] | TmpStk.PcbMax | S32 FIX1 ÷10 | °C | Inps."TmpStk.PcbMax" |
| 52..53 | [42..43] | TmpExl | S32 FIX1 ÷10 | °C | Inps.TmpExl |
| 54..55 | [44..45] | TmpTrf | S32 FIX1 ÷10 | °C | Inps.TmpTrf |
| 56..57 | [46..47] | DcSw1Stt | S32 ENUM | — | Inps.DcSw1Stt |
| 58..59 | [48..49] | DcSw2Stt | S32 ENUM | — | Inps.DcSw2Stt |
| 60..61 | [50..51] | DcSw3Stt | S32 ENUM | — | Inps.DcSw3Stt |
| 62..63 | [52..53] | AcSwStt | S32 ENUM | — | Inps.AcSwStt |
| 66..67 | [56..57] | CapacSwStt | S32 ENUM | — | Inps.CapacSwStt |
| 68..69 | [58..59] | PrchrgSwStt | S32 ENUM | — | Inps.PrchrgSwStt |
| 70..71 | [60..61] | Cnt.TotFeedTm | U32 FIX0 | s | Inps."Cnt.TotFeedTm" |
| 72..73 | [62..63] | Cnt.TotOpTm | U32 FIX0 | s | Inps."Cnt.TotOpTm" |
| 74..75 | [64..65] | Cnt.TotWatthIn | S32 FIX2 ÷100 | MWh | Inps."Cnt.TotWatthIn" |
| 76..77 | [66..67] | Cnt.TotWhOut | S32 FIX2 ÷100 | MWh | Inps."Cnt.TotWhOut" |
| 78..79 | [68..69] | Cnt.WatthIn | S32 FIX2 ÷100 | MWh | Inps."Cnt.WatthIn" |
| 80..81 | [70..71] | Cnt.WhOut | S32 FIX2 ÷100 | MWh | Inps."Cnt.WhOut" |
| 82..83 | [72..73] | Cnt.FanCab1Tm | U32 FIX0 | s | Inps."Cnt.FanCab1Tm" |
| 84..85 | [74..75] | Cnt.FanCab2Tm | U32 FIX0 | s | Inps."Cnt.FanCab2Tm" |
| 86..87 | [76..77] | Cnt.FanStkTm | U32 FIX0 | s | Inps."Cnt.FanStkTm" |
| 88..89 | [78..79] | Cnt.HtCabTm | U32 FIX0 | s | Inps."Cnt.HtCabTm" |
| 90..91 | [80..81] | Cnt.HtLoExlTmpTm | U32 FIX0 | s | Inps."Cnt.HtLoExlTmpTm" |
| 100..101 | [90..91] | Rio.KeySw | S32 ENUM | — | Inps."Rio.KeySw" |
| 102..103 | [92..93] | WaitGriTm | S32 FIX1 ÷10 | s | Inps.WaitGriTm |
| 104..105 | [94..95] | DevInf.SerNo | U32 FIX0 | — | Inps."DevInf.SerNo" |
| 106..107 | [96..97] | GfdiSwStt | S32 ENUM | — | Inps.GfdiSwStt |
| **108..109** | **[98..99]** | **WSpt readback** | **S32 FIX0** | **kW** | **Inps.WSpt_Fdbk** |
| 110..111 | [100..101] | VAMaxSpt | S32 FIX1 ÷10 | VA | Inps.VAMaxSpt |
| **112..113** | **[102..103]** | **VArSpt readback** | **S32 FIX0** | **kVAr** | **Inps.VarSpt_Fdbk** |
| **114..115** | **[104..105]** | **PFSpt readback** | **S32 FIX4 ÷10000** | **—** | **Inps.PFSpt_Fdbk (Real)** |
| 92..93 | [82..83] | ErrLcn | U32 FIX0 | — | Inv.ErrLcn |
| **94..95** | **[84..85]** | **ErrStt** | **S32 FIX0** | **ENUM** | **Inv.ErrStt** |
| 96..97 | [86..87] | ErrNo | U32 FIX0 | — | Inv.ErrNo |
| **98..99** | **[88..89]** | **OpStt** | **S32 FIX0** | **ENUM** | **Inv.OpStt** |

*Bold rows are consumed by FC_PPC_SkidMapping or drive PPC control decisions.*
*WSpt/VArSpt/PFSpt readbacks are feedback only — stored in Params_Inputs, not Inverter_controller.*

---

### 2.2 FC_InputReg116_L112_To_Inputs — SMA registers 116–227

Array offset: `Reg[0]` = SMA register 116.

| SMA Reg | Reg[] | Field | Scaling | Unit | UDT destination |
|---|---|---|---|---|---|
| 116..117 | [0..1] | TrfPro.Pres | S32 ENUM | — | Inps."TrfPro.Pres" |
| 118..119 | [2..3] | TrfPro.TmpTrp | S32 ENUM | — | Inps."TrfPro.TmpTrp" |
| 120..121 | [4..5] | TrfPro.GasOilLev | S32 ENUM | — | Inps."TrfPro.GasOilLev" |
| 122..123 | [6..7] | TrfPro.TmpWrn | S32 ENUM | — | Inps."TrfPro.TmpWrn" |
| 124..125 | [8..9] | TmpStk1.lgbt | S32 FIX1 ÷10 | °C | Inps."TmpStk1.lgbt" |
| 126..127 | [10..11] | TmpStk2.lgbt | S32 FIX1 ÷10 | °C | Inps."TmpStk2.lgbt" |
| 128..129 | [12..13] | TmpStk3.lgbt | S32 FIX1 ÷10 | °C | Inps."TmpStk3.lgbt" |
| 130..131 | [14..15] | TmpStk1.Pcb | S32 FIX1 ÷10 | °C | Inps."TmpStk1.Pcb" |
| 132..133 | [16..17] | TmpStk2.Pcb | S32 FIX1 ÷10 | °C | Inps."TmpStk2.Pcb" |
| 134..135 | [18..19] | TmpStk3.Pcb | S32 FIX1 ÷10 | °C | Inps."TmpStk3.Pcb" |
| 136..137 | [20..21] | Cnt.YstdWhOut | S32 FIX2 ÷100 | MWh | Inps."Cnt.YstdWhOut" |
| 138..139 | [22..23] | Cpu1UpTime | U32 FIX0 | s | Inps.Cpu1UpTime |
| 140..141 | [24..25] | PvGnd.RisIso | S32 FIX1 ÷10 | kΩ | Inps."PvGnd.RisIso" |
| 142..143 | [26..27] | PresTrf | S32 FIX2 ÷100 | — | Inps.PresTrf |
| 144..145 | [28..29] | PresTrf.ErrStt | S32 ENUM | — | Inps."PresTrf.ErrStt" |
| 146 | [30] | BfpBits | U16 | — | Inps.BfpBits (Int) |
| 147..148 | [31..32] | DcMs.BfpAmp | S32 FIX1 ÷10 | A | Inps."DcMs.BfpAmp" |
| 149..150 | [33..34] | GriMs.Vol.PsNom | S32 FIX4 ÷10000 | pu | Inps."GriMs.Vol.PsNom" |
| 151..152 | [35..36] | Cnt.TotDcWhOut | S32 FIX2 ÷100 | MWh | Inps."Cnt.TotDcWhOut" |
| 153..154 | [37..38] | Cnt.TotAcWhIn | S32 FIX2 ÷100 | MWh | Inps."Cnt.TotAcWhIn" |
| 155..156 | [39..40] | Cnt.DcWhOut | S32 FIX2 ÷100 | MWh | Inps."Cnt.DcWhOut" |
| 157..158 | [41..42] | Cnt.AcWhIn | S32 FIX2 ÷100 | MWh | Inps."Cnt.AcWhIn" |
| 159..160 | [43..44] | DclVolSpt | S32 FIX1 ÷10 | V | Inps.DclVolSpt |
| 163..164 | [47..48] | VolNomSpt | S32 FIX4 ÷10000 | pu | Inps.VolNomSpt |
| 167 | [51] | AuxCtl.LifeSign | U16 | — | Inps."AuxCtl.LifeSign" (Int) |
| 168..169 | [52..53] | InvPwrVolTyp | S32 ENUM | — | Inps.InvPwrVolTyp |
| 170..171 | [54..55] | HzNomSpt | S32 FIX2 ÷100 | Hz | Inps.HzNomSpt |
| **172..173** | **[56..57]** | **WAval** | **S32 FIX4 ÷10000** | **pu (0.0–1.0)** | **Inv.WAval (Real)** |
| **174..175** | **[58..59]** | **VArAval** | **S32 FIX4 ÷10000** | **pu (0.0–1.0)** | **Inv.VArAval (Real)** |
| **176..177** | **[60..61]** | **DrtStt** | **S32 ENUM** | **—** | **Inps.DrtStt** |
| **178..179** | **[62..63]** | **PwrOffReas** | **S32 ENUM** | **—** | **Inv.PwrOffReas** |
| 180..181 | [64..65] | DiagRmgTm | U32 FIX0 | s | Inps.DiagRmgTm |
| 182 | [66] | Rio.Din.FloatCtl.Wa | U16 | — | Inps."Rio.Din.FloatCtl.Wa" (Int) |
| 183 | [67] | Rio.Din.FloatCtl.Err | U16 | — | Inps."Rio.Din.FloatCtl.Err" (Int) |
| **184..185** | **[68..69]** | **WRtg** | **S32 FIX0** | **kW** | **Inps.WRtg** |
| 186 | [70] | Gfdi.AmpPrc | S16 FIX2 ÷100 | A | Inps."Gfdi.AmpPrc" |
| 187 | [71] | Gfdi.AmpErr | S16 FIX2 ÷100 | A | Inps."Gfdi.AmpErr" |
| 188..189 | [72..73] | ActErrNo1 | U32 FIX0 | — | Inps.ActErrNo1 |
| 190..191 | [74..75] | ActErrLcn1 | U32 ENUM | — | Inps.ActErrLcn1 |
| *(192..227)* | *[76..111]* | *ActErrNo2..10 / ActErrLcn2..10* | *U32* | *—* | *Inps.ActErrNo2-10 / ActErrLcn2-10* |

---

## 3. FC_PPC_SkidMapping — The Bridge

Called once per SKID in OB30 (10 calls total), **before** FB_PPC_Controller.
Inputs: `SkidInverter` (Sunny_inverter VAR_IN_OUT), `SkidInputs` (Skid_Parameters_Inputs VAR_INPUT), `CommError` (Bool VAR_INPUT).
In/Out: `Inverter` (Inverter_controller VAR_IN_OUT).

### 3.1 READ direction: SKID DB → Inverter_controller

| Source (Sunny_inverter / Params_Inputs) | Conversion | Destination (Inverter_controller) | Notes |
|---|---|---|---|
| `SkidInverter.OpStt` (DInt ENUM) | =3526 OR 3527 OR 3529 OR 3530 | `Inverter.RemReady` (Bool) | 3526=GridFeed, 3527=FRT, 3529=QonDemand, 3530=RampDown |
| `SkidInverter.ErrStt` (DInt ENUM) | ≠ 307 | `Inverter.Error` (Bool) | 307=Ok |
| `SkidInverter."InvMs.TotW"` (DInt, kW) | direct copy | `Inverter.Wactive` (DInt, kW) | monitoring only |
| `SkidInverter."InvMs.TotVAr"` (DInt, kVAr) | direct copy | `Inverter.Qactive` (DInt, kVAr) | monitoring only |
| `SkidInverter.WAval` (Real, pu 0.0–1.0) | × 10000 → REAL_TO_DINT | `Inverter.WAval` (DInt, FIX4 pu×10000) | **drives PmaxPlant** |
| `SkidInverter.VArAval` (Real, pu 0.0–1.0) | × 10000 → REAL_TO_DINT | `Inverter.VArAval` (DInt, FIX4 pu×10000) | **drives QmaxPlant** |
| `SkidInverter.PwrOffReas` (DInt ENUM) | direct copy | `Inverter.PwrOffReas` (DInt) | online criteria |
| `SkidInputs.DrtStt` (DInt ENUM) | direct copy | `Inverter.DrtStt` (DInt) | derating state |
| `CommError` (Bool) | direct copy | `Inverter.CommError` (Bool) | online criteria |

### 3.2 WRITE direction: Inverter_controller → SKID DB

Skipped entirely when `CommError = TRUE`.

| Source (Inverter_controller) | Conversion | Destination (Sunny_inverter) | SMA register | Notes |
|---|---|---|---|---|
| `Inverter.OperMode` (DInt) | direct | `SkidInverter.RemRdy` (DInt) | written first | SMA interlock: RemRdy before InvOpMod |
| `Inverter.OperMode` (DInt) | direct | `SkidInverter.InvOpMod` (DInt) | written second | 308=Run, 303=Stop |
| `Inverter.WMode` (DInt) | direct | `SkidInverter."GriMng.WMod"` (DInt) | reg 0 group | 1079=WCtlCom, 303=Off |
| `Inverter.WSpt` (DInt, kW) | direct | `SkidInverter.WSpt` (DInt, kW) | reg 108 | active power setpoint |
| `Inverter.VArMode` (DInt) | direct | `SkidInverter."GriMng.VArMod"` (DInt) | reg 0 group | 1072=VArCtlCom, 1075=PFCtlCom, 303=Off |
| `Inverter.VArSpt` (DInt, kVAr) | direct | `SkidInverter.VArSpt` (DInt, kVAr) | reg 112 | reactive power setpoint |
| `Inverter.PFSpt` (DInt, FIX4) | ÷ 10000 → Real | `SkidInverter.PFSpt` (Real, cos φ) | reg 114 | e.g. 9500 DInt → 0.9500 Real |
| `Inverter.ErrClr` (DInt) | direct | `SkidInverter.ErrClr` (DInt) | reg 8 | one-shot: 26 for one scan, then 0 |

**FC_Pack_Write_Regs** then packs the Sunny_inverter write fields into holding register arrays for MB_CLIENT FC16 writes:
- WriteStep 1: regs 0–9 (InvOpMod, RemRdy, VArMod, WMod, ErrClr)
- WriteStep 2: regs 108–109 (WSpt)
- WriteStep 3: regs 112–115 (VArSpt + PFSpt as FIX4 DInt × 10000)

---

## 4. WAval/VArAval Scaling Chain (End-to-End)

This is the most critical scaling path — it drives the entire active and reactive power dispatch.

```
SMA Modbus register 172 (S32 FIX4)
  Raw value example: 8500   (= 85% of rated power available)
        │
        │ FC_InputReg116_L112_To_Inputs
        │   Inv.WAval := DINT_TO_REAL(di32) / 10000.0
        ▼
SKID1.Inverter.WAval  = 0.85  (Real, per-unit, 0.0–1.0)
        │
        │ FC_PPC_SkidMapping
        │   Inverter.WAval := REAL_TO_DINT(SkidInverter.WAval × 10000.0)
        ▼
FB_PPC_Controller_DB.Inverters[0].WAval  = 8500  (DInt, FIX4 pu×10000)
        │
        │ FC_PPC_InverterMonitor
        │   PmaxPlant += DINT_TO_REAL(WAval) / 10000.0 × WRtg_kW
        │                = 8500 / 10000.0 × 4600 kW = 3910 kW
        ▼
PmaxPlant (Real, kW) = sum across all Available inverters
        │
        │ Used as Pmax_disp input to FB_PPC_FreqResponse
        │   Pmax_active = Pmax_disp - dP_at_200mHz_OF
        ▼
FB_PPC_FreqResponse → P_final_kW
        │
        │ FC_PPC_PowerDistribution proportional split
        │   share_i = WAval[i] / ΣWAval[j]    (raw DInt ratio, units cancel)
        │   WSpt[i] = P_final_kW × share_i
        ▼
Inverter_controller.WSpt[0..9]  (DInt, kW) → written to SMA via FC_PPC_SkidMapping
```

Note: in the proportional split, the ÷10000 and ×WRtg_kW factors cancel across numerator and denominator, so raw DInt values are used directly for the ratio — no conversion needed at that stage.

---

## 5. InverterMonitor Online Criteria

`FC_PPC_InverterMonitor` computes `Inverters[i].Available` from six conditions, all of which must be TRUE:

| Condition | Source | Note |
|---|---|---|
| `Enabled` | HMI/SCADA write to DB39 | Operator enable — never overwritten by PPC logic |
| `RemReady` | from OpStt via FC_PPC_SkidMapping | Inverter reports grid-connected remote-ready state |
| `NOT Error` | from ErrStt via FC_PPC_SkidMapping | ErrStt = 307 means no fault |
| `NOT CommError` | from MB_CLIENT error output | Modbus TCP link healthy |
| `PwrOffReas = 0` | from Inv.PwrOffReas via FC_PPC_SkidMapping | No abnormal disconnection reason |
| `ELECTRIC_OK` | from FC_SkidElectricStatus | Breaker / separator / earthing switch status OK |

`Available` is written once per scan and read by all downstream FCs (PowerDistribution, ReactiveControl, FaultHandler) — single source of truth, no re-derivation.

---

## 6. Scaling Conventions Summary

| Signal | SMA Modbus format | Sunny_inverter (SKID DB) | Inverter_controller (PPC) | PPC computation |
|---|---|---|---|---|
| WAval | S32 FIX4 (reg 172) | Real pu (÷10000) | DInt FIX4 (×10000) | ÷10000 × WRtg_kW → kW |
| VArAval | S32 FIX4 (reg 174) | Real pu (÷10000) | DInt FIX4 (×10000) | ÷10000 × WRtg_kW → kVAr |
| InvMs.TotW | S32 FIX0 kW (reg 28) | DInt kW (direct) | DInt kW (direct) | monitoring only |
| InvMs.TotVAr | S32 FIX0 kVAr (reg 30) | DInt kVAr (direct) | DInt kVAr (direct) | monitoring only |
| GriMs.Hz | S32 FIX2 Hz (reg 38) | Real Hz (÷100) | — | read by PPC via GriMs.Hz |
| WSpt | S32 FIX0 kW (reg 108) | DInt kW (direct) | DInt kW (direct) | PPC writes; readback → WSpt_Fdbk |
| VArSpt | S32 FIX0 kVAr (reg 112) | DInt kVAr (direct) | DInt kVAr (direct) | PPC writes; readback → VarSpt_Fdbk |
| PFSpt | S32 FIX4 (reg 114) | Real cos φ (FC_Pack writes ×10000) | DInt FIX4 | readback ÷10000 → PFSpt_Fdbk |
| WRtg | S32 FIX0 kW (reg 184) | DInt kW (Inps.WRtg) | — | DB39.WRtg_kW = 4600 (commissioning constant) |
| OpStt | S32 ENUM (reg 98) | DInt ENUM (direct) | → RemReady Bool | 3526/3527/3529/3530 = TRUE |
| ErrStt | S32 ENUM (reg 94) | DInt ENUM (direct) | → Error Bool | ≠ 307 = TRUE |
| PwrOffReas | S32 ENUM (reg 178) | DInt ENUM (direct) | DInt (direct) | ≠ 0 → not Available |
| DrtStt | S32 ENUM (reg 176) | — | DInt (from Params_Inputs) | derating diagnostic |

---

## 7. Key Constants (DB39 — PPC_Controller)

| Parameter | Value | Source |
|---|---|---|
| WRtg_kW | 4600.0 kW | Read from SMA reg 184 at commissioning; stored in DB39 |
| Pn_MW | 46.0 MW | 10 × WRtg_kW ÷ 1000 |
| Droop_OF_pct | 8.0 % | ANRE Ord.51/2019 Art. 114-115 |
| Droop_UF_pct | 10.0 % | ANRE Ord.51/2019 Art. 118-120 |
