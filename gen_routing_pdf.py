from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY

OUTPUT = r"c:\Users\cosmi\OneDrive\WORK\PPC_ENERGY\Write_Sequence_Data_Routing.pdf"

# ── colour palette ────────────────────────────────────────────────────────────
C_NAVY   = colors.HexColor("#1a2e4a")
C_BLUE   = colors.HexColor("#2563a8")
C_LBLUE  = colors.HexColor("#dbeafe")
C_GREEN  = colors.HexColor("#166534")
C_LGREEN = colors.HexColor("#dcfce7")
C_RED    = colors.HexColor("#7f1d1d")
C_LRED   = colors.HexColor("#fee2e2")
C_AMBER  = colors.HexColor("#92400e")
C_LAMBER = colors.HexColor("#fef3c7")
C_GREY   = colors.HexColor("#f1f5f9")
C_DGREY  = colors.HexColor("#64748b")
C_BLACK  = colors.HexColor("#0f172a")

W = A4[0] - 30*mm   # usable width

# ── styles ────────────────────────────────────────────────────────────────────
ss = getSampleStyleSheet()

def sty(name, parent="Normal", **kw):
    return ParagraphStyle(name, parent=ss[parent], **kw)

H1  = sty("H1",  "Heading1", fontSize=18, textColor=C_NAVY,  spaceAfter=4*mm, spaceBefore=2*mm)
H2  = sty("H2",  "Heading2", fontSize=13, textColor=C_BLUE,  spaceAfter=3*mm, spaceBefore=5*mm,
           borderPad=2, backColor=C_LBLUE, leftIndent=2*mm, rightIndent=2*mm)
H3  = sty("H3",  "Heading3", fontSize=11, textColor=C_NAVY,  spaceAfter=2*mm, spaceBefore=4*mm, fontName="Helvetica-Bold")
BOD = sty("BOD", "Normal",   fontSize=9,  textColor=C_BLACK, spaceAfter=2*mm, leading=13)
BLD = sty("BLD", "Normal",   fontSize=9,  fontName="Helvetica-Bold", textColor=C_BLACK, spaceAfter=1*mm)
COD = sty("COD", "Normal",   fontSize=8,  fontName="Courier",        textColor=C_NAVY,  spaceAfter=1*mm, backColor=C_GREY, leftIndent=4*mm)
WAR = sty("WAR", "Normal",   fontSize=9,  textColor=C_AMBER, fontName="Helvetica-Bold", spaceAfter=1*mm)
ERR = sty("ERR", "Normal",   fontSize=9,  textColor=C_RED,   fontName="Helvetica-Bold", spaceAfter=1*mm)
OK  = sty("OK",  "Normal",   fontSize=9,  textColor=C_GREEN, fontName="Helvetica-Bold", spaceAfter=1*mm)
SML = sty("SML", "Normal",   fontSize=8,  textColor=C_DGREY, spaceAfter=1*mm, leading=11)
TTL = sty("TTL", "Normal",   fontSize=22, textColor=colors.white, fontName="Helvetica-Bold",
          alignment=TA_CENTER, spaceAfter=2*mm)
SUB = sty("SUB", "Normal",   fontSize=11, textColor=colors.HexColor("#bfdbfe"),
          alignment=TA_CENTER, spaceAfter=1*mm)

# ── helpers ───────────────────────────────────────────────────────────────────
def hr(): return HRFlowable(width="100%", thickness=0.5, color=C_DGREY, spaceAfter=3*mm, spaceBefore=1*mm)
def sp(h=3): return Spacer(1, h*mm)
def p(txt, style=BOD): return Paragraph(txt, style)
def code(txt): return Paragraph(txt, COD)

