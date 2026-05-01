"""
analyzer.py — Sends a drawing PDF to Claude and returns structured CRS data.
Indo Shell Cast Private Limited
"""

import base64
import json
import os
from typing import Any

import anthropic

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY environment variable is not set.")
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are the engineering analysis system for Indo Shell Cast Private Limited (ISC),
a precision shell-moulding foundry in Coimbatore, India.

Your job is to read a customer engineering drawing and fill out ISC's internal
CONTRACT REVIEW SHEET FOR ENQUIRY – RAW CASTING.

The sheet has 31 numbered items split across two pages:
  Page 1 (items 1–11): Technical review — for each item you produce:
    • "spec": what the drawing actually states (text for the E–H column)
    • "review": ISC's feasibility assessment (text for the I–N column)
  Page 2 (items 12–25): Cost estimation inputs — you produce:
    • "value": the known or "TBD" value (text spanning E–N)
  Page 2 (items 26–31): Risk analysis — you produce:
    • "label": short description label
    • "value": detailed risk analysis text

Rules:
- Return ONLY valid JSON — no prose, no markdown fences.
- Be thorough: extract every dimension, tolerance, note, marking from the drawing.
- For feasibility review column: write from ISC's perspective (what ISC can/cannot do).
- Use "Not specified" or "TBD" for genuinely absent information; never leave blank.
- Numbers stay as numbers in weight/quantity fields; everything else is a string.
"""

EXTRACTION_PROMPT = """Analyse the attached engineering drawing and return this exact JSON:

{
  "customer_name": "string",
  "enquiry_ref": "string  (drawing number, revision, date, drawn by, validated by — one line)",
  "end_use": "string  (product end use / application from drawing notes)",
  "source_of_information": "string  (drawing number, revision, scale, issuer)",
  "review_no": "string or null",

  "page1": [
    {
      "no": "1.",
      "description": "Component Name",
      "spec": "string  — part reference number, full name, application description from title block",
      "review": "string  — ISC feasibility comment on component geometry and shell-moulding suitability"
    },
    {
      "no": "2.",
      "description": "Drawing No. &\\nRevision Status",
      "spec": "string  — drawing number, current revision, date, drawn/validated by, latest 3 revision history entries if visible",
      "review": "string  — ISC comment on drawing clarity and revision status"
    },
    {
      "no": "3.",
      "description": "Material\\nSpecification",
      "spec": "string  — full material grade, type (e.g. SG Iron / Ductile Iron), min tensile, yield, elongation, heat treatment, surface treatment callouts",
      "review": "string  — ISC comment on whether material is within shell-moulding capability"
    },
    {
      "no": "4.",
      "description": "Casting Weight\\n(Kgs)",
      "spec": "string  — rough weight and finish weight as stated on drawing; note if not specified",
      "review": "string  — ISC comment on weight suitability for production capacity"
    },
    {
      "no": "5.",
      "description": "Casting Size\\nMM / INCHES",
      "spec": "string  — overall envelope dimensions, key diameters, bore sizes, wall thicknesses, all major features extracted from drawing views and sections",
      "review": "string  — ISC comment on size vs. machine envelope, cavity count"
    },
    {
      "no": "6.",
      "description": "Quantity Requirement\\n(Month / Year)",
      "spec": "string  — monthly and annual quantity as stated; 'Not specified' if absent",
      "review": "string  — ISC comment on capacity to meet volume"
    },
    {
      "no": "7.",
      "description": "Traceability &\\nIdentification\\nRequirements",
      "spec": "string  — all markings, logos, stamps, part references, orientation marks called out on drawing",
      "review": "string  — ISC comment on ability to incorporate markings in tooling"
    },
    {
      "no": "8.",
      "description": "Lead Time\\nRequirements\\n(PPAP/Samples)",
      "spec": "string  — lead time stated on drawing or enquiry; 'Not specified' if absent",
      "review": "string  — ISC standard lead time statement"
    },
    {
      "no": "9.",
      "description": "Tolerance\\nStandard\\nSpecified",
      "spec": "string  — general casting tolerance class, all specific tolerances called out, draft angles, parting line offset, edge treatment",
      "review": "string  — ISC comment on achievability of tolerances in shell moulding"
    },
    {
      "no": "10.",
      "description": "Machining\\nAllowances",
      "spec": "string  — stated machining allowances; ISC standard to apply if not stated; list surfaces requiring machining",
      "review": "string  — ISC standard machining allowance statement"
    },
    {
      "no": "11.",
      "description": "Other Special\\nRequirements\\n(HT / NDT /\\nCoating / etc.)",
      "spec": "string  — surface roughness Ra values, concentricity/GD&T callouts, NDT requirements, heat treatment, painting/coating, quality control documents referenced, draft angles, any other special notes",
      "review": "string  — ISC comment on critical control points and special process requirements"
    }
  ],

  "page2_cost": [
    {"no": "12.", "description": "Casting Weight",         "value": "string"},
    {"no": "13.", "description": "No. of Cavities",        "value": "string"},
    {"no": "14.", "description": "Pouring Weight",         "value": "string"},
    {"no": "15.", "description": "Shell Weight / Shot / Mould", "value": "string"},
    {"no": "16.", "description": "Core Weight",            "value": "string"},
    {"no": "17.", "description": "Filter Type & Size",     "value": "string"},
    {"no": "18.", "description": "Shell Backing",          "value": "string"},
    {"no": "19.", "description": "Machining Cost / Piece", "value": "string"},
    {"no": "20.", "description": "Painting Cost / Piece",  "value": "string"},
    {"no": "21.", "description": "Inhibitory IS",          "value": "string"},
    {"no": "22.", "description": "Heat Treatment",         "value": "string"},
    {"no": "23.", "description": "Pattern Development Tool","value": "string"},
    {"no": "24.", "description": "Additional Process",     "value": "string"},
    {"no": "25.", "description": "Machining Fixture Cost", "value": "string"}
  ],

  "page2_risk": [
    {
      "no": "26.",
      "description": "Implied requirements\\nnot stated by customer?",
      "value": "string  — list all implied requirements the customer hasn't explicitly stated"
    },
    {
      "no": "27.",
      "description": "Statutory / regulatory\\nrequirements?",
      "value": "string  — any regulatory, export, CE, RoHS requirements"
    },
    {
      "no": "28.",
      "description": "Potential risks\\ninvolved?",
      "value": "string  — identify key process and quality risks"
    },
    {
      "no": "29.",
      "description": "Explain risk &\\nmethods to overcome",
      "value": "string  — risk mitigation plan for each identified risk"
    },
    {
      "no": "30.",
      "description": "Product safety\\nrequirements?",
      "value": "string  — product safety and load-bearing considerations"
    },
    {
      "no": "31.",
      "description": "Customer-specific\\nrequirements?",
      "value": "string  — any customer QMS documents, PPAP level, special approvals"
    }
  ],

  "concluding_remarks": "string  — overall feasibility verdict, list of items pending customer input, recommended next steps"
}
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def analyze_drawing(pdf_bytes: bytes, filename: str) -> dict[str, Any]:
    """Send *pdf_bytes* to Claude and return the structured CRS data dict."""

    client = _get_client()
    pdf_b64 = base64.standard_b64encode(pdf_bytes).decode()

    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_b64,
                        },
                        "title": filename,
                    },
                    {
                        "type": "text",
                        "text": EXTRACTION_PROMPT,
                    },
                ],
            }
        ],
    )

    raw = message.content[0].text.strip()

    # Strip accidental markdown fences
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        raw = raw.rsplit("```", 1)[0]

    return json.loads(raw.strip())
