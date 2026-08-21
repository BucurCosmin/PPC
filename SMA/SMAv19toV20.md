# SMA Sunny Central Modbus Interface — v1.9 to v2.0 Deep-Dive Analysis

**Source documents**

- `MODBUS-SCxxxx-TI-en-19.pdf` — Version 1.9
- `MODBUS-SC-TI-en-20.pdf` — Version 2.0, status 20.03.2026

> **Important:** Version 2.0 is marked by SMA as *internal use only – share under NDA and with company watermark*.  
> This analysis is intended for engineering use in the PPC / SCADA / TIA Portal design context.

---

## 1. Executive summary

The transition from **v1.9 to v2.0 is not just a register-list refresh**.

The most important change is that v2.0 formalizes the Sunny Central Modbus interface as a much more explicit **real-time PPC control interface**.

The main architectural evolution is:

```text
v1.9
Modbus interface mainly used for:
- inverter parameterization
- measurements
- existing grid-management functions
- SCADA supervision

v2.0
Modbus interface additionally formalized for:
- fast P setpoint
- fast Q setpoint
- cos(phi) setpoint
- external frequency reference
- external AC-voltage reference
- communication supervision through cyclic setpoints
- fallback behaviour on communication loss
- more explicit plant-controller integration rules
```

For a Siemens TIA Portal PPC, the critical conclusion is:

> **v2.0 should be treated as the normative control profile for modern Sunny Central UP inverters, provided the installed inverter firmware lies in the stated compatibility range.**

The most important control additions are located under **Unit ID 2**, especially:

| Register | Channel | Function |
|---:|---|---|
| 40022 | `VArSpt` | Reactive power setpoint |
| 40023 | `WSpt` | Active power setpoint |
| 40024 | `VArModCfg.PFCtlComCfg.PF` | cos(phi) magnitude |
| 40025 | `VArModCfg.PFCtlComCfg.PFExt` | excitation type |
| 41261 | `HzNomSpt` | frequency reference |
| 41263 | `VolNomSpt` | AC voltage reference |
| 44039 | `WSptMax` | higher-priority P maximum limit |
| 44041 | `WSptMin` | P minimum limit |

This is the core reason v2.0 is much more relevant for a custom PLC-based PPC.

---

# 2. Validity and supported inverter generations

## 2.1 Version 1.9

Version 1.9 applies to a broad mixture of older Sunny Central generations and the first UP units.

Examples include:

- SC 1760-US
- SC 1850-US
- SC 2000-US
- SC 2000-EV-US
- SC 2200 / 2200-US
- SC 2475
- SC 2500-EV / EV-US
- SC 2750-EV / EV-US
- SC 3000-EV
- SC 4000 UP / UP-US
- SC 4200 UP / UP-US
- SC 4400 UP / UP-US
- SC 4600 UP / UP-US

Minimum firmware in the document:

```text
from firmware version 1.0
```

Reference: **v1.9, Section 1.1, page 5**

---

## 2.2 Version 2.0

Version 2.0 moves the scope to the modern Sunny Central UP platform:

- SC 2660 UP
- SC 2800 UP
- SC 2930 UP
- SC 3060 UP
- SC 4000 UP
- SC 4200 UP
- SC 4400 UP
- SC 4600 UP
- 2-stack variants
- 3-stack variants
- corresponding US variants

Minimum firmware:

```text
from firmware version 10.03.xx.R
```

Reference: **v2.0, Section 1.1, page 5**

### Engineering consequence

Do not assume that a v1.9 implementation can simply be copied register-for-register into a modern v2.0 plant.

Many legacy addresses remain compatible, but the control philosophy, supported inverter generation and PPC integration guidance have evolved substantially.

---

# 3. Core Modbus transport behaviour — mostly unchanged

The basic Modbus mechanics remain familiar between v1.9 and v2.0.

## 3.1 Supported transport

Both versions support:

- Modbus TCP
- Modbus UDP

The access model remains:

```text
TCP -> read/write
UDP -> write-only
```

---

## 3.2 Supported function codes

The main function codes remain unchanged:

| Function | Function code | Data volume |
|---|---:|---:|
| Read Coils | FC01 | 1...2000 |
| Read Discrete Inputs | FC02 | 1...2000 |
| Read Holding Registers | FC03 | 1...123 |
| Read Input Registers | FC04 | 1...125 |
| Write Single Coil | FC05 | 1 |
| Write Single Holding Register | FC06 | 1 |
| Write Multiple Coils | FC15 | 1...1968 |
| Write Multiple Registers | FC16 | 1...123 |

References:

- v1.9: Section 3.8, page 14
- v2.0: Section 3.8, page 13

---

## 3.3 Endianness

Both versions use:

```text
Motorola format / Big Endian
```

For multi-register data, the higher-order data is transmitted first.

This remains directly relevant for Siemens S7-1500 implementation.

Typical conversion logic must account for:

```text
Modbus registers
WORD[0]
WORD[1]
   ↓
DWORD / DINT
   ↓
apply scaling
```

---

# 4. Unit ID structure — mostly preserved

The global Unit ID architecture remains largely unchanged.

| Unit ID | Meaning |
|---:|---|
| 2 | System parameters / plant-level data |
| 3 | Inverter |
| 4...15 | Reserved |
| 16...31 | External devices |
| 32 | Left DC module |
| 33 | Right DC module |
| 34 | Center DC module, where applicable |
| 102 | SMA plant controller / plant manager |
| 120...169 | SMA String Monitor |
| 255 | Not directly addressable |

One visible wording evolution is Unit ID 102:

### v1.9

```text
SMA Power Plant Controller
```

### v2.0

```text
SMA Power Plant Controller or SMA Power Plant Manager
```

This is a small wording change, but it reflects SMA's updated plant-level architecture.

References:

- v1.9: Section 3.6.1, page 12
- v2.0: Section 3.6.1, page 11

---

# 5. Major architectural addition in v2.0: Setpoints / Parameters / Measurements

Version 2.0 introduces a new explicit functional grouping under Section 3.11:

```text
S = Setpoints
P = Parameters
M = Measured values
```

This distinction is one of the most important changes in the document.

Reference: **v2.0, Section 3.11, pages 16-17**

---

## 5.1 Setpoints

Setpoints define the **current operating point**.

SMA specifically highlights:

```text
WSpt
VArSpt
```

as critical signals.

The document explains that these signals are optimized for frequent cyclic transmission.

Typical cycle:

```text
~100 ms
```

Minimum allowed cycle:

```text
not less than 50 ms
```

The important detail is that these signals are also used as a **communication sign-of-life**.

Therefore:

> `WSpt` and `VArSpt` should continue to be transmitted independently of the inverter's current operating state.

This is a direct PPC implementation requirement.

---

## 5.2 Parameters

Parameters are settings.

Version 2.0 explicitly warns that writing parameters updates the inverter's non-volatile settings database.

Therefore parameters should only be written when a configuration change is actually required.

Correct architecture:

```text
SETPOINT
  -> cyclic

PARAMETER
  -> event driven

MEASUREMENT
  -> cyclic read
```

This is a very important distinction for TIA Portal.

---

## 5.3 Measurements

Measured values are input registers.

They represent:

- current operating state
- electrical measurements
- status information

Version 2.0 states that the internal measured-value update cycle is approximately:

```text
100 ms
```

A measurement polling strategy should therefore normally be aligned to this update interval or a multiple of it.

---

# 6. Unit ID 2 becomes a real PPC runtime control interface

This is the biggest functional difference between the two versions.

---

## 6.1 Unit ID 2 in v1.9

Version 1.9 mainly exposes general system functions such as:

| Register | Description |
|---:|---|
| 1104 | plant/system time |
| 1106 | time zone |

The system-level input registers contain:

- profile version
- communication-interface device ID
- Modbus change counter
- UTC time

Reference: **v1.9, Section 5.2, page 21**

There is no equivalent v1.9 Unit ID 2 fast control block comparable to v2.0.

---

## 6.2 Unit ID 2 in v2.0

Version 2.0 adds a dedicated setpoint area.

### New runtime setpoints

