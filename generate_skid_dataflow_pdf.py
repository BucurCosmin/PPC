"""Generate SKID_DataFlow.pdf — SKID Modbus Comms <-> FB_PPC_Controller data flow."""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER

OUTPUT = r"c:\Users\cosmi\OneDrive\WORK\PPC_ENERGY\SKID_DataFlow.pdf"

C_BLUE   = colors.HexColor("#1F4E79")
C_LBLUE  = colors.HexColor("#2E75B6")
C_HEADER = colors.HexColor("#D6E4F0")
C_ALT    = colors.HexColor("#F2F7FB")
C_WHITE  = colors.white
C_BLACK  = colors.black
C_GREEN  = colors.HexColor("#E2EFDA")
C_YELLOW = colors.HexColor("#FFF2CC")
C_ORANGE = colors.HexColor("#FCE4D6")
C_GREY   = colors.HexColor("#F5F5F5")

PAGE_W, PAGE_H = A4
MARGIN = 1.8 * cm

base = getSampleStyleSheet()

def style(name, parent="Normal", **kw):
    return ParagraphStyle(name, parent=base[parent], **kw)

S_TITLE = style("T",  fontSize=18, textColor=C_BLUE, fontName="Helvetica-Bold",
                spaceAfter=4, alignment=TA_CENTER)
S_SUB   = style("Su", fontSize=10, textColor=C_LBLUE, spaceAfter=2,
                alignment=TA_CENTER)
S_H1    = style("H1", fontSize=12, textColor=C_WHITE, fontName="Helvetica-Bold",
                spaceAfter=6, spaceBefore=12, backColor=C_BLUE,
                borderPadding=(4, 6, 4, 6))
S_H2    = style("H2", fontSize=10, textColor=C_BLUE, fontName="Helvetica-Bold",
                spaceAfter=4, spaceBefore=8)
S_BODY  = style("B",  fontSize=9,  spaceAfter=4, leading=13)
S_NOTE  = style("N",  fontSize=8,  textColor=colors.HexColor("#555555"),
                fontName="Helvetica-Oblique", spaceAfter=4, leading=12)
S_CODE  = style("Co", fontSize=7.5, fontName="Courier",
                backColor=C_GREY, spaceAfter=4, leading=11,
                leftIndent=10, borderPadding=(4, 4, 4, 4))
S_TH    = style("TH", fontSize=8,  textColor=C_WHITE, fontName="Helvetica-Bold",
                alignment=TA_CENTER, backColor=C_LBLUE, leading=11)
S_TD    = style("TD", fontSize=8,  leading=11)
S_TDC   = style("TC", fontSize=8,  leading=11, alignment=TA_CENTER)
S_TDSM  = style("TS", fontSize=7.5, leading=10)
S_TDCSM = style("TCS",fontSize=7.5, leading=10, alignment=TA_CENTER)

def p(text, s=S_BODY):  return Paragraph(text, s)
def h1(t):              return Paragraph(t, S_H1)
def h2(t):              return Paragraph(t, S_H2)
def sp(n=6):            return Spacer(1, n)
def hr():               return HRFlowable(width="100%", thickness=0.5,
                                          color=C_LBLUE, spaceAfter=4, spaceBefore=4)

def th(t):  return Paragraph(t, S_TH)
def td(t):  return Paragraph(t, S_TD)
def tdc(t): return Paragraph(t, S_TDC)
def tdsm(t):  return Paragraph(t, S_TDSM)
def tdcsm(t): return Paragraph(t, S_TDCSM)