def table(data, col_widths, header_row=True, row_colors=None):
    t = Table(data, colWidths=col_widths)
    style_cmds = [
        ("FONTNAME",    (0,0), (-1,-1), "Helvetica"),
        ("FONTSIZE",    (0,0), (-1,-1), 8),
        ("TOPPADDING",  (0,0), (-1,-1), 3),
        ("BOTTOMPADDING",(0,0),(-1,-1), 3),
        ("LEFTPADDING", (0,0), (-1,-1), 4),
        ("RIGHTPADDING",(0,0), (-1,-1), 4),
        ("GRID",        (0,0), (-1,-1), 0.4, C_DGREY),
        ("VALIGN",      (0,0), (-1,-1), "TOP"),
    ]
    if header_row:
        style_cmds += [
            ("BACKGROUND", (0,0), (-1,0), C_NAVY),
            ("TEXTCOLOR",  (0,0), (-1,0), colors.white),
            ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",   (0,0), (-1,0), 8),
        ]
    if row_colors:
        for row_idx, bg in row_colors:
            style_cmds.append(("BACKGROUND", (0, row_idx), (-1, row_idx), bg))
    t.setStyle(TableStyle(style_cmds))
    return t

def info_box(text, bg=C_LBLUE, border=C_BLUE):
    data = [[Paragraph(text, sty("ib","Normal", fontSize=9, textColor=C_BLACK, leading=13))]]
    t = Table(data, colWidths=[W])
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(0,0), bg),
        ("BOX",          (0,0),(0,0), 1, border),
        ("LEFTPADDING",  (0,0),(0,0), 6),
        ("RIGHTPADDING", (0,0),(0,0), 6),
        ("TOPPADDING",   (0,0),(0,0), 5),
        ("BOTTOMPADDING",(0,0),(0,0), 5),
    ]))
    return t

def warn_box(text): return info_box("⚠  " + text, C_LAMBER, colors.HexColor("#d97706"))
def err_box(text):  return info_box("✖  " + text, C_LRED,   colors.HexColor("#dc2626"))
def ok_box(text):   return info_box("✔  " + text, C_LGREEN, colors.HexColor("#16a34a"))

# ── document ──────────────────────────────────────────────────────────────────
doc = SimpleDocTemplate(OUTPUT, pagesize=A4,
                        leftMargin=15*mm, rightMargin=15*mm,
                        topMargin=15*mm, bottomMargin=15*mm)
story = []

# ── cover banner ─────────────────────────────────────────────────────────────
banner_data = [[Paragraph("Write Sequence — Data Routing", TTL)],
               [Paragraph("FB15 ReadInverterData  |  PPC Energy  |  TIA Portal S7-1500", SUB)],
               [Paragraph("Implementation Reference &amp; Race-Condition Checklist", SUB)]]
banner = Table(banner_data, colWidths=[W])
banner.setStyle(TableStyle([
    ("BACKGROUND",    (0,0),(0,2), C_NAVY),
    ("TOPPADDING",    (0,0),(0,2), 5),
    ("BOTTOMPADDING", (0,0),(0,2), 5),
    ("LEFTPADDING",   (0,0),(0,2), 8),
    ("RIGHTPADDING",  (0,0),(0,2), 8),
    ("ROUNDEDCORNERS",(0,0),(0,2), [4,4,4,4]),
]))
story += [banner, sp(5)]

# ═══════════════════════════════════════════════════════════════════════════════
story.append(p("1.  ARCHITECTURE OVERVIEW", H2))

story.append(p(
    "The SMA Sunny Central inverters are controlled over <b>Modbus TCP (FC16 write / FC03-FC04 read)</b>. "
    "All communication for a single inverter is handled by one instance of <b>FB15 ReadInverterData</b>, "
    "which owns the TCP connection and the <i>holdingRegisterMod</i> wire buffer. "
    "PPC logic and FB15 share data exclusively through the <b>SKID_DB.Inverter</b> structure "
    "(<i>Sunny_inverter</i> UDT). "
    "holdingRegisterMod is <u>never written by PPC</u> — it is only the Modbus byte-stream buffer."
))

story += [sp(2)]

# ── data flow table ───────────────────────────────────────────────────────────
story.append(p("Data flow for one OB30 tick (one inverter):", BLD))