| Address | Channel | Description | Type | Format |
|---:|---|---|---|---|
| 40018 | `FstStop` | inverter disconnection | U32 | ENUM |
| 40022 | `VArSpt` | reactive power setpoint | S16 | FIX2 % |
| 40023 | `WSpt` | active power setpoint | S16 | FIX2 % |
| 40024 | `VArModCfg.PFCtlComCfg.PF` | displacement power factor | U16 | FIX4 |
| 40025 | `VArModCfg.PFCtlComCfg.PFExt` | excitation type | U32 | ENUM |
| 41261 | `HzNomSpt` | nominal frequency / frequency setpoint | U32 | FIX3 Hz |
| 41263 | `VolNomSpt` | nominal AC voltage / voltage setpoint | U16 | FIX4 p.u. |
| 44039 | `WSptMax` | higher-priority active-power upper limit | S32 | FIX2 % |
| 44041 | `WSptMin` | active-power lower limit | S32 | FIX2 % |

References: **v2.0, Section 5.2.1, pages 21-22**

This is the clearest indication that v2.0 is intended to support an external PPC directly.

---

# 7. Active power setpoint — `WSpt`

Register:

```text
Unit ID: 2
Address: 40023
Channel: WSpt
```

Function:

```text
active power setpoint P
```

The setpoint is expressed as a percentage of the active-power reference value.

The reference is related to:

```text
WExlSpt.RefVal
```

and the reference selection is configured via:

```text
WExlSpt.RefMod
```

### Sign convention

v2.0 explicitly generalizes the active-power interface:

```text
positive P
-> generator / discharge mode

negative P
-> load / charge mode
```

This is an important evolution because the interface is clearly being generalized toward:

- PV
- BESS
- hybrid operation

rather than only classic PV generation.

---

# 8. Reactive power setpoint — `VArSpt`

Register:

```text
Unit ID: 2
Address: 40022
Channel: VArSpt
```

Function:

```text
reactive power setpoint Q
```

Format:

```text
S16
FIX2
%
```

The value is relative to:

```text
VArExlSpt.RefVal
```

with the reference mode controlled by:

```text
VArExlSpt.RefMod
```

Typical range:

```text
-100.00 % ... +100.00 %
```

The sign is defined by SMA in terms of:

```text
underexcited
no reactive power
overexcited
```

For a PPC, it is important to define and test the exact sign convention at commissioning so that:

```text
positive Q command
```

has the expected inductive/capacitive effect at the PCC.

---

# 9. New explicit voltage setpoint — `VolNomSpt`

This is one of the most important additions for voltage-control implementation.

Register:

```text
Unit ID: 2
Address: 41263
Channel: VolNomSpt
```

Description in v2.0:

```text
Nominal AC voltage for voltage-dependent reactive power control / AC voltage setpoint
```

Type:

```text
U16
```

Scaling:

```text
10000
```

Format:

```text
FIX4
```

Unit:

```text
p.u.
```

Reference: **v2.0, Section 5.2.1, page 22**

---

## 9.1 Example scaling

```text
1.0000 p.u. -> raw value 10000
1.0200 p.u. -> raw value 10200
0.9800 p.u. -> raw value 9800
```

This confirms that a custom PLC-based PPC can send an explicit AC-voltage reference to the Sunny Central.

---

## 9.2 Important distinction: U setpoint does not mean "force grid voltage"

The Sunny Central is still a grid-following converter in normal operation.

The logic is conceptually:

```text
Uref
  ↓
internal voltage/reactive-power controller
  ↓
Q response
  ↓
local AC voltage influence
```

The inverter cannot arbitrarily impose the grid voltage.

Therefore the actual plant-level voltage-regulation architecture still needs to consider:

- PCC voltage
- transformer impedance
- cable impedance
- inverter terminal voltage
- Q capability
- voltage droop / plant controller gains

---

# 10. Frequency setpoint — `HzNomSpt`

v2.0 also adds:

```text
Unit ID: 2
Address: 41261
Channel: HzNomSpt
```

Function:

```text
nominal frequency for frequency-dependent active-power control
/
frequency setpoint
```

Format:

```text
U32
FIX3
Hz
```

This gives the external PPC another explicit runtime reference point.

Reference: **v2.0, Section 5.2.1, page 22**

---

# 11. cos(phi) runtime control becomes much clearer

Version 2.0 introduces a dedicated pair of plant-control registers:

```text
40024 -> cos(phi) magnitude
40025 -> excitation type
```

This is documented in the new Section 5.2.3:

```text
Power Control with cos φ and Excitation Type
```

Reference: **v2.0, Section 5.2.3, page 23**

SMA explicitly states that this mode is active when:

```text
GriMng.VArMod = PFCtlCom
```

This confirms a clean separation between:

```text
configuration parameter
GriMng.VArMod
```

and:

```text
runtime setpoint
40024 / 40025
```

---

# 12. Important PPC rule: do not cyclically rewrite mode parameters

This is one of the most important implementation conclusions.

For example:

```text
GriMng.VArMod
```

is a parameter.

`VArSpt` is a setpoint.

Bad implementation:

```text
every 100 ms:
    write GriMng.VArMod
    write VArSpt
```

Recommended implementation:

```text
on mode change:
    write GriMng.VArMod once

every 100 ms:
    write VArSpt
```

The same concept applies to:

- active-power mode
- PF mode
- voltage-control mode
- ramp configuration
- fallback settings

---

# 13. Existing voltage mode parameter remains on Unit ID 3

Both v1.9 and v2.0 contain:

```text
Unit ID: 3
Address: 28
Channel: GriMng.VolNomMod
```

Description:

```text
Grid management services: setpoint via AC voltage
```

This means the inverter already had a mode selector associated with AC-voltage-based control.

The important v2.0 improvement is that the external voltage reference itself is now explicitly exposed on:

```text
Unit ID 2
Register 41263
VolNomSpt
```

So the architecture becomes much clearer:

```text
configuration:
    GriMng.VolNomMod

runtime:
    VolNomSpt
```

---

# 14. P maximum / minimum priority limits

Version 2.0 introduces two important runtime limit registers.

## 14.1 WSptMax

```text
Unit ID: 2
Address: 44039
Channel: WSptMax
```

Purpose:

```text
higher-priority limitation of WSpt
```

Communication use must be enabled by:

```text
GriMng.WMaxMod
```

---

## 14.2 WSptMin

```text
Unit ID: 2
Address: 44041
Channel: WSptMin
```

Purpose:

```text
lower limitation of WSpt
```

Communication use must be enabled by the corresponding configuration.

---

## 14.3 PPC implication

This enables a command hierarchy such as:

```text
normal plant dispatch
       |
       v
     WSpt

higher-priority active-power ceiling
       |
       v
    WSptMax

lower operating boundary
       |
       v
    WSptMin
```

Example:

```text
PPC desired active power = 85 %
grid operator limit       = 60 %

WSpt    = 85 %
WSptMax = 60 %
```

The inverter should remain limited to the higher-priority 60 % boundary.

This is much cleaner than overloading one single P command for all operating constraints.

---

# 15. New reference values for generic PPC scaling

Version 2.0 adds important Unit ID 3 measured values that make a generic PPC implementation much easier.

Examples include:

| Address | Channel | Meaning |
|---:|---|---|
| 268 | `VArExlSpt.RefVal` | Q setpoint reference value |
| 269 | `WExlSpt.RefVal` | P setpoint reference value |
| 270 | `VARtg` | rated apparent power |
| 272 | `InvTyp` | inverter type |
| 274 | `VArRtg` | rated reactive power |

These values allow the PLC to normalize commands dynamically.

Instead of hard-coding inverter ratings:

```text
Pcmd_pct := Pcmd_kW / 4400.0 * 100.0
```

a generic implementation can use:

```text
Pcmd_pct :=
    Pcmd_kW /
    WExlSpt_RefVal_kW *
    100.0
```

and:

```text
Qcmd_pct :=
    Qcmd_kvar /
    VArExlSpt_RefVal_kvar *
    100.0
```

This is especially useful for a project with four Sunny Central inverters that may not be identical or may use stacked variants.

---

# 16. More explicit inverter type support

Version 2.0 expands the conceptual inverter-type model.

The interface distinguishes among categories such as:

```text
PV inverter
battery inverter
PV + battery inverter
```

This matches the generalized positive/negative P interface.

This suggests a broader control platform design than the older v1.9 generation.

For a generic TIA driver, this is useful because the inverter instance can potentially self-identify and load the appropriate capability model.

---

# 17. Communication-loss / fallback functionality is significantly expanded

This is one of the most important practical improvements in v2.0.

New or expanded parameters include:

| Address | Channel | Function |
|---:|---|---|
| 121 | `WGraFlb` | active-power gradient during communication fallback |
| 123 | `VArGraFlb` | reactive-power gradient during communication fallback |
| 127 | `ExlConn` | external release for grid connection |
| 129 | `GriMng.ExtdFlbErrClr` | acknowledge extended fallback error |