def table(data, col_widths, row_colors=None):
    t = Table(data, colWidths=col_widths, repeatRows=1)
    cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), C_LBLUE),
        ("TEXTCOLOR",  (0, 0), (-1, 0), C_WHITE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, C_ALT]),
        ("GRID",       (0, 0), (-1, -1), 0.4, colors.HexColor("#C0C0C0")),
        ("VALIGN",     (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",(0, 0), (-1, -1), 4),
        ("RIGHTPADDING",(0,0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING",(0,0),(-1, -1), 3),
    ]
    if row_colors:
        for row_idx, col, bg in row_colors:
            cmds.append(("BACKGROUND", (0, row_idx), (-1, row_idx), bg))
    t.setStyle(TableStyle(cmds))
    return t

# ─────────────────────────────────────────────────────────────────────────────
doc = SimpleDocTemplate(OUTPUT, pagesize=A4,
                        leftMargin=MARGIN, rightMargin=MARGIN,
                        topMargin=MARGIN, bottomMargin=MARGIN)
story = []

# ── Cover ─────────────────────────────────────────────────────────────────────
story += [
    sp(20),
    p("CEF TANDAREI 46 MW — PPC SYSTEM", S_SUB),
    sp(6),
    p("SKID Modbus Communication", S_TITLE),
    p("↔  FB_PPC_Controller Data Flow", S_TITLE),
    sp(8),
    p("Siemens S7-1500 · TIA Portal SCL · SMA SC 4600 UP", S_SUB),
    p("Version: 2026-07-11", S_SUB),
    sp(16),
    hr(),
    sp(8),
]

# ── §1 Architecture ──────────────────────────────────────────────────────────
story += [h1("1.  Architecture Overview")]
story += [p(
    "Each SMA SC 4600 UP inverter has a dedicated SKID DB (SKID1 … SKID10). "
    "The PPC controller maintains a 10-element <b>Inverter_controller</b> array "
    "inside <b>FB_PPC_Controller_DB</b>. Two function blocks bridge them every "
    "100 ms OB30 scan — reading Modbus data into the SKID DB and mapping it "
    "to/from the PPC inverter array."
)]

arch = [
    "SMA Inverter (Modbus TCP)  →  [FC04 reads, two blocks/scan]",
    "SKIDx.db",
    "  ├─ Inverter       : Sunny_inverter         ← FC_InputReg10_L106   (regs 10–115)",
    "  ├─ Params_Inputs  : Skid_Parameters_Inputs ← FC_InputReg116_L112  (regs 116–227)",
    "  ├─ Params_Hold    : Skid_Parameters_Hold",
    "  └─ ConnectSettings: TCON_IP_v4  (192.168.10.x : 502)",
    "",
    "FC_PPC_SkidMapping  (called 10×/scan, before FB_PPC_Controller)",
    "",
    "FB_PPC_Controller_DB.Inverters[0..9]  : Inverter_controller",
    "  ├─ FC_PPC_InverterMonitor   → PmaxPlant, QmaxPlant, N_Online",
    "  ├─ FC_PPC_PowerDistribution → WSpt per inverter",
    "  └─ FC_PPC_ReactiveControl   → VArSpt / PFSpt per inverter",
    "",
    "FC_PPC_SkidMapping writes setpoints back → SKIDx.db.Inverter",
    "FC_Pack_Write_Regs → [FC16 writes] → SMA Inverter",
]
for line in arch:
    story.append(p(line, S_CODE))
story.append(sp(4))

story += [h2("OB30 call order (critical)")]
story += [p(
    "① FC_SkidElectricStatus × 10 — DI switchgear status → FB_PPC_Controller_DB.Skids[0..9]<br/>"
    "② FC_PPC_SkidMapping × 10 — reads SKID DB into Inverter_controller, writes previous scan's setpoints back<br/>"
    "③ FB_PPC_Controller (InverterMonitor → RampControl → FreqResponse → PowerDistribution → ReactiveControl → FaultHandler)"
)]

# ── §2 Read blocks ────────────────────────────────────────────────────────────
story += [PageBreak(), h1("2.  Modbus Read Blocks — SKID DB Population")]
story += [p(
    "Two FCs together cover the complete SMA SC 4600 UP input register map. "
    "Both are called by ReadInverterData (FB15) once per scan per SKID."
)]

# § 2.1 FC17 table
story += [h2("2.1  FC_InputReg10_L106_To_Inputs — SMA registers 10–115")]
story += [p("Array offset: Reg[0] = SMA register 10.  Bold rows = consumed by PPC control logic.")]

hdr = [th("SMA Reg"), th("Reg[ ]"), th("Field"), th("Scaling"), th("Unit"), th("Destination UDT")]
fc10_rows = [
    hdr,
    [tdcsm("10..11"),  tdcsm("[0..1]"),   tdsm("DcMs.TotWatt"),       tdcsm("S32 FIX0"),        tdcsm("W"),    tdsm("Inps.DcMs.TotWatt")],
    [tdcsm("12..13"),  tdcsm("[2..3]"),   tdsm("InvMs.DclVol.Stk1"),  tdcsm("S32 FIX1 ÷10"),   tdcsm("V"),    tdsm("Inps.InvMs.DclVol.Stk1")],
    [tdcsm("14..15"),  tdcsm("[4..5]"),   tdsm("InvMs.DclVol.Stk2"),  tdcsm("S32 FIX1 ÷10"),   tdcsm("V"),    tdsm("Inps.InvMs.DclVol.Stk2")],
    [tdcsm("16..17"),  tdcsm("[6..7]"),   tdsm("InvMs.DclVol.Stk3"),  tdcsm("S32 FIX1 ÷10"),   tdcsm("V"),    tdsm("Inps.InvMs.DclVol.Stk3")],
    [tdcsm("18..19"),  tdcsm("[8..9]"),   tdsm("InvMs.TotA.PhsA"),    tdcsm("S32 FIX0"),        tdcsm("mA"),   tdsm("Inps.InvMs.TotA.PhsA")],
    [tdcsm("22..23"),  tdcsm("[12..13]"), tdsm("InvMs.TotA.PhsC"),    tdcsm("S32 FIX0"),        tdcsm("mA"),   tdsm("Inps.InvMs.TotA.PhsC")],
    [tdcsm("24..25"),  tdcsm("[14..15]"), tdsm("InvMs.PF"),           tdcsm("S32 FIX4 ÷10000"), tdcsm("—"),    tdsm("Inps.InvMs.PF  (Real)")],
    [tdcsm("26..27"),  tdcsm("[16..17]"), tdsm("InvMs.TotVA"),        tdcsm("S32 FIX0"),        tdcsm("VA"),   tdsm("Inv.InvMs.TotVA")],
    [tdcsm("28..29"),  tdcsm("[18..19]"), tdsm("InvMs.TotW"),         tdcsm("S32 FIX0"),        tdcsm("kW"),   tdsm("Inv.InvMs.TotW  (monitoring)")],
    [tdcsm("30..31"),  tdcsm("[20..21]"), tdsm("InvMs.TotVAr"),       tdcsm("S32 FIX0"),        tdcsm("kVAr"), tdsm("Inv.InvMs.TotVAr  (monitoring)")],
    [tdcsm("32..37"),  tdcsm("[22..27]"), tdsm("GriMs.V.PhsAB/BC/CA"),tdcsm("S32 FIX1 ÷10"),   tdcsm("V"),    tdsm("Inps.GriMs.V.*")],
    [tdcsm("38..39"),  tdcsm("[28..29]"), tdsm("GriMs.Hz"),           tdcsm("S32 FIX2 ÷100"),   tdcsm("Hz"),   tdsm("Inv.GriMs.Hz  (Real)")],
    [tdcsm("40..55"),  tdcsm("[30..45]"), tdsm("TmpCab.* / TmpStk.* / TmpExl / TmpTrf"), tdcsm("S32 FIX1 ÷10"), tdcsm("°C"), tdsm("Inps.Tmp*")],
    [tdcsm("56..69"),  tdcsm("[46..59]"), tdsm("DcSw1..3Stt / AcSwStt / CapacSwStt / PrchrgSwStt"), tdcsm("S32 ENUM"), tdcsm("—"), tdsm("Inps.*Stt")],
    [tdcsm("70..91"),  tdcsm("[60..81]"), tdsm("Cnt.* counters"),      tdcsm("U32/S32"),         tdcsm("s/MWh"),tdsm("Inps.Cnt.*")],
    [tdcsm("100..101"),tdcsm("[90..91]"), tdsm("Rio.KeySw"),           tdcsm("S32 ENUM"),        tdcsm("—"),    tdsm("Inps.Rio.KeySw")],
    [tdcsm("102..103"),tdcsm("[92..93]"), tdsm("WaitGriTm"),           tdcsm("S32 FIX1 ÷10"),   tdcsm("s"),    tdsm("Inps.WaitGriTm")],
    [tdcsm("104..107"),tdcsm("[94..97]"), tdsm("DevInf.SerNo / GfdiSwStt"), tdcsm("U32/S32"),  tdcsm("—"),    tdsm("Inps.*")],
    [tdcsm("108..109"),tdcsm("[98..99]"), tdsm("WSpt readback"),       tdcsm("S32 FIX0"),        tdcsm("kW"),   tdsm("Inps.WSpt_Fdbk")],
    [tdcsm("110..111"),tdcsm("[100..101]"),tdsm("VAMaxSpt"),           tdcsm("S32 FIX1 ÷10"),   tdcsm("VA"),   tdsm("Inps.VAMaxSpt")],
    [tdcsm("112..113"),tdcsm("[102..103]"),tdsm("VArSpt readback"),    tdcsm("S32 FIX0"),        tdcsm("kVAr"), tdsm("Inps.VarSpt_Fdbk")],
    [tdcsm("114..115"),tdcsm("[104..105]"),tdsm("PFSpt readback"),     tdcsm("S32 FIX4 ÷10000"),tdcsm("—"),    tdsm("Inps.PFSpt_Fdbk  (Real)")],
    [tdcsm("92..93"),  tdcsm("[82..83]"), tdsm("ErrLcn"),              tdcsm("U32"),             tdcsm("—"),    tdsm("Inv.ErrLcn")],
    [tdcsm("94..95"),  tdcsm("[84..85]"), tdsm("ErrStt"),              tdcsm("S32 ENUM"),        tdcsm("—"),    tdsm("Inv.ErrStt  → Error flag")],
    [tdcsm("96..97"),  tdcsm("[86..87]"), tdsm("ErrNo"),               tdcsm("U32"),             tdcsm("—"),    tdsm("Inv.ErrNo")],
    [tdcsm("98..99"),  tdcsm("[88..89]"), tdsm("OpStt"),               tdcsm("S32 ENUM"),        tdcsm("—"),    tdsm("Inv.OpStt  → RemReady flag")],
]
# highlight critical rows (0-indexed after header = row 1+)
crit_rows_fc10 = [(9,None,C_GREEN),(10,None,C_GREEN),(12,None,C_GREEN),
                  (19,None,C_YELLOW),(21,None,C_YELLOW),(22,None,C_YELLOW),
                  (24,None,C_GREEN),(26,None,C_GREEN)]
crit_cmds = []
for row_idx, _, bg in crit_rows_fc10:
    crit_cmds.append(("BACKGROUND", (0, row_idx), (-1, row_idx), bg))

t = Table(fc10_rows, colWidths=[1.8*cm, 1.7*cm, 4.8*cm, 2.5*cm, 1.4*cm, 4.8*cm], repeatRows=1)
t.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (-1,0), C_LBLUE),
    ("TEXTCOLOR",  (0,0), (-1,0), C_WHITE),
    ("ROWBACKGROUNDS",(0,1),(-1,-1),[C_WHITE, C_ALT]),
    ("GRID",       (0,0), (-1,-1), 0.4, colors.HexColor("#C0C0C0")),
    ("VALIGN",     (0,0), (-1,-1), "TOP"),
    ("LEFTPADDING",(0,0), (-1,-1), 3),
    ("RIGHTPADDING",(0,0),(-1,-1), 3),
    ("TOPPADDING", (0,0), (-1,-1), 2),
    ("BOTTOMPADDING",(0,0),(-1,-1),2),
] + crit_cmds))
story.append(t)
story += [sp(4), p(
    "<font color='#1F7A1F'>■</font> Green = consumed by PPC control.  "
    "<font color='#B8860B'>■</font> Yellow = setpoint readback (diagnostic).",
    S_NOTE
)]