flow = [
    ["Step", "Who runs", "Action", "Data location after this step"],
    ["1", "OB30 scheduler",
     "PPC logic executes\n(PowerDistribution,\nReactiveControl,\nFaultHandler)",
     "SKID1.Inverter.InvOpMod  = 308\n"
     "SKID1.Inverter.RemRdy    = 308\n"
     "SKID1.Inverter.\"GriMng.WMod\" = 1079\n"
     "SKID1.Inverter.WSpt      = <PPC kW>\n"
     "SKID1.Inverter.VArSpt    = <PPC kVAr>\n"
     "SKID1.Inverter.PFSpt     = <PPC pf>\n"
     "SKID1.Inverter.ErrClr    = 0 (or ack code)"],
    ["2", "FC19 READ_INVERTERS\n→ FB15 (states 1-3)",
     "Modbus reads:\n"
     "  State 1: FC03 addr 0  len 104\n"
     "  State 2: FC04 addr 10 len 106\n"
     "  State 3: FC04 addr 116 len 112",
     "holdingRegisterMod[] = raw Modbus words\n"
     "→ decode FCs map measurements into:\n"
     "  SKID1.Inverter.OpStt, InvMs.TotW,\n"
     "  GriMs.Hz, WAval, VArAval, etc.\n"
     "(setpoint fields must NOT be overwritten\n— see Section 3)"],
    ["3", "FB15 FC_Pack_Write_Regs\n(states 4-6 transition)",
     "Packs SKID DB setpoints\ninto holdingRegisterMod[]",
     "holdingRegisterMod[0..9]  = ctrl group\n"
     "holdingRegisterMod[0..1]  = WSpt\n"
     "holdingRegisterMod[0..3]  = VArSpt+PFSpt"],
    ["4", "FB15 MB_CLIENT\n(states 4, 5, 6)",
     "Modbus writes:\n"
     "  State 4: FC16 addr 0   len 10\n"
     "  State 5: FC16 addr 108 len 2\n"
     "  State 6: FC16 addr 112 len 4",
     "Physical inverter registers updated:\n"
     "  reg 0-9: InvOpMod,RemRdy,VArMod,WMod,ErrClr\n"
     "  reg 108-109: WSpt\n"
     "  reg 112-115: VArSpt, PFSpt"],
]

cw = [10*mm, 35*mm, 60*mm, W - 10*mm - 35*mm - 60*mm]
story.append(table(flow, cw, row_colors=[(2,C_LBLUE),(3,C_LGREEN),(4,C_LGREEN)]))
story.append(sp(3))

# ═══════════════════════════════════════════════════════════════════════════════
story.append(p("2.  FSM STATE SEQUENCE", H2))
story.append(p(
    "FB15 uses a <b>FunctionalStateMachine (FSM_DB)</b> with <b>NumStates = 6</b>. "
    "The FSM advances on the rising edge of <i>clientData.done</i>. "
    "Each state fires one MB_CLIENT request. The full cycle takes 6 Modbus round-trips."
))

fsm = [
    ["State", "Direction", "FC", "Modbus addr", "Words", "Data mapped to"],
    ["1 — READ", "← Inverter", "FC03 (mode 103)", "0",   "104", "Inverter (holding regs: InvOpMod, RemRdy, modes...)\n+ ParamHold"],
    ["2 — READ", "← Inverter", "FC04 (mode 104)", "10",  "106", "ParamInputs + Inverter measurements\n(OpStt, InvMs.TotW, GriMs.Hz, ...)"],
    ["3 — READ", "← Inverter", "FC04 (mode 104)", "116", "112", "ParamInputs + Inverter measurements (continued)"],
    ["4 — WRITE","→ Inverter", "FC16 (mode 1)",   "0",   "10",  "InvOpMod, RemRdy, GriMng.VArMod, GriMng.WMod, ErrClr"],
    ["5 — WRITE","→ Inverter", "FC16 (mode 1)",   "108", "2",   "WSpt (active power setpoint)"],
    ["6 — WRITE","→ Inverter", "FC16 (mode 1)",   "112", "4",   "VArSpt + PFSpt (reactive power + power factor)"],
]

cw2 = [22*mm, 22*mm, 25*mm, 22*mm, 14*mm, W - 22*mm - 22*mm - 25*mm - 22*mm - 14*mm]
story.append(table(fsm, cw2,
    row_colors=[(1,C_LBLUE),(2,C_LBLUE),(3,C_LBLUE),
                (4,C_LGREEN),(5,C_LGREEN),(6,C_LGREEN)]))
