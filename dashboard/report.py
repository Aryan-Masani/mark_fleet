"""
report.py — Generates executive PDF and Markdown deployment reports
for selected Pareto-optimal fleet solutions.
"""

from __future__ import annotations
import io
from typing import Any, Dict, List
from fpdf import FPDF

from moqpso.encoding import DecodedPlan, VoyageAssignment, RouteInfo, VesselInfo


def generate_markdown_report(
    solution_idx: int,
    plan: DecodedPlan,
    vessels: List[VesselInfo],
    routes: List[RouteInfo],
    scenario_params: Dict[str, Any],
) -> str:
    """Produces a clean Markdown summary of the selected fleet deployment plan."""
    md = []
    md.append(f"# Green Fleet Deployment Strategy Report — Solution #{solution_idx + 1}")
    md.append(f"**Project**: SIH26138 Egreen Quanta | **Optimizer**: MOQPSO\n")

    md.append("## 1. Executive Summary & KPIs")
    md.append(f"- **Total Voyage Fuel Cost**: ${plan.raw_j1_cost:,.2f}")
    md.append(f"- **Total Lifecycle GHG Emissions**: {plan.raw_j2_emissions / 1000.0:,.2f} metric tons CO2eq")
    md.append(f"- **Schedule Reliability**: {plan.raw_j3_reliability:.0f} / {len(plan.assignments)} legs on-time")
    md.append(f"- **Total Unmet Cargo Demand**: {plan.total_unmet_demand:,.0f} tons")
    md.append(f"- **Regulatory CII Violations**: {plan.cii_violations} vessels")
    md.append(f"- **Port Fuel Availability Violations**: {plan.fuel_availability_violations}\n")

    md.append("## 2. Optimal Vessel-to-Route Assignments")
    md.append("| Vessel | Type | Route | Speed (kts) | Fuel | Cargo (t) | Load % | Transit (h) | On-Time | Cost ($) | GHG (t CO2eq) |")
    md.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for asgn in plan.assignments:
        md.append(
            f"| {asgn.vessel_id} | {asgn.vessel_type} | {asgn.route_id} | {asgn.speed_knots:.1f} | "
            f"{asgn.fuel_type} | {asgn.cargo_load_tons:,.0f} | {asgn.cargo_load_fraction*100:.0f}% | "
            f"{asgn.transit_time_hours:.1f} | {'Yes' if asgn.on_time else 'No'} | "
            f"${asgn.fuel_cost:,.0f} | {asgn.ghg_emissions_tons:,.1f} |"
        )
    md.append("\n")

    md.append("## 3. Scenario & Operational Configuration")
    md.append(f"- **Fleet Size**: {len(vessels)} vessels")
    md.append(f"- **Routes**: {len(routes)} voyage legs")
    for k, v in scenario_params.items():
        md.append(f"- **{k}**: {v}")
    md.append("\n")

    md.append("---\n*Generated autonomously by SIH26138 Egreen Quanta Dashboard.*")
    return "\n".join(md)


class FleetPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 8, "SIH26138 Egreen Quanta - Green Fleet Deployment Report", ln=True, align="C")
        self.set_font("Helvetica", "I", 9)
        self.set_text_color(100, 100, 100)
        self.cell(0, 5, "Multi-Objective Quantum-Inspired Fleet Optimization & Fuel Decarbonization", ln=True, align="C")
        self.line(10, 24, 200, 24)
        self.ln(6)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(140, 140, 140)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}} | Confidential Maritime Deployment Advisory", align="C")