# § 2.2 FC_InputReg116 table
story += [PageBreak(), h2("2.2  FC_InputReg116_L112_To_Inputs — SMA registers 116–227")]
story += [p("Array offset: Reg[0] = SMA register 116.")]

hdr2 = [th("SMA Reg"), th("Reg[ ]"), th("Field"), th("Scaling"), th("Unit"), th("Destination UDT")]
fc116_rows = [
    hdr2,
    [tdcsm("116..123"), tdcsm("[0..7]"),   tdsm("TrfPro.*"),          tdcsm("S32 ENUM"),        tdcsm("—"),    tdsm("Inps.TrfPro.*")],
    [tdcsm("124..135"), tdcsm("[8..19]"),  tdsm("TmpStk1..3.lgbt"),   tdcsm("S32 FIX1 ÷10"),   tdcsm("°C"),   tdsm("Inps.TmpStk*.lgbt")],
    [tdcsm("130..135"), tdcsm("[14..19]"), tdsm("TmpStk1..3.Pcb"),    tdcsm("S32 FIX1 ÷10"),   tdcsm("°C"),   tdsm("Inps.TmpStk*.Pcb")],
    [tdcsm("136..137"), tdcsm("[20..21]"), tdsm("Cnt.YstdWhOut"),     tdcsm("S32 FIX2 ÷100"),  tdcsm("MWh"),  tdsm("Inps.Cnt.YstdWhOut")],
    [tdcsm("138..139"), tdcsm("[22..23]"), tdsm("Cpu1UpTime"),        tdcsm("U32 FIX0"),        tdcsm("s"),    tdsm("Inps.Cpu1UpTime")],
    [tdcsm("140..141"), tdcsm("[24..25]"), tdsm("PvGnd.RisIso"),      tdcsm("S32 FIX1 ÷10"),   tdcsm("kΩ"),   tdsm("Inps.PvGnd.RisIso")],
    [tdcsm("142..145"), tdcsm("[26..29]"), tdsm("PresTrf / PresTrf.ErrStt"), tdcsm("S32"),     tdcsm("—"),    tdsm("Inps.PresTrf*")],
    [tdcsm("146"),      tdcsm("[30]"),     tdsm("BfpBits"),           tdcsm("U16"),             tdcsm("—"),    tdsm("Inps.BfpBits  (Int)")],
    [tdcsm("147..148"), tdcsm("[31..32]"), tdsm("DcMs.BfpAmp"),       tdcsm("S32 FIX1 ÷10"),   tdcsm("A"),    tdsm("Inps.DcMs.BfpAmp")],
    [tdcsm("149..150"), tdcsm("[33..34]"), tdsm("GriMs.Vol.PsNom"),   tdcsm("S32 FIX4 ÷10000"),tdcsm("pu"),   tdsm("Inps.GriMs.Vol.PsNom")],
    [tdcsm("151..158"), tdcsm("[35..42]"), tdsm("Cnt.TotDcWhOut / TotAcWhIn / DcWhOut / AcWhIn"), tdcsm("S32 FIX2 ÷100"), tdcsm("MWh"), tdsm("Inps.Cnt.*")],
    [tdcsm("159..160"), tdcsm("[43..44]"), tdsm("DclVolSpt"),         tdcsm("S32 FIX1 ÷10"),   tdcsm("V"),    tdsm("Inps.DclVolSpt")],
    [tdcsm("163..164"), tdcsm("[47..48]"), tdsm("VolNomSpt"),         tdcsm("S32 FIX4 ÷10000"),tdcsm("pu"),   tdsm("Inps.VolNomSpt")],
    [tdcsm("167"),      tdcsm("[51]"),     tdsm("AuxCtl.LifeSign"),   tdcsm("U16"),             tdcsm("—"),    tdsm("Inps.AuxCtl.LifeSign  (Int)")],
    [tdcsm("168..169"), tdcsm("[52..53]"), tdsm("InvPwrVolTyp"),      tdcsm("S32 ENUM"),        tdcsm("—"),    tdsm("Inps.InvPwrVolTyp")],
    [tdcsm("170..171"), tdcsm("[54..55]"), tdsm("HzNomSpt"),          tdcsm("S32 FIX2 ÷100"),  tdcsm("Hz"),   tdsm("Inps.HzNomSpt")],
    [tdcsm("172..173"), tdcsm("[56..57]"), tdsm("WAval"),             tdcsm("S32 FIX4 ÷10000"),tdcsm("pu"),   tdsm("Inv.WAval  (Real 0.0–1.0)")],
    [tdcsm("174..175"), tdcsm("[58..59]"), tdsm("VArAval"),           tdcsm("S32 FIX4 ÷10000"),tdcsm("pu"),   tdsm("Inv.VArAval  (Real 0.0–1.0)")],
    [tdcsm("176..177"), tdcsm("[60..61]"), tdsm("DrtStt"),            tdcsm("S32 ENUM"),        tdcsm("—"),    tdsm("Inps.DrtStt")],
    [tdcsm("178..179"), tdcsm("[62..63]"), tdsm("PwrOffReas"),        tdcsm("S32 ENUM"),        tdcsm("—"),    tdsm("Inv.PwrOffReas")],
    [tdcsm("180..181"), tdcsm("[64..65]"), tdsm("DiagRmgTm"),         tdcsm("U32 FIX0"),        tdcsm("s"),    tdsm("Inps.DiagRmgTm")],
    [tdcsm("182"),      tdcsm("[66]"),     tdsm("Rio.Din.FloatCtl.Wa"),tdcsm("U16"),            tdcsm("—"),    tdsm("Inps.Rio.Din.FloatCtl.Wa")],
    [tdcsm("183"),      tdcsm("[67]"),     tdsm("Rio.Din.FloatCtl.Err"),tdcsm("U16"),           tdcsm("—"),    tdsm("Inps.Rio.Din.FloatCtl.Err")],
    [tdcsm("184..185"), tdcsm("[68..69]"), tdsm("WRtg"),              tdcsm("S32 FIX0"),        tdcsm("kW"),   tdsm("Inps.WRtg  (commissioning read)")],
    [tdcsm("186"),      tdcsm("[70]"),     tdsm("Gfdi.AmpPrc"),       tdcsm("S16 FIX2 ÷100"),  tdcsm("A"),    tdsm("Inps.Gfdi.AmpPrc")],
    [tdcsm("187"),      tdcsm("[71]"),     tdsm("Gfdi.AmpErr"),       tdcsm("S16 FIX2 ÷100"),  tdcsm("A"),    tdsm("Inps.Gfdi.AmpErr")],
    [tdcsm("188..227"), tdcsm("[72..111]"),tdsm("ActErrNo1..10 / ActErrLcn1..10"), tdcsm("U32"), tdcsm("—"), tdsm("Inps.ActErrNo/Lcn 1..10")],
]
crit_fc116 = [17, 18, 20]  # WAval, VArAval, PwrOffReas
crit_cmds2 = [("BACKGROUND",(0,r),(-1,r),C_GREEN) for r in crit_fc116]
t2 = Table(fc116_rows, colWidths=[1.8*cm, 1.7*cm, 4.8*cm, 2.5*cm, 1.4*cm, 4.8*cm], repeatRows=1)
t2.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (-1,0), C_LBLUE),
    ("TEXTCOLOR",  (0,0), (-1,0), C_WHITE),
    ("ROWBACKGROUNDS",(0,1),(-1,-1),[C_WHITE, C_ALT]),
    ("GRID",       (0,0), (-1,-1), 0.4, colors.HexColor("#C0C0C0")),
    ("VALIGN",     (0,0), (-1,-1), "TOP"),
    ("LEFTPADDING",(0,0), (-1,-1), 3),
    ("RIGHTPADDING",(0,0),(-1,-1), 3),
    ("TOPPADDING", (0,0), (-1,-1), 2),
    ("BOTTOMPADDING",(0,0),(-1,-1),2),
] + crit_cmds2))
story.append(t2)
story += [sp(4), p("<font color='#1F7A1F'>■</font> Green = consumed by PPC control logic.", S_NOTE)]