story.append(sp(2))

story.append(info_box(
    "<b>Timing:</b>  Each state needs one Modbus TCP round-trip (~5–20 ms). "
    "Full 6-state cycle = ~30–120 ms per inverter. All 10 inverters run in parallel "
    "(each has its own MB_CLIENT IDB and TCP connection). OB30 = 100 ms.",
    C_GREY, C_DGREY
))
story.append(sp(3))

# ═══════════════════════════════════════════════════════════════════════════════
story.append(p("3.  RACE CONDITION — SETPOINT OVERWRITE RISK", H2))

story.append(warn_box(
    "States 1-3 (reads) run BEFORE states 4-6 (writes) within the same FSM cycle. "
    "If decode FCs map the FC04 readbacks of WSpt/VArSpt/PFSpt into "
    "SKID_DB.Inverter.WSpt / VArSpt / PFSpt, they will OVERWRITE the values "
    "PPC wrote in step 1 before MB_CLIENT has a chance to send them."
))
story.append(sp(2))

story.append(p("3.1  How to verify — check FC_InputReg10_L106_To_Inputs", H3))
story.append(p(
    "State 2 reads FC04 input registers starting at address 10, length 106 words. "
    "This range covers addresses 10–115, which includes:"
))

reg_check = [
    ["Modbus reg", "SMA channel", "Buffer offset in holdingRegisterMod", "Risk field in Sunny_inverter UDT"],
    ["108–109", "WSpt readback",  "offset 196–197  ( (108-10)×2 )",     "Inverter.WSpt"],
    ["112–113", "VArSpt readback","offset 204–205  ( (112-10)×2 )",     "Inverter.VArSpt"],
    ["114–115", "PFSpt readback", "offset 208–209  ( (114-10)×2 )",     "Inverter.PFSpt"],
]
cw3 = [22*mm, 30*mm, 60*mm, W - 22*mm - 30*mm - 60*mm]
story.append(table(reg_check, cw3,
    row_colors=[(1,C_LAMBER),(2,C_LAMBER),(3,C_LAMBER)]))
story.append(sp(2))

story.append(p("Open FC_InputReg10_L106_To_Inputs in TIA Portal and locate the lines that "
               "read buffer positions 196–209. Check what UDT field they assign to:", BOD))
story.append(sp(1))

chk1 = [
    ["What you find in FC_InputReg10_L106_To_Inputs", "Status", "Action required"],
    ["Buffer[196..197] → #Inv.WSpt  (Inverter UDT)",
     "CONFLICT", "Route to ParamInputs instead — add fields WSpt_Fdbk, VArSpt_Fdbk, PFSpt_Fdbk to Skid_Parameters_Inputs UDT"],
    ["Buffer[196..197] → #Inp.WSpt_Fdbk  (ParamInputs UDT)",
     "SAFE", "No action needed — Inverter.WSpt stays as PPC commanded"],
    ["Buffer[196..197] not mapped at all",
     "SAFE", "No action needed — readback discarded, Inverter.WSpt stays as PPC commanded"],
]
cw4 = [75*mm, 18*mm, W - 75*mm - 18*mm]
story.append(table(chk1, cw4,
    row_colors=[(1,C_LRED),(2,C_LGREEN),(3,C_LGREEN)]))
story.append(sp(3))

story.append(p("3.2  Same check for FC_Decode_Holding_0_103_V2 (State 1)", H3))
story.append(p(
    "State 1 reads FC03 holding registers 0–103. "
    "The holding registers for InvOpMod (reg 0), RemRdy (reg 2), WMod (reg 6), VArMod (reg 4) "
    "return the values the inverter <i>last acknowledged</i> — which may lag PPC's command by one cycle. "
    "If the decode FC writes these back into Inverter.InvOpMod etc., PPC's new command "
    "for the same cycle will be overwritten."
))