There are also related voltage feedback/fallback limits and diagnostic registers.

The important control concept becomes:

```text
normal PPC operation
       ↓
cyclic WSpt / VArSpt
       ↓
communications lost
       ↓
SMA fallback logic
       ↓
P fallback ramp
Q fallback ramp
       ↓
fallback status feedback
```

This is a much more deterministic strategy than simply declaring:

```text
Modbus timeout -> inverter unavailable
```

---

# 18. New extended fallback status

Version 2.0 adds:

```text
Unit ID: 3
Input register: 286
Channel: GriMng.ExtdFlbStt
```

This exposes the state of the extended fallback function.

The reported states include concepts related to:

- normal operation
- inactive timeout
- longer fallback timeout
- short fallback timeout
- fallback/error state

This gives the external PPC a direct indication that the inverter has entered communication-loss handling.

For FAT and SAT this is very valuable.

---

# 19. New P-limit feedback

Version 2.0 adds measured feedback for the internally effective active-power bounds:

```text
338 -> WSptMin
339 -> WSptMax
```

These are useful for determining the actual permitted operating region.

The PPC dispatcher can therefore use a more realistic model:

```text
P_available_i
P_min_i
P_max_i
```

rather than:

```text
0 ... rated power
```

for every inverter under all conditions.

---

# 20. Expanded environmental diagnostics

Version 2.0 adds more environmental and internal-condition signals.

Examples:

```text
340 RlHmdtRio
341 RlHmdtAcc
342 RlHmdtDcc
```

Relative humidity in different internal areas.

Additional signals include:

```text
343 DrtExlStt
```

external/environmental derating state.

And dehumidification-related channels such as:

```text
345 HmdtCtl.TmCnt
347 HmdtCtl.Stt
```

These are not part of the fast PPC loop, but are useful for:

- SCADA
- maintenance
- availability diagnostics
- derating explanation

---

# 21. New switching-cycle counters

Version 2.0 exposes additional lifetime / switching counters.

Examples include:

```text
290 Cnt.DcSw1
292 Cnt.DcSw2
294 Cnt.DcSw3
296 Cnt.AcSw
```

and corresponding overvoltage-related counters such as:

```text
330 Cnt.DcSw1Uvr
332 Cnt.DcSw2Uvr
334 Cnt.DcSw3Uvr
336 Cnt.AcSwUvr
```

These are suitable for slow SCADA polling, not for the control loop.

Recommended polling interval:

```text
10...60 s
```

or slower depending on plant requirements.

---

# 22. New DC-to-ground measurements

Version 2.0 adds measurements such as:

```text
276 DcMs.Vol.PosGnd
278 DcMs.Vol.NegGnd
```

These provide DC bus potential relative to ground.

They are useful for:

- insulation monitoring
- ground fault diagnostics
- maintenance
- DC-side troubleshooting

---

# 23. Main real-time electrical measurements remain familiar

The important electrical process variables remain broadly compatible with v1.9.

Examples include:

```text
InvMs.TotW
InvMs.TotVAr
InvMs.PF
GriMs.V.PhsAB
GriMs.V.PhsBC
GriMs.V.PhsCA
```

This means an existing measurement FB can likely be adapted rather than completely rewritten.

The main difference is that v2.0 gives the external PPC a much clearer and more formal command interface.

---

# 24. Legacy Unit ID 3 control parameters are largely preserved

The traditional Unit ID 3 parameter range remains recognizable.

Examples:

```text
0   InvOpMod
2   RemRdy
4   GriMng.VArMod
6   GriMng.WMod
8   ErrClr
10  VADrtPriMod
12  WGraMod
14  WGra
16  VArGraMod
18  VArGra
20  ErrClr.ProErr
22  GriMng.InvVArMod
28  GriMng.VolNomMod
```

This is important because it means an older v1.9 integration still provides useful knowledge.

However, v2.0 changes the recommended **usage pattern**:

```text
Unit ID 3
-> configuration / parameters / measurements

Unit ID 2
-> fast external PPC setpoints
```

That separation should be reflected in the TIA architecture.

---

# 25. Frequency-control configuration receives an explicit prerequisite