# ── §3 SkidMapping ────────────────────────────────────────────────────────────
story += [PageBreak(), h1("3.  FC_PPC_SkidMapping — The Bridge")]
story += [p(
    "Called once per SKID in OB30 (10 calls total), <b>before</b> FB_PPC_Controller. "
    "Performs read and write directions in a single call. Skips setpoint writes when CommError = TRUE."
)]

# 3.1 READ
story += [h2("3.1  READ direction: SKID DB → Inverter_controller")]
rd_hdr = [th("Source (Sunny_inverter / Params_Inputs)"), th("Conversion"), th("Destination (Inverter_controller)"), th("Note")]
rd_rows = [
    rd_hdr,
    [td("SkidInverter.OpStt  (DInt ENUM)"), td("= 3526 OR 3527 OR 3529 OR 3530"), td("Inverter.RemReady  (Bool)"), td("3526=GridFeed, 3527=FRT, 3529=QonDemand, 3530=RampDown")],
    [td("SkidInverter.ErrStt  (DInt ENUM)"), td("≠ 307"), td("Inverter.Error  (Bool)"), td("307 = Ok (no fault)")],
    [td("SkidInverter.InvMs.TotW  (DInt, kW)"), td("direct copy"), td("Inverter.Wactive  (DInt, kW)"), td("monitoring only — not used in control")],
    [td("SkidInverter.InvMs.TotVAr  (DInt, kVAr)"), td("direct copy"), td("Inverter.Qactive  (DInt, kVAr)"), td("monitoring only")],
    [td("SkidInverter.WAval  (Real, pu 0.0–1.0)"), td("× 10000 → REAL_TO_DINT"), td("Inverter.WAval  (DInt, FIX4)"), td("drives PmaxPlant and proportional distribution")],
    [td("SkidInverter.VArAval  (Real, pu 0.0–1.0)"), td("× 10000 → REAL_TO_DINT"), td("Inverter.VArAval  (DInt, FIX4)"), td("drives QmaxPlant")],
    [td("SkidInverter.PwrOffReas  (DInt ENUM)"), td("direct copy"), td("Inverter.PwrOffReas  (DInt)"), td("≠ 0 → not Available (online criteria)")],
    [td("SkidInputs.DrtStt  (DInt ENUM)"), td("direct copy"), td("Inverter.DrtStt  (DInt)"), td("derating state — diagnostic")],
    [td("CommError  (Bool)"), td("direct copy"), td("Inverter.CommError  (Bool)"), td("online criteria")],
]
crit_rd = [6, 7]
crit_rd_cmds = [("BACKGROUND",(0,r),(-1,r),C_GREEN) for r in crit_rd]
t3 = Table(rd_rows, colWidths=[5.2*cm, 3.5*cm, 4.2*cm, 4.1*cm], repeatRows=1)
t3.setStyle(TableStyle([
    ("BACKGROUND",(0,0),(-1,0),C_LBLUE),
    ("TEXTCOLOR", (0,0),(-1,0),C_WHITE),
    ("ROWBACKGROUNDS",(0,1),(-1,-1),[C_WHITE,C_ALT]),
    ("GRID",(0,0),(-1,-1),0.4,colors.HexColor("#C0C0C0")),
    ("VALIGN",(0,0),(-1,-1),"TOP"),
    ("LEFTPADDING",(0,0),(-1,-1),4),
    ("RIGHTPADDING",(0,0),(-1,-1),4),
    ("TOPPADDING",(0,0),(-1,-1),3),
    ("BOTTOMPADDING",(0,0),(-1,-1),3),
] + crit_rd_cmds))
story.append(t3)
story += [sp(4), p("<font color='#1F7A1F'>■</font> Green = primary dispatch fields.", S_NOTE)]