chk2 = [
    ["Holding reg", "Field", "Buffer offset", "Risk"],
    ["0–1",  "InvOpMod", "0–1",   "Inverter.InvOpMod overwritten with acknowledged (not commanded) value"],
    ["2–3",  "RemRdy",   "2–3",   "Inverter.RemRdy overwritten"],
    ["4–5",  "GriMng.VArMod","4–5","Inverter.VArMod overwritten"],
    ["6–7",  "GriMng.WMod","6–7", "Inverter.WMod overwritten"],
    ["8–9",  "ErrClr",   "8–9",   "Inverter.ErrClr overwritten — one-shot lost"],
]
cw5 = [18*mm, 35*mm, 25*mm, W - 18*mm - 35*mm - 25*mm]
story.append(table(chk2, cw5,
    row_colors=[(1,C_LAMBER),(2,C_LAMBER),(3,C_LAMBER),(4,C_LAMBER),(5,C_LAMBER)]))
story.append(sp(2))

story.append(warn_box(
    "ErrClr is the most critical: it is a one-shot command. "
    "If State 1 reads back reg 8 (ErrClr = 0, because the inverter cleared it after executing) "
    "and the decode FC writes 0 back into Inverter.ErrClr, the one-shot is silently lost "
    "in the same cycle PPC set it."
))
story.append(sp(2))

story.append(p("Recommended fix if conflicts are found:", BLD))
story.append(p(
    "For the setpoint/command fields (InvOpMod, RemRdy, WMod, VArMod, ErrClr, WSpt, VArSpt, PFSpt): "
    "in the decode FCs, do <b>not</b> map the readback into the Inverter UDT field. "
    "Instead, store the readback in a separate <i>_Fdbk</i> field in ParamInputs or a dedicated "
    "feedback structure. This gives you both the PPC command AND the inverter-acknowledged value "
    "without conflict."
))
story.append(sp(3))

# ═══════════════════════════════════════════════════════════════════════════════
story.append(p("4.  ERRCL ONE-SHOT IMPLEMENTATION", H2))

story.append(p(
    "ErrClr must be written exactly <b>once per fault-clear request</b>. "
    "Writing it every cycle would keep sending the acknowledge command continuously, "
    "which the SMA inverter may interpret as repeated fault attempts."
))
story.append(sp(2))

errcl = [
    ["Stage", "Code / Network", "Description"],
    ["FaultHandler sets command",
     "SKID1.Inverter.ErrClr := 302;",
     "PPC writes acknowledge ENUM on rising edge of fault-clear request"],
    ["State 4 transition: pack",
     "FC_Pack_Write_Regs(WriteStep:=1, ...)",
     "ErrClr value packed into holdingRegisterMod[8..9]"],
    ["State 4: MB_CLIENT sends",
     "FC16 addr 0, len 10",
     "ErrClr acknowledge sent to inverter"],
    ["State 5 transition: self-clear",
     "IF (FSM_DB.State=5) AND (FSM_DB.Transition)\nTHEN #Inverter.ErrClr := 0;",
     "State 5 starting = State 4 confirmed done.\nClear ErrClr so next cycle writes 0 (no action)."],
    ["Next cycle: State 4 sends 0",
     "holdingRegisterMod[8..9] = 0x00000000",
     "Inverter receives ErrClr=0 — idle, no repeated acknowledge"],
]
cw6 = [30*mm, 65*mm, W - 30*mm - 65*mm]
story.append(table(errcl, cw6))
story.append(sp(2))

story.append(ok_box(
    "Use (FSM_DB.State = 5) AND (FSM_DB.Transition) to detect State 4 write completed. "
    "Write1_Done static variable is declared in FB15 but never driven — do not use it."
))
story.append(sp(3))

# ═══════════════════════════════════════════════════════════════════════════════
story.append(p("5.  WRITE REGISTER MAP", H2))