def generate_pdf_report(
    solution_idx: int,
    plan: DecodedPlan,
    vessels: List[VesselInfo],
    routes: List[RouteInfo],
    scenario_params: Dict[str, Any],
) -> bytes:
    """Generates an executive PDF report using fpdf2."""
    pdf = FleetPDF(orientation="P", unit="mm", format="A4")
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # 1. Title Block
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(20, 35, 60)
    pdf.cell(0, 7, f"Executive Solution Summary - Pareto Strategy #{solution_idx + 1}", ln=True)
    pdf.ln(2)

    # 2. Key Metrics Cards (2x2 grid)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(240, 244, 248)
    pdf.set_draw_color(200, 210, 225)

    col_w = 46
    h = 12

    # Row 1
    pdf.cell(col_w, h, f" Cost: ${plan.raw_j1_cost:,.0f}", border=1, fill=True)
    pdf.cell(col_w, h, f" GHG: {plan.raw_j2_emissions/1000.0:,.1f} t CO2eq", border=1, fill=True)
    pdf.cell(col_w, h, f" On-Time: {plan.raw_j3_reliability:.0f}/{len(plan.assignments)} legs", border=1, fill=True)
    pdf.cell(col_w, h, f" Unmet: {plan.total_unmet_demand:,.0f} tons", border=1, fill=True, ln=True)

    pdf.ln(5)

    # 3. Allocation Table
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "Optimal Vessel-to-Route Deployment Table:", ln=True)
    pdf.ln(1)

    # Table Header
    pdf.set_font("Helvetica", "B", 7.5)
    pdf.set_fill_color(30, 58, 95)
    pdf.set_text_color(255, 255, 255)

    headers = [
        ("Vessel", 28),
        ("Route", 28),
        ("Spd (kts)", 16),
        ("Fuel", 20),
        ("Cargo (t)", 22),
        ("Load %", 14),
        ("Transit", 16),
        ("Cost ($)", 22),
        ("GHG (t)", 18),
    ]

    for title, width in headers:
        pdf.cell(width, 6, title, border=1, fill=True, align="C")
    pdf.ln()

    # Table Rows
    pdf.set_font("Helvetica", "", 7.5)
    pdf.set_text_color(20, 20, 20)

    fill = False
    for asgn in plan.assignments:
        pdf.set_fill_color(248, 250, 252) if fill else pdf.set_fill_color(255, 255, 255)
        pdf.cell(28, 5.5, f" {asgn.vessel_id}", border=1, fill=fill)
        pdf.cell(28, 5.5, f" {asgn.route_id}", border=1, fill=fill)
        pdf.cell(16, 5.5, f"{asgn.speed_knots:.1f}", border=1, fill=fill, align="C")
        pdf.cell(20, 5.5, f" {asgn.fuel_type}", border=1, fill=fill)
        pdf.cell(22, 5.5, f"{asgn.cargo_load_tons:,.0f}", border=1, fill=fill, align="R")
        pdf.cell(14, 5.5, f"{asgn.cargo_load_fraction*100:.0f}%", border=1, fill=fill, align="C")
        pdf.cell(16, 5.5, f"{asgn.transit_time_hours:.1f}h", border=1, fill=fill, align="C")
        pdf.cell(22, 5.5, f"${asgn.fuel_cost:,.0f}", border=1, fill=fill, align="R")
        pdf.cell(18, 5.5, f"{asgn.ghg_emissions_tons:,.1f}", border=1, fill=fill, align="R")
        pdf.ln()
        fill = not fill

    pdf.ln(5)

    # 4. Scenario Settings & Notes
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(20, 35, 60)
    pdf.cell(0, 6, "Operational Parameters & Regulatory Baseline:", ln=True)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(50, 50, 50)

    pdf.cell(0, 4.5, f"- Model Engine: {scenario_params.get('Prediction Model', 'Quantum-Inspired QIEA')}", ln=True)
    pdf.cell(0, 4.5, f"- Bunkering Policies: {scenario_params.get('Fuel Availability Policy', 'Port Constrained')}", ln=True)
    pdf.cell(0, 4.5, f"- Shore Power Cold-Ironing: {scenario_params.get('Shore Power Berth Toggles', 'Active at Selected Ports')}", ln=True)
    pdf.cell(0, 4.5, f"- Fuel Mix Policy: {scenario_params.get('Fuel Override Mode', 'Pareto Multi-Fuel Free Choice')}", ln=True)

    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 7.5)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(0, 4, "Notes: Predictions generated via trained black-box surrogate models. Emissions reflect well-to-wake lifecycle factors adhering to IMO MEPC guidelines. Optimizations performed via MOQPSO with mbest contraction-expansion dynamics.")

    pdf_out = pdf.output()
    return bytes(pdf_out) if isinstance(pdf_out, bytearray) else pdf_out