# 3.2 WRITE
story += [sp(6), h2("3.2  WRITE direction: Inverter_controller → SKID DB  (skipped if CommError)")]
wr_hdr = [th("Source (Inverter_controller)"), th("Conversion"), th("Destination (Sunny_inverter)"), th("SMA Reg"), th("Note")]
wr_rows = [
    wr_hdr,
    [td("Inverter.OperMode  (DInt)"), td("direct"), td("SkidInverter.RemRdy"), tdc("1st"), td("SMA requires RemRdy before InvOpMod")],
    [td("Inverter.OperMode  (DInt)"), td("direct"), td("SkidInverter.InvOpMod"), tdc("2nd"), td("308=Run, 303=Stop")],
    [td("Inverter.WMode  (DInt)"), td("direct"), td("SkidInverter.GriMng.WMod"), tdc("0 grp"), td("1079=WCtlCom, 303=Off")],
    [td("Inverter.WSpt  (DInt, kW)"), td("direct"), td("SkidInverter.WSpt"), tdc("108"), td("active power setpoint")],
    [td("Inverter.VArMode  (DInt)"), td("direct"), td("SkidInverter.GriMng.VArMod"), tdc("0 grp"), td("1072=VArCtlCom, 1075=PFCtlCom")],
    [td("Inverter.VArSpt  (DInt, kVAr)"), td("direct"), td("SkidInverter.VArSpt"), tdc("112"), td("reactive power setpoint")],
    [td("Inverter.PFSpt  (DInt, FIX4)"), td("÷ 10000 → Real"), td("SkidInverter.PFSpt  (Real, cos φ)"), tdc("114"), td("FC_Pack_Write_Regs packs back to FIX4 for FC16")],
    [td("Inverter.ErrClr  (DInt)"), td("direct"), td("SkidInverter.ErrClr"), tdc("8"), td("one-shot: 26 for one scan, then 0")],
]
t4 = Table(wr_rows, colWidths=[4.5*cm, 2.8*cm, 4.2*cm, 1.8*cm, 3.7*cm], repeatRows=1)
t4.setStyle(TableStyle([
    ("BACKGROUND",(0,0),(-1,0),C_LBLUE),
    ("TEXTCOLOR", (0,0),(-1,0),C_WHITE),
    ("ROWBACKGROUNDS",(0,1),(-1,-1),[C_WHITE,C_ALT]),
    ("GRID",(0,0),(-1,-1),0.4,colors.HexColor("#C0C0C0")),
    ("VALIGN",(0,0),(-1,-1),"TOP"),
    ("LEFTPADDING",(0,0),(-1,-1),4),
    ("RIGHTPADDING",(0,0),(-1,-1),4),
    ("TOPPADDING",(0,0),(-1,-1),3),
    ("BOTTOMPADDING",(0,0),(-1,-1),3),
]))
story.append(t4)