wr = [
    ["Write\nState", "FC16\nAddr", "Words", "holdingRegisterMod\nindex", "UDT field\n(source)", "SMA channel", "Format", "Scaling"],
    ["4","0","2","[0..1]","Inverter.InvOpMod","InvOpMod","S32 ENUM","1 (308=Run, 303=Stop)"],
    ["4","2","2","[2..3]","Inverter.RemRdy","RemRdy","S32 ENUM","1 (308=Ready, 303=Standby)"],
    ["4","4","2","[4..5]","Inverter.\"GriMng.VArMod\"","GriMng.VArMod","S32 ENUM","1"],
    ["4","6","2","[6..7]","Inverter.\"GriMng.WMod\"","GriMng.WMod","S32 ENUM","1 (1079=WCtlCom)"],
    ["4","8","2","[8..9]","Inverter.ErrClr","ErrClr","S32 ENUM","1 — ONE-SHOT"],
    ["5","108","2","[0..1]","Inverter.WSpt","WSpt","S32 FIX0","×1, value in kW"],
    ["6","112","2","[0..1]","Inverter.VArSpt","VArSpt","S32 FIX0","×1, value in kVAr"],
    ["6","114","2","[2..3]","Inverter.PFSpt","PFSpt","S32 FIX4","Real×10000  e.g. 0.95→9500"],
]
cw7 = [13*mm, 13*mm, 13*mm, 22*mm, 38*mm, 22*mm, 18*mm, W - 13*mm*3 - 22*mm*2 - 38*mm - 18*mm]
story.append(table(wr, cw7,
    row_colors=[(1,C_LAMBER),(2,C_LAMBER),(3,C_LAMBER),(4,C_LAMBER),(5,C_LRED),
                (6,C_LGREEN),(7,C_LGREEN),(8,C_LGREEN)]))
story.append(sp(3))

# ═══════════════════════════════════════════════════════════════════════════════
story.append(p("6.  IMPLEMENTATION CHECKLIST", H2))

checks = [
    ["#", "Item to verify", "Where to check", "Pass condition"],
    ["1", "NumStates changed from 3 to 6 in FB15 Network 2",
     "FB15 Network 2 → FSM block NumStates input",
     "Constant value = 6"],
    ["2", "State 4/5/6 settings networks added to FB15",
     "FB15 Networks (after existing Network 6)",
     "3 new SCL networks: IF State=4/5/6 THEN set modbusMode=1, addr, len"],
    ["3", "FC_Pack_Write_Regs called on Transition for states 4, 5, 6",
     "FB15 new pack networks",
     "Condition = (FSM_DB.State=N) AND (FSM_DB.Transition)"],
    ["4", "FC_Pack WriteStep 1: holdingRegisterMod[0..9] correct word order",
     "Online watch: trigger State 4, inspect holdingRegisterMod[0..9]",
     "High word before low word for each DInt. e.g. InvOpMod=308 → [0]=0, [1]=308"],
    ["5", "FC_Pack WriteStep 2: holdingRegisterMod[0..1] = WSpt",
     "Online watch during State 5",
     "Value matches PPC commanded WSpt, not inverter readback"],
    ["6", "FC_Pack WriteStep 3: PFSpt scaling ×10000",
     "Online watch [2..3] during State 6",
     "PFSpt=0.9500 → DInt 9500 → [2]=0x0000, [3]=0x251C"],
    ["7", "FC_InputReg10_L106_To_Inputs does NOT overwrite Inverter.WSpt/VArSpt/PFSpt",
     "Open FC17 source, find buffer offsets 196–209",
     "Those offsets map to ParamInputs (or unmapped), NOT Inverter UDT"],
    ["8", "FC_Decode_Holding_0_103_V2 does NOT overwrite Inverter.InvOpMod/ErrClr etc.",
     "Open FC16 source, find buffer offsets 0–9",
     "Setpoint fields not written by decode FC — only status/measurement fields updated"],
    ["9", "ErrClr cleared after State 4 write completes",
     "FB15: IF (State=5) AND (Transition) THEN Inverter.ErrClr:=0",
     "After fault-clear test: ErrClr goes 0 within one OB30 cycle after State 5 starts"],
    ["10","No second MB_CLIENT instance on same inverter IP",
     "Project → Connections table / Device view",
     "Each inverter IP has exactly one MB_CLIENT IDB (one per ReadInverterData_DB_N)"],
    ["11","State 4 write: RemRdy written before InvOpMod (Modbus mapping note)",
     "FC16 writes registers 0–9 as a block. Reg 2 (RemRdy) is physically after reg 0.",
     "For block FC16 this is acceptable — inverter processes atomically. "
     "If SMA requires separate transactions: split State 4 into two states."],
    ["12","ErrClr ENUM value correct for SMA acknowledge",
     "SMA Modbus register map for ErrClr (reg 8)",
     "Confirm the ENUM code used by FaultHandler is the correct SMA acknowledge code"],
]
cw8 = [8*mm, 45*mm, 45*mm, W - 8*mm - 45*mm - 45*mm]
story.append(table(checks, cw8,
    row_colors=[(5,C_LRED),(7,C_LRED),(8,C_LRED)]))   # highlight conflict-risk rows