Version 2.0 adds an important qualification around frequency-control configuration.

The channel:

```text
WCtlHzMod
```

already existed.

v2.0 clarifies that corresponding configuration through Modbus can depend on:

```text
WCtlHz.CfgMod
```

being enabled/configured appropriately in the inverter.

Engineering implication:

```text
successful Modbus write
```

does not automatically guarantee:

```text
functional behaviour
```

if the commissioning-level configuration has not enabled the function.

This is a key SAT consideration.

---

# 26. Existing P(U) function is retained

Both versions contain the active-power-versus-voltage function.

Representative channels include:

```text
WCtlVol.Ena
WCtlVol.Vol1
WCtlVol.Vol2
WCtlVol.Vol3
WCtlVol.Vol4
WCtlVol.W1
WCtlVol.W2
WCtlVol.W3
WCtlVol.W4
```

This is:

```text
P(U)
```

meaning active power changes as a function of measured grid voltage.

This must not be confused with:

```text
VolNomSpt
```

which is an external voltage reference used in voltage-dependent reactive-power control.

The two concepts are different:

```text
P(U)
grid voltage
    ↓
active power modification
```

versus:

```text
Uref
    ↓
reactive-power / voltage controller
    ↓
Q response
```

---

# 27. Existing Q(U) functionality remains

The existing:

```text
VArCtlVol....
```

family remains available for autonomous voltage-dependent reactive-power control.

This gives three possible voltage/reactive control architectures:

## Architecture A — central PPC calculates Q

```text
PCC voltage
    ↓
TIA voltage PI
    ↓
Q demand
    ↓
Q dispatch
    ↓
VArSpt
```

## Architecture B — PPC sends U reference

```text
PPC Uref
    ↓
VolNomSpt
    ↓
SMA internal voltage/Q control
```

## Architecture C — inverter local Q(U)

```text
local AC voltage
    ↓
configured Q(U) curve
    ↓
reactive power
```

For a utility-scale plant, the final selection should consider where voltage is regulated and measured.

---

# 28. Voltage control — important plant-level engineering consideration

The existence of `VolNomSpt` does not automatically mean that direct inverter U-reference control is the best plant-level PPC strategy.

A utility-scale plant is usually required to control voltage at the:

```text
PCC / POC
```

while the inverter sees:

```text
its local LV/MV terminal voltage
```

Between the inverter and PCC there may be:

- inverter transformer
- MV collector cable
- MV switchgear
- main transformer
- grid impedance

Therefore:

```text
U_inverter_terminal != U_PCC
```

especially under high reactive-power flow.

This means a central PPC may still need to close the loop at the PCC, even if the inverter supports a local voltage reference.

---

# 29. String Monitor documentation changes

Version 1.9 contains a dedicated section for:

```text
SMA String-Monitor Parameters
Unit ID 120...169
```

and also contains a specific procedure for obtaining the assigned Unit IDs.

Version 2.0 still reserves:

```text
120...169
```

for SMA String Monitors, but the detailed register documentation is no longer presented in the same way.

Important conclusion:

> Do not interpret this as proof that String Monitor support disappeared.

The safer interpretation is:

> the detailed SSM mapping is no longer part of this Sunny Central v2.0 document and should be obtained from the current SMA SSM documentation/profile.

---

# 30. Zone monitoring / DC module documentation changes

Both documents retain Unit IDs 32, 33 and 34 for DC-zone-related functions.

Version 2.0 presents more explicit information regarding physical connection availability for certain fused-input configurations.

This is useful because some logical registers may correspond to hardware inputs that are not physically available in a given DC-coupling configuration.

Engineering rule:

```text
do not assume every documented zone current channel is valid for every fuse arrangement
```

---

# 31. External Moxa device support

The external Modbus master profile functionality remains.

Supported Moxa ioLogik devices include:

- E1210-T
- E1240-T
- E1242-T
- E1260-T

Version 2.0 presents this more consistently.

This does not materially affect the PPC control loop, but it matters for auxiliary IO integration.

---

# 32. User-defined Modbus profile remains available

Both versions support a user-defined Modbus profile.

This allows relevant registers to be remapped into a more convenient consecutive address range.

Potential advantage:

```text
fewer Modbus transactions
```

For example:

```text
native profile:
multiple address ranges / Unit IDs

custom profile:
compact consecutive block
```

However, for initial PPC commissioning it is usually safer to use the native SMA addresses because it makes troubleshooting easier.

During FAT/SAT:

```text
TIA tag
    ↕
SMA documented register
    ↕
SMA service tool
```

should remain directly comparable.

---

# 33. New integration guidance in v2.0

Version 2.0 adds explicit integration guidance that is highly relevant to PLC programming.

The key operational rules are:

| Topic | v2.0 guidance |
|---|---|
| `WSpt` | send cyclically |
| `VArSpt` | send cyclically |
| reason | also used for communication monitoring |
| normal setpoint cycle | approximately 100 ms |
| absolute minimum cycle | 50 ms |
| maximum setpoint rate | approximately 20 writes/s |
| measured values | typically no faster than 10 Hz |
| parameters | write only when required |
| 32-bit values | process/write the complete pair of 16-bit registers |
| ENUM | only valid documented values |
| Unit IDs | must be respected |

This guidance should directly define the TIA communication scheduler.

---

# 34. Recommended TIA Portal communication architecture

For each inverter:

```text
FB_SMA_SC
```

should be divided logically into different service groups.

---

## 34.1 Fast write group

Recommended cycle:

```text
100 ms
```

Signals:

```text
WSpt
VArSpt
```

plus mode-dependent runtime commands such as:

```text
VolNomSpt
PF setpoint
excitation type
```

where required.

---

## 34.2 Fast read group

Recommended cycle:

```text
100 ms
```

Typical signals:

```text
P actual
Q actual
U
f
cos(phi)
operating state
```

---

## 34.3 Medium-speed status group

Recommended cycle:

```text
500 ms ... 1 s
```

Typical signals:

```text
availability
derating
Pmin
Pmax
fallback status
alarm summary
remote readiness
```

---

## 34.4 Slow diagnostics group

Recommended cycle:

```text
10 ... 60 s
```

Typical signals:

```text
switching counters
humidity
dehumidification
temperatures
firmware
maintenance data
```

---

## 34.5 Parameter service

Parameters should not run continuously.

Recommended design:

```text
parameter-change queue
```

Example:

```text
HMI requests Q-control mode
       ↓
queue command
       ↓
write GriMng.VArMod
       ↓
verify readback
       ↓
return success/failure
```

This is much better than continuously mirroring a parameter DB to the inverter.

---

# 35. 32-bit register handling

Many SMA values are 32-bit and therefore occupy two Modbus registers.

Recommended rule:

```text
never write one half of a 32-bit value independently
```

Prefer one complete block write.

Example:

```text
FC16
start address N
length 2 registers
```

This avoids transient invalid values.

---

# 36. ENUM validation

v2.0 makes it clear that only defined ENUM codes are valid.

Therefore the TIA project should not expose raw unrestricted integer writes to HMI users.

Recommended flow:

```text
HMI selection
    ↓
PLC enum
    ↓
validation
    ↓
SMA register
```

This is particularly important for:

```text
GriMng.VArMod
GriMng.WMod
GriMng.VolNomMod
InvOpMod
RemRdy
```

---

# 37. Proposed four-inverter PPC structure

For four Sunny Central inverters:

```text
INV1
INV2
INV3
INV4
```

instantiate:

```text
FB_SMA_SC[1]
FB_SMA_SC[2]
FB_SMA_SC[3]
FB_SMA_SC[4]
```

Above them, create plant-level blocks:

```text
FB_PPC_P
FB_PPC_Q
FB_PPC_U
FB_PPC_PF
FB_PPC_Frequency
FB_PPC_Dispatch
FB_PPC_Fallback
FB_PPC_Sequence
```

---

# 38. Suggested four control modes

## 38.1 P control

Configuration:

```text
GriMng.WMod
```

Runtime:

```text
WSpt
```

---

## 38.2 Q control

Configuration:

```text
GriMng.VArMod = communication-based Q control
```

Runtime:

```text
VArSpt
```

---

## 38.3 PF control

Configuration:

```text
GriMng.VArMod = PFCtlCom
```

Runtime:

```text
40024 -> cos(phi)
40025 -> excitation type
```

---

## 38.4 Voltage control

Configuration concept:

```text
GriMng.VolNomMod
```

Runtime:

```text
VolNomSpt
```

This control path is strongly supported by the v2.0 register definitions, but the exact activation/commissioning sequence should be validated against the installed Sunny Central firmware before SAT.

---

# 39. Communication-loss strategy for the PPC

The final PPC should explicitly test and manage communication loss.

Recommended concept:

```text
PPC healthy
    ↓
WSpt + VArSpt transmitted cyclically
    ↓
communication interrupted
    ↓
SMA detects missing setpoint heartbeat
    ↓
fallback behaviour
    ↓
WGraFlb / VArGraFlb
    ↓
GriMng.ExtdFlbStt changes
    ↓
SCADA alarm
    ↓
communication restored
    ↓
controlled return to live setpoints
```

This behaviour should be included in FAT/SAT test cases.

---

# 40. Functional delta summary

| Area | v1.9 | v2.0 | PPC impact |
|---|---|---|---|
| Product generation | older + first UP | modern UP / stacks | High |
| Minimum firmware | 1.0 | 10.03.xx.R | Critical |
| Dedicated fast P setpoint | not explicit at Unit ID 2 | `WSpt 40023` | Critical |
| Dedicated fast Q setpoint | not explicit at Unit ID 2 | `VArSpt 40022` | Critical |
| Voltage reference | not explicit as Unit ID 2 runtime command | `VolNomSpt 41263` | Critical |
| Frequency reference | not explicit there | `HzNomSpt 41261` | High |
| PF runtime command | less explicit | 40024 + 40025 | High |
| Priority P limits | limited | 44039 / 44041 | High |
| P/Q sign-of-life | not formally emphasized | explicit | Critical |
| Setpoint timing | generic | 50...100 ms guidance | Critical |
| Parameter write philosophy | less explicit | explicit non-volatile warning | Critical |
| Fallback ramps | limited | W/Q fallback gradients | Critical |
| Fallback state | limited | explicit extended fallback status | Critical |
| P/Q reference values | less PPC-friendly | explicit dynamic reference values | Critical |
| BESS/hybrid orientation | limited | much clearer | Medium |
| Environmental diagnostics | limited | expanded | Medium |
| Switching counters | limited | expanded | Low/Medium |
| String Monitor detail | included | moved out of main profile | Medium |
| Integration section | limited | explicit integration guidance | Critical |

---

# 41. Bottom-line engineering conclusion

The move from SMA Modbus v1.9 to v2.0 is best understood as a transition from:

```text
"inverter Modbus interface"
```

to a much more clearly defined:

```text
"external PPC-to-inverter control interface"
```

The evidence is the combination of:

```text
dedicated P setpoint
dedicated Q setpoint
external U setpoint
external frequency reference
PF command
setpoint priority limits
cyclic communication requirements
communication sign-of-life
reference-value feedback
fallback configuration
fallback status
integration timing rules
```

For a custom Siemens TIA Portal PPC controlling four Sunny Central inverters, the v2.0 profile allows a much cleaner architecture.

The recommended design principle is:

```text
Unit ID 2
-> fast runtime plant-control commands

Unit ID 3
-> inverter modes
-> configuration
-> measurements
-> limits
-> availability
-> fallback state
-> diagnostics
```

The most important new register for the previous voltage-control discussion is:

```text
Unit ID 2
Address 41263
VolNomSpt
U16
FIX4
p.u.
```

Therefore a direct external AC-voltage reference is explicitly available in v2.0.

---

# 42. Recommended next engineering step

The next document should convert this protocol analysis into a concrete Siemens implementation specification containing:

1. exact register list for the four inverters;
2. read/write cycle for each register group;
3. Modbus function code per block;
4. TIA data types;
5. Big-Endian conversion rules;
6. scaling formulas;
7. mode-change state machine;
8. P/Q/U/PF command logic;
9. communication watchdog;
10. fallback handling;
11. plant-level dispatch across four inverters;
12. FAT/SAT test matrix.

A practical file structure could be:

```text
SMA_PPC_TIA/
├── SMA_Modbus_Map.md
├── SMA_UDT_Definition.md
├── SMA_CommScheduler.md
├── PPC_ControlModes.md
├── PPC_Fallback.md
└── PPC_FAT_SAT.md
```

This would turn the v2.0 analysis into a directly implementable TIA Portal design.