# ── §4 WAval chain ────────────────────────────────────────────────────────────
story += [PageBreak(), h1("4.  WAval / VArAval Scaling Chain (End-to-End)")]
story += [p(
    "This is the most critical scaling path — it drives active power dispatch, "
    "proportional distribution, and the FreqResponse dynamic band."
)]

chain_lines = [
    "SMA Modbus register 172  (S32 FIX4)",
    "  Raw example: 8500   →  85 % of rated power available",
    "",
    "FC_InputReg116_L112_To_Inputs:",
    "  Inv.WAval := DINT_TO_REAL(di32) / 10000.0",
    "         ↓",
    "SKID1.Inverter.WAval = 0.85  (Real, per-unit 0.0–1.0)",
    "",
    "FC_PPC_SkidMapping:",
    "  Inverter.WAval := REAL_TO_DINT(SkidInverter.WAval × 10000.0)",
    "         ↓",
    "FB_PPC_Controller_DB.Inverters[0].WAval = 8500  (DInt, FIX4 pu×10000)",
    "",
    "FC_PPC_InverterMonitor:",
    "  PmaxPlant += DINT_TO_REAL(WAval) / 10000.0 × WRtg_kW",
    "             = 8500 / 10000.0 × 4600 kW  =  3910 kW  (this inverter's contribution)",
    "         ↓",
    "PmaxPlant (Real, kW)  =  sum across all Available inverters  →  up to 46 000 kW",
    "",
    "FB_PPC_FreqResponse:",
    "  Pmax_active = Pmax_disp - dP_at_200mHz_OF   (Pmax_disp = PmaxPlant)",
    "         ↓",
    "FC_PPC_PowerDistribution:",
    "  share_i = WAval[i] / ΣWAval[j]    (raw DInt ratio — units cancel)",
    "  WSpt[i] = P_final_kW × share_i    → per-inverter kW setpoint",
    "  maxWSpt = WAval[i] / 10000 × WRtg_kW   → per-inverter clamp",
    "         ↓",
    "Inverter_controller.WSpt[0..9]  (DInt, kW)  →  written via FC_PPC_SkidMapping",
]
for line in chain_lines:
    story.append(p(line, S_CODE))