story.append(sp(2))
story.append(p(
    "<font color='#7f1d1d'>Red rows</font> = highest risk — must be verified before commissioning. "
    "<font color='#92400e'>Amber rows</font> (in Section 3 tables) = verify in decode FC source.",
    SML
))
story.append(sp(3))

# ═══════════════════════════════════════════════════════════════════════════════
story.append(p("7.  FC17 RACE CONDITION — RESOLUTION", H2))

story.append(ok_box(
    "Fix applied (Option B): FC_InputReg10_L106_To_Inputs (FC17) lines 174-175, 190-191, 194-195 "
    "redirected from Inv.WSpt/VArSpt/PFSpt to new fields Inps.WSpt_Fdbk/VArSpt_Fdbk/PFSpt_Fdbk."
))
story.append(sp(2))

fc17 = [
    ["FC17 line", "Old assignment (CONFLICT)", "New assignment (FIXED)"],
    ["174–175", "#Inv.\"WSpt\" := #di32",
     "#Inps.\"WSpt_Fdbk\" := #di32"],
    ["190–191", "#Inv.\"VArSpt\" := #di32",
     "#Inps.\"VArSpt_Fdbk\" := #di32"],
    ["194–195", "#Inv.\"PFSpt\" := DINT_TO_REAL(#di32)/10000.0",
     "#Inps.\"PFSpt_Fdbk\" := DINT_TO_REAL(#di32)/10000.0"],
]
cw_fc = [18*mm, 70*mm, W - 18*mm - 70*mm]
story.append(table(fc17, cw_fc, row_colors=[(1,C_LGREEN),(2,C_LGREEN),(3,C_LGREEN)]))
story.append(sp(2))
story.append(p(
    "Three new fields must be added to <b>Skid_Parameters_Inputs</b> UDT: "
    "<b>WSpt_Fdbk : DInt</b>, <b>VArSpt_Fdbk : DInt</b>, <b>PFSpt_Fdbk : Real</b>. "
    "After this fix, Inv.WSpt / VArSpt / PFSpt are exclusively owned by PPC (command values). "
    "The inverter tracking confirmation is readable from Inps.*_Fdbk for HMI/SCADA comparison."
))
story.append(sp(3))

# ═══════════════════════════════════════════════════════════════════════════════
story.append(p("8.  IEC_WATCHDOG — FB_PPC_CONTROLLER INPUT", H2))

story.append(p(
    "<b>IEC_Watchdog : Bool</b> is the upstream SCADA / grid-operator communication alive signal "
    "wired directly to the <b>FB_PPC_Controller</b> input. "
    "When FALSE, the PPC controller stops following remote setpoints and enters safe mode "
    "(hold last setpoint or ramp to zero per plant policy). "
    "It is the software interlock that separates valid remote commands from stale or missing ones."
))
story.append(sp(2))

wd_states = [
    ["IEC_Watchdog", "Meaning", "PPC behaviour"],
    ["TRUE", "Upstream comms alive — setpoints valid and fresh",
     "Normal dispatch — follow Targets_P / Q / PF from SCADA"],
    ["FALSE", "Upstream link dead or data stale — timeout expired",
     "Safe mode — hold last setpoint or ramp to zero per plant policy.\nNo new commands issued to inverters."],
]
cw_wd = [25*mm, 60*mm, W - 25*mm - 60*mm]
story.append(table(wd_states, cw_wd,
    row_colors=[(1,C_LGREEN),(2,C_LRED)]))
story.append(sp(2))

story.append(p("Wiring options by upstream protocol:", BLD))
wd_wire = [
    ["Upstream link", "Wire IEC_Watchdog from"],
    ["IEC 60870-5-104 (CP module, e.g. CP 1543-1)",
     "CP_Block.Connected AND CP_Block.DataValid"],
    ["IEC 60870-5-104 software stack",
     "Stack connection status Bool + data-age check Bool"],
    ["Modbus TCP from SCADA (PLC as slave)",
     "Modbus server Connected output bit"],
    ["Profinet IO or OPC UA from EMS",
     "IO exchange quality bit / subscription active status"],
    ["Commissioning — no upstream SCADA yet",
     "Manual Bool bit e.g. %M300.0, set TRUE from HMI. NEVER hardwire TRUE in production."],
]
cw_ww = [70*mm, W - 70*mm]
story.append(table(wd_wire, cw_ww))
story.append(sp(2))

story.append(p("Recommended implementation — retriggerable TON timer (protocol-independent):", BLD))
story.append(code('// OB30 — SCADA_NewData = TRUE each time SCADA writes any new setpoint value'))
story.append(code('"IEC_WD_Timer"(IN := NOT "SCADA_NewData", PT := T#30S);'))
story.append(code('IEC_Watchdog := NOT "IEC_WD_Timer".Q;'))
story.append(code('// Timer.Q = TRUE → 30 s elapsed with no new data → IEC_Watchdog = FALSE'))
story.append(sp(2))

story.append(info_box(
    "<b>Why use a timer rather than just the TCP connection status:</b> A Modbus TCP or IEC 104 "
    "connection can remain open (TCP keepalive active) while the SCADA application has crashed "
    "or stopped sending updates. The timer catches 'connected but silent' failures that "
    "the connection status bit alone cannot detect.",
    C_GREY, C_DGREY
))
story.append(sp(2))

story.append(warn_box(
    "Never permanently hardwire IEC_Watchdog = TRUE in production. "
    "If the SCADA link fails with the watchdog forced TRUE, the PPC will continue dispatching "
    "the last received setpoints indefinitely with no alarm — a silent failure mode."
))
story.append(sp(3))

story.append(p("8.1  AuxCtl.LifeSign — SMA Inverter Application Watchdog", H3))
story.append(p(
    "Separate from IEC_Watchdog, the SMA Sunny Central monitors a <b>lifesign counter</b> "
    "that the PLC must increment every cycle. If it stops changing for the configured SMA "
    "parameter <b>WtTms</b> (typically 60 s), the inverter drops out of remote control mode "
    "and ignores Modbus setpoints — even if the TCP connection is still alive."
))
story.append(sp(1))

ls = [
    ["Item", "Detail"],
    ["SMA channel", "AuxCtl.LifeSign"],
    ["Direction", "PLC → Inverter (FC16 write)"],
    ["Data type", "S16 (Int)"],
    ["PLC action", "Increment by 1 every OB30 cycle; wrap 32767 → 0"],
    ["SMA timeout", "WtTms parameter (default 60 s — verify in SMA service menu)"],
    ["Readback", "Already mapped in Skid_Parameters_Inputs.AuxCtl.LifeSign (from FC17)"],
    ["Implementation", "Add State 7 to FB15 FSM, OR include address in State 4 block if contiguous"],
]
cw_ls = [45*mm, W - 45*mm]
story.append(table(ls, cw_ls, header_row=False,
    row_colors=[(0,C_NAVY),(1,C_GREY),(3,C_LAMBER),(6,C_LGREEN)]))
story.append(sp(4))

# ── footer ─────────────────────────────────────────────────────────────────────
story.append(hr())
story.append(p("PPC Energy  |  FB15 Write Sequence Data Routing  |  Rev 2.0  |  2026-06-04  "
               "|  Additions: FC17 fix, IEC_Watchdog, AuxCtl.LifeSign", SML))

# ── build ──────────────────────────────────────────────────────────────────────
doc.build(story)
print(f"PDF written to {OUTPUT}")