story += [sp(6), p(
    "<b>Note:</b> In the proportional split, the ÷10000 and ×WRtg_kW factors cancel "
    "across numerator and denominator, so raw DInt FIX4 values are used directly for "
    "the ratio — no conversion at that stage. Conversion is only needed for absolute "
    "kW/kVAr values (PmaxPlant, QmaxPlant, per-inverter WSpt clamp)."
)]

# ── §5 InverterMonitor criteria ───────────────────────────────────────────────
story += [sp(6), h1("5.  InverterMonitor Online Criteria")]
story += [p(
    "FC_PPC_InverterMonitor computes Inverters[i].Available once per scan. "
    "All six conditions must be TRUE. Result is cached into Available — "
    "PowerDistribution, ReactiveControl, and FaultHandler read this, never re-deriving it."
)]
crit_hdr = [th("Condition"), th("Source field"), th("Set to FALSE when")]
crit_rows = [
    crit_hdr,
    [td("Enabled"), td("DB39 / HMI write"), td("Operator has disabled this inverter slot")],
    [td("RemReady"), td("Inverter.RemReady  (from OpStt)"), td("OpStt ∉ {3526, 3527, 3529, 3530}")],
    [td("NOT Error"), td("Inverter.Error  (from ErrStt)"), td("ErrStt ≠ 307")],
    [td("NOT CommError"), td("Inverter.CommError  (from MB_CLIENT)"), td("Modbus TCP timeout or error")],
    [td("PwrOffReas = 0"), td("Inverter.PwrOffReas  (from OpStt group)"), td("Inverter disconnected abnormally")],
    [td("ELECTRIC_OK"), td("FB_PPC_Controller_DB.Skids[i]"), td("Breaker / separator / earthing not OK (DI status)")],
]
t5 = Table(crit_rows, colWidths=[3.5*cm, 5.5*cm, 8.0*cm], repeatRows=1)
t5.setStyle(TableStyle([
    ("BACKGROUND",(0,0),(-1,0),C_LBLUE),
    ("TEXTCOLOR", (0,0),(-1,0),C_WHITE),
    ("ROWBACKGROUNDS",(0,1),(-1,-1),[C_WHITE,C_ALT]),
    ("GRID",(0,0),(-1,-1),0.4,colors.HexColor("#C0C0C0")),
    ("VALIGN",(0,0),(-1,-1),"TOP"),
    ("LEFTPADDING",(0,0),(-1,-1),4),
    ("RIGHTPADDING",(0,0),(-1,-1),4),
    ("TOPPADDING",(0,0),(-1,-1),3),
    ("BOTTOMPADDING",(0,0),(-1,-1),3),
]))
story.append(t5)

# ── §6 Scaling Summary ────────────────────────────────────────────────────────
story += [sp(10), h1("6.  Scaling Conventions Summary")]
sc_hdr = [th("Signal"), th("SMA Modbus"), th("Sunny_inverter (SKID DB)"), th("Inverter_controller (PPC)"), th("PPC computation")]
sc_rows = [
    sc_hdr,
    [td("WAval"),       tdc("S32 FIX4\nreg 172"),     tdc("Real pu\n(÷10000)"),         tdc("DInt FIX4\n(×10000)"),    td("÷10000 × WRtg_kW → kW")],
    [td("VArAval"),     tdc("S32 FIX4\nreg 174"),     tdc("Real pu\n(÷10000)"),         tdc("DInt FIX4\n(×10000)"),    td("÷10000 × WRtg_kW → kVAr")],
    [td("InvMs.TotW"),  tdc("S32 FIX0\nreg 28, kW"),  tdc("DInt kW\n(direct)"),         tdc("DInt kW\n(direct)"),      td("monitoring only")],
    [td("InvMs.TotVAr"),tdc("S32 FIX0\nreg 30, kVAr"),tdc("DInt kVAr\n(direct)"),      tdc("DInt kVAr\n(direct)"),    td("monitoring only")],
    [td("GriMs.Hz"),    tdc("S32 FIX2\nreg 38"),      tdc("Real Hz\n(÷100)"),           tdc("—"),                      td("read by PPC via Sunny_inverter.GriMs.Hz")],
    [td("WSpt"),        tdc("S32 FIX0\nreg 108, kW"), tdc("DInt kW\n(PPC writes)"),     tdc("DInt kW\n(direct)"),      td("readback → Inps.WSpt_Fdbk")],
    [td("VArSpt"),      tdc("S32 FIX0\nreg 112, kVAr"),tdc("DInt kVAr\n(PPC writes)"), tdc("DInt kVAr\n(direct)"),    td("readback → Inps.VarSpt_Fdbk")],
    [td("PFSpt"),       tdc("S32 FIX4\nreg 114"),     tdc("Real cos φ\n(FC_Pack ×10000)"),tdc("DInt FIX4\ne.g. 9500"), td("readback ÷10000 → Inps.PFSpt_Fdbk")],
    [td("WRtg"),        tdc("S32 FIX0\nreg 184, kW"), tdc("DInt kW\n(Inps.WRtg)"),     tdc("—"),                      td("DB39.WRtg_kW = 4600 (commissioning)")],
    [td("OpStt"),       tdc("S32 ENUM\nreg 98"),       tdc("DInt ENUM\n(direct)"),      tdc("→ RemReady\n(Bool)"),     td("3526/3527/3529/3530 → TRUE")],
    [td("ErrStt"),      tdc("S32 ENUM\nreg 94"),       tdc("DInt ENUM\n(direct)"),      tdc("→ Error\n(Bool)"),        td("≠ 307 → TRUE")],
    [td("PwrOffReas"),  tdc("S32 ENUM\nreg 178"),      tdc("DInt ENUM\n(direct)"),      tdc("DInt\n(direct)"),         td("≠ 0 → not Available")],
    [td("DrtStt"),      tdc("S32 ENUM\nreg 176"),      tdc("DInt ENUM\n(Params_Inputs)"),tdc("DInt\n(direct)"),        td("derating diagnostic")],
]
t6 = Table(sc_rows, colWidths=[2.8*cm, 2.5*cm, 3.5*cm, 3.2*cm, 5.0*cm], repeatRows=1)
t6.setStyle(TableStyle([
    ("BACKGROUND",(0,0),(-1,0),C_LBLUE),
    ("TEXTCOLOR", (0,0),(-1,0),C_WHITE),
    ("ROWBACKGROUNDS",(0,1),(-1,-1),[C_WHITE,C_ALT]),
    ("GRID",(0,0),(-1,-1),0.4,colors.HexColor("#C0C0C0")),
    ("VALIGN",(0,0),(-1,-1),"TOP"),
    ("LEFTPADDING",(0,0),(-1,-1),4),
    ("RIGHTPADDING",(0,0),(-1,-1),4),
    ("TOPPADDING",(0,0),(-1,-1),3),
    ("BOTTOMPADDING",(0,0),(-1,-1),3),
    ("BACKGROUND",(0,1),(-1,2),C_GREEN),   # WAval, VArAval
]))
story.append(t6)

# ── §7 Key Constants ──────────────────────────────────────────────────────────
story += [sp(10), h1("7.  Key Constants — DB39 (PPC_Controller)")]
kc_hdr = [th("Parameter"), th("Value"), th("Source / Note")]
kc_rows = [
    kc_hdr,
    [td("WRtg_kW"),      td("4600.0 kW"),  td("Read from SMA reg 184 at commissioning; stored in DB39")],
    [td("Pn_MW"),        td("46.0 MW"),    td("10 × WRtg_kW ÷ 1000  (plant nameplate)")],
    [td("Droop_OF_pct"), td("8.0 %"),      td("ANRE Ord.51/2019 Art. 114-115 (over-frequency)")],
    [td("Droop_UF_pct"), td("10.0 %"),     td("ANRE Ord.51/2019 Art. 118-120 (under-frequency)")],
]
t7 = Table(kc_rows, colWidths=[4.0*cm, 3.0*cm, 10.0*cm], repeatRows=1)
t7.setStyle(TableStyle([
    ("BACKGROUND",(0,0),(-1,0),C_LBLUE),
    ("TEXTCOLOR", (0,0),(-1,0),C_WHITE),
    ("ROWBACKGROUNDS",(0,1),(-1,-1),[C_WHITE,C_ALT]),
    ("GRID",(0,0),(-1,-1),0.4,colors.HexColor("#C0C0C0")),
    ("VALIGN",(0,0),(-1,-1),"TOP"),
    ("LEFTPADDING",(0,0),(-1,-1),4),
    ("RIGHTPADDING",(0,0),(-1,-1),4),
    ("TOPPADDING",(0,0),(-1,-1),3),
    ("BOTTOMPADDING",(0,0),(-1,-1),3),
]))
story.append(t7)

story += [sp(20), hr(),
          p("CEF Tandarei 46 MW PV Plant — PPC System Documentation", S_SUB),
          p("Generated 2026-07-11", S_SUB)]

doc.build(story)
print(f"PDF written: {OUTPUT}")
