#!/usr/bin/env python3
"""
Generate a Paradigm form term sheet (.docx) from deal parameters.

Usage:
    python3 generate.py '<JSON parameters>'
    python3 generate.py --file params.json

Output: Term Sheet - {Company} Series {X}.docx in the current directory.
"""

import json
import os
import sys
from copy import deepcopy
from pathlib import Path

try:
    from docx import Document
    from docx.shared import Pt, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH
except ImportError:
    print("ERROR: python-docx not installed. Run: pip install python-docx", file=sys.stderr)
    sys.exit(1)


DEFAULTS = {
    "no_shop_days": 30,
    "counsel_fee_cap": 75000,
    "qualified_ipo_threshold": 100000000,
    "founder_vesting_percent": 25,
    "founder_vesting_years": 4,
    "founder_cliff_months": 12,
    "auto_conversion_percent": 60,
    "protective_provisions_percent": 50,
    "equity_plan_shares": None,
    "board_seat": True,
    "observer_seat": True,
    "is_crypto": False,
}

REQUIRED = ["company_name", "series", "investment_amount", "post_money_valuation", "option_pool_percent"]


def fmt_dollars(n):
    """Format number as dollar string: $10,000,000."""
    if n is None:
        return "$[●]"
    return f"${n:,.0f}"


def fmt_pct(n):
    """Format number as percentage string."""
    if n is None:
        return "[●]%"
    if n == int(n):
        return f"{int(n)}%"
    return f"{n}%"


def fmt_number(n):
    """Format number with commas."""
    if n is None:
        return "[●]"
    return f"{n:,.0f}"


def add_heading(doc, text, level=1):
    h = doc.add_heading(text, level=level)
    return h


def add_para(doc, text, bold=False, italic=False):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold = bold
    run.italic = italic
    return p


def add_field(doc, label, value, indent=False):
    """Add a labeled field like 'Issuer: Acme Corp (the "Company").'"""
    p = doc.add_paragraph()
    if indent:
        p.paragraph_format.left_indent = Inches(0.5)
    run_label = p.add_run(f"{label}: ")
    run_label.bold = True
    p.add_run(value)
    return p


def add_bullet(doc, text, level=0):
    p = doc.add_paragraph(text, style="List Bullet")
    if level > 0:
        p.paragraph_format.left_indent = Inches(0.5 * (level + 1))
    return p


def generate(params):
    """Generate the term sheet document."""
    # Apply defaults
    p = {**DEFAULTS, **params}

    # Validate required fields
    missing = [f for f in REQUIRED if f not in p or p[f] is None]
    if missing:
        print(f"ERROR: Missing required fields: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    company = p["company_name"]
    series = p["series"]
    amount = p["investment_amount"]
    post_money = p["post_money_valuation"]
    pre_money = post_money - amount
    option_pool = p["option_pool_percent"]
    board_seat = p["board_seat"]
    observer_seat = p["observer_seat"]
    is_crypto = p["is_crypto"]
    no_shop = p["no_shop_days"]
    counsel_cap = p["counsel_fee_cap"]
    ipo_threshold = p["qualified_ipo_threshold"]
    founder_vested = p["founder_vesting_percent"]
    founder_years = p["founder_vesting_years"]
    founder_cliff = p["founder_cliff_months"]
    auto_convert_pct = p["auto_conversion_percent"]
    pp_pct = p["protective_provisions_percent"]
    equity_shares = p["equity_plan_shares"]

    # Board composition
    if board_seat:
        board_size = 5
        preferred_directors = 1
        common_directors = 2
        independent_directors = 1
        ceo_seat = True
    else:
        board_size = 3
        preferred_directors = 0
        common_directors = 2
        independent_directors = 0
        ceo_seat = True

    # ---- Build document ----
    doc = Document()

    # -- Styles --
    style = doc.styles["Normal"]
    font = style.font
    font.name = "Times New Roman"
    font.size = Pt(11)

    # ---- Title ----
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run(f"TERM SHEET\nFOR SERIES {series.upper()} PREFERRED STOCK FINANCING\nOF {company.upper()}")
    run.bold = True
    run.font.size = Pt(14)

    date_para = doc.add_paragraph()
    date_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    date_para.add_run("[●], 202[●]")

    disclaimer = doc.add_paragraph()
    disclaimer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = disclaimer.add_run(
        "This term sheet is non-binding and is intended solely as a summary of the terms that are currently proposed by the parties. "
        "Any party may terminate negotiations at any time for any reason. "
        "Only the sections titled \"Exclusivity / No Shop,\" \"Confidentiality,\" and \"Counsel and Expenses\" "
        "are intended to be legally binding."
    )
    run.italic = True
    run.font.size = Pt(9)

    doc.add_paragraph()  # spacer

    # ==== OFFERING TERMS ====
    add_heading(doc, "Offering Terms", level=1)

    add_field(doc, "Issuer", f'{company} (the "Company").')

    add_field(doc, "Investors",
              f'Paradigm ("Paradigm" or the "Lead Investor") (collectively with any additional investors, the "Investors").')

    add_field(doc, "Securities to be Issued",
              f'Shares of Series {series} Preferred Stock (the "Series {series} Preferred").')

    add_field(doc, "Aggregate Proceeds",
              f'{fmt_dollars(amount)} in total proceeds (the "Aggregate Proceeds").')

    add_field(doc, "Price Per Share",
              f'$[●] per share (the "Original Purchase Price"), based on a post-money valuation of '
              f'{fmt_dollars(post_money)}, assuming the issuance of all shares reserved under the Company\'s '
              f'equity incentive plan (the option pool representing {fmt_pct(option_pool)} of the post-money capitalization).')

    add_field(doc, "Pre-Money Valuation", f'{fmt_dollars(pre_money)}.')

    add_field(doc, "Post-Money Valuation", f'{fmt_dollars(post_money)}.')

    # ==== CHARTER PROVISIONS ====
    add_heading(doc, "Charter Provisions", level=1)

    add_field(doc, "Dividends",
              f'Dividends will be paid on the Series {series} Preferred on an as-converted basis '
              f'when, as, and if paid on the Common Stock. Non-cumulative.')

    add_field(doc, "Liquidation Preference",
              f'In the event of any liquidation, dissolution, or winding up of the Company, '
              f'the holders of the Series {series} Preferred shall be entitled to receive, '
              f'prior and in preference to any distribution to the holders of Common Stock, '
              f'an amount per share equal to the greater of (i) the Original Purchase Price '
              f'(plus declared but unpaid dividends) or (ii) such amount per share as would have been payable '
              f'had all shares of Series {series} Preferred been converted into Common Stock '
              f'immediately prior to such liquidation, dissolution, or winding up (non-participating preferred). '
              f'A merger, acquisition, or sale of all or substantially all of the assets of the Company '
              f'shall be deemed a liquidation event ("Deemed Liquidation Event").')

    add_field(doc, "Conversion",
              f'Each share of Series {series} Preferred may be converted at any time, '
              f'at the option of the holder, into shares of Common Stock. '
              f'The initial conversion rate shall be 1:1, subject to adjustment as provided herein.')

    auto_convert_text = (
        f'Each share of Series {series} Preferred will automatically convert into Common Stock upon: '
        f'(i) the closing of a firmly underwritten public offering with gross proceeds to the Company of '
        f'at least {fmt_dollars(ipo_threshold)} (a "Qualified IPO"); or '
        f'(ii) the consent of the holders of at least {fmt_pct(auto_convert_pct)} of the then-outstanding '
        f'shares of Series {series} Preferred.'
    )
    add_field(doc, "Automatic Conversion", auto_convert_text)

    add_field(doc, "Anti-Dilution Provisions",
              f'The conversion price of the Series {series} Preferred will be subject to '
              f'broad-based weighted average anti-dilution protection.')

    # Voting Rights
    add_field(doc, "Voting Rights",
              f'The holders of the Series {series} Preferred shall vote together with the holders of '
              f'Common Stock on an as-converted basis on all matters.')

    # Board Composition
    if board_seat:
        board_text = (
            f'The Board of Directors shall consist of {board_size} members comprised as follows: '
            f'({preferred_directors}) director elected by the holders of the Series {series} Preferred, '
            f'voting as a separate class (the "Series {series} Director"), who shall initially be a representative designated by Paradigm; '
            f'({common_directors}) directors elected by the holders of Common Stock; '
            f'(1) the Chief Executive Officer of the Company; '
        )
        if independent_directors:
            board_text += (
                f'and ({independent_directors}) independent director mutually agreed upon by the Common Stock and '
                f'the Series {series} Preferred.'
            )
    else:
        board_text = (
            f'The Board of Directors shall consist of {board_size} members comprised as follows: '
            f'({common_directors}) directors elected by the holders of Common Stock; '
            f'and (1) the Chief Executive Officer of the Company.'
        )

    if observer_seat and not board_seat:
        board_text += (
            f' Paradigm shall be entitled to appoint one observer to the Board of Directors, '
            f'who shall be entitled to attend and participate in all Board meetings in a non-voting capacity '
            f'and receive all information provided to Board members.'
        )
    elif observer_seat and board_seat:
        board_text += (
            f' In addition, Paradigm shall be entitled to appoint one observer to the Board of Directors, '
            f'who shall be entitled to attend and participate in all Board meetings in a non-voting capacity '
            f'and receive all information provided to Board members.'
        )

    add_field(doc, "Board Composition", board_text)

    # Protective Provisions
    pp_intro = (
        f'The consent of the holders of at least {fmt_pct(pp_pct)} of the Series {series} Preferred '
        f'shall be required for:'
    )
    add_field(doc, "Protective Provisions", pp_intro)

    pp_items = [
        "Any liquidation, dissolution, or winding up of the Company.",
        "Any amendment to the Certificate of Incorporation or Bylaws that adversely affects the Series Preferred.",
        "The creation or issuance of any security senior to or on parity with the Series Preferred.",
        "The reclassification of any existing security into a security senior to or on parity with the Series Preferred.",
        "Any purchase or redemption of any capital stock of the Company (except for repurchases at cost upon termination of service).",
        "The declaration or payment of any dividend or distribution on any capital stock.",
        "Any increase or decrease in the authorized number of directors on the Board.",
        "Any borrowing or guarantee of indebtedness in excess of $[●] (other than equipment financing and trade payables in the ordinary course).",
    ]
    if is_crypto:
        pp_items.append(
            "The issuance of any tokens or digital assets by the Company or any subsidiary "
            "(unless pursuant to a token warrant previously approved by the Board and the Series Preferred)."
        )

    for item in pp_items:
        add_bullet(doc, item)

    # Redemption
    add_field(doc, "Redemption",
              f'The Series {series} Preferred shall not be redeemable.')

    # ==== STOCK PURCHASE AGREEMENT ====
    add_heading(doc, "Stock Purchase Agreement", level=1)

    add_field(doc, "Representations and Warranties",
              "Standard representations and warranties by the Company, including but not limited to: "
              "organization, capitalization, authorization, financial statements, material contracts, "
              "intellectual property, litigation, compliance with laws, tax matters, and insurance. "
              "Standard sanctions, OFAC, and anti-corruption representations. "
              "Outbound investment compliance representation (31 C.F.R. Part 850).")

    add_field(doc, "Conditions to Closing",
              "Standard conditions to closing, including satisfactory completion of legal due diligence "
              "by counsel to the Investors, delivery of a legal opinion from counsel to the Company, "
              "execution and delivery of all transaction documents, and delivery of indemnification agreements "
              "and management rights letters.")

    add_field(doc, "Counsel and Expenses",
              f'The Company shall pay at the closing the reasonable fees and expenses of counsel to the Investors, '
              f'in an amount not to exceed {fmt_dollars(counsel_cap)}.')

    # ==== INVESTORS' RIGHTS AGREEMENT ====
    add_heading(doc, "Investors' Rights Agreement", level=1)

    add_field(doc, "Registration Rights", "")
    reg_items = [
        "Demand Rights: Beginning five (5) years after the closing or one hundred eighty (180) days after the Company's initial public offering, whichever is earlier.",
        "Piggyback Rights: Standard piggyback registration rights, subject to customary cutback provisions.",
        "S-3 Rights: Standard S-3 registration rights when the Company is eligible, with a minimum offering size of $5,000,000.",
    ]
    for item in reg_items:
        add_bullet(doc, item)

    add_field(doc, "Management and Information Rights",
              "Standard management rights. The Company will deliver to each Major Investor: "
              "(i) monthly financial statements within thirty (30) days of month-end; "
              "(ii) quarterly financial statements within forty-five (45) days of quarter-end; "
              "(iii) annual audited financial statements within one hundred twenty (120) days of fiscal year-end; "
              "and (iv) an annual budget at least thirty (30) days prior to the start of each fiscal year.")

    add_field(doc, "Right to Participate in Future Sales",
              "Each Major Investor shall have a right of first offer to purchase its pro rata share "
              "(based on as-converted percentage ownership) of any new equity securities issued by the Company, "
              "subject to customary exceptions.")

    if board_seat or observer_seat:
        rights_text = "Paradigm shall receive a management rights letter confirming"
        if board_seat:
            rights_text += " board participation rights"
        if board_seat and observer_seat:
            rights_text += " and"
        if observer_seat:
            rights_text += " board observer rights"
        rights_text += (
            ", information rights, and consultation rights sufficient to qualify its investment "
            "as a \"venture capital investment\" under the Plan Assets Regulation (29 C.F.R. § 2510.3-101)."
        )
        add_field(doc, "Management Rights Letter", rights_text)

    # Competitor carve-out
    add_field(doc, "Competitor Carve-Out",
              "In no event shall Paradigm or any of its Affiliates be deemed a \"Competitor\" "
              "for purposes of any provision of any transaction document.")

    # Section 220
    add_field(doc, "Inspection Rights",
              "Nothing in any transaction document shall constitute a waiver of Paradigm's rights "
              "under Section 220 of the Delaware General Corporation Law.")

    # ==== ROFR / CO-SALE ====
    add_heading(doc, "Right of First Refusal / Co-Sale Agreement", level=1)

    add_field(doc, "Right of First Refusal",
              "The Company shall have a right of first refusal (not assignable) with respect to "
              "any proposed transfer of shares by the Founders (the \"Key Holders\"). "
              "To the extent the Company does not exercise its right, the Major Investors shall have "
              "a secondary right of first refusal. "
              "The ROFR exercise period shall be thirty (30) days from notice.")

    add_field(doc, "Right of Co-Sale",
              "The Major Investors shall have a right of co-sale to participate on a pro rata basis "
              "in any proposed transfer of shares by the Key Holders, to the extent the right of first refusal "
              "is not exercised.")

    add_field(doc, "Founder Carveout",
              "Key Holders may transfer up to 2% of the Company's outstanding capital stock "
              "without triggering the right of first refusal or co-sale provisions.")

    add_field(doc, "Drag-Along Right",
              f'If the Board of Directors and the holders of a majority of the Series {series} Preferred '
              f'approve a sale of the Company, all shareholders shall be required to vote in favor of '
              f'and participate in such sale on the same terms and conditions.')

    # ==== VOTING AGREEMENT ====
    add_heading(doc, "Voting Agreement", level=1)

    add_field(doc, "Board Election",
              "The shareholders shall enter into a Voting Agreement to elect the Board of Directors "
              "as set forth in the \"Board Composition\" section above.")

    # ==== TOKEN WARRANT (crypto only) ====
    if is_crypto:
        add_heading(doc, "Token Warrant", level=1)

        add_field(doc, "Token Rights",
                  f'The Company shall issue to each Investor a warrant to purchase tokens (the "Token Warrant") '
                  f'in connection with any Token Generating Event ("TGE") undertaken by the Company or any subsidiary.')

        add_field(doc, "Exercise",
                  "The Token Warrant shall be exercisable at any time following the TGE. "
                  "The exercise price shall be nominal ($0.01 per token or such lesser amount as may apply). "
                  "Net exercise shall be the default exercise method.")

        add_field(doc, "Token Allocation",
                  "Each Investor's token allocation shall be pro rata based on its equity ownership percentage "
                  "multiplied by the Company's token reserve, with a minimum allocation of no less than "
                  "the Investor's pro rata share of 50% of total network tokens allocated to the Company.")

        add_field(doc, "Lockup",
                  "Tokens shall be subject to a lockup period of no less than one (1) year and no more than "
                  "four (4) years. The lockup shall be no more onerous than that applicable to insiders. "
                  "Any waiver of the insider lockup shall apply equally to the Investors.")

        add_field(doc, "Expiration",
                  "The Token Warrant shall expire on the earliest of (i) ten (10) years from issuance, "
                  "(ii) sixty (60) days following the TGE, or (iii) written notice of abandonment of token plans by the Company.")

        add_field(doc, "Smart Contract Restrictions",
                  "Any smart contract provisions affecting the Investors' token rights shall require "
                  "Paradigm's prior written consent.")

    # ==== OTHER MATTERS ====
    add_heading(doc, "Other Matters", level=1)

    founder_remaining = 100 - founder_vested if founder_vested else 75
    add_field(doc, "Founders' Stock",
              f'All shares of Common Stock held by the Founders shall be subject to vesting as follows: '
              f'{fmt_pct(founder_vested)} shall be deemed vested as of the closing; '
              f'the remaining {fmt_pct(founder_remaining)} shall vest in equal monthly installments over '
              f'{founder_years} years, subject to a {founder_cliff}-month cliff. '
              f'Upon a change of control, [●]% of each Founder\'s unvested shares shall immediately vest.')

    eq_shares_text = fmt_number(equity_shares) if equity_shares else "[●]"
    add_field(doc, "Equity Incentive Plan",
              f'The Company will maintain an equity incentive plan with {eq_shares_text} shares reserved '
              f'for issuance to employees, consultants, and advisors, representing '
              f'{fmt_pct(option_pool)} of the post-money capitalization.')

    add_field(doc, "Exclusivity / No Shop",
              f'The Company and the Founders agree that for a period of {no_shop} days from the date '
              f'of this term sheet, they will not, directly or indirectly, (i) solicit, initiate, or encourage '
              f'any inquiries or proposals for any equity financing, merger, sale of assets, or similar transaction, '
              f'or (ii) negotiate with or provide information to any third party in connection with any such transaction. '
              f'This section is legally binding.')

    add_field(doc, "Confidentiality",
              "The parties agree to keep the existence and terms of this term sheet confidential "
              "and shall not disclose such information to any third party without the prior written consent "
              "of the other parties, except to their respective advisors and counsel on a need-to-know basis. "
              "This section is legally binding.")

    # ==== NON-BINDING ====
    doc.add_paragraph()
    non_binding = doc.add_paragraph()
    run = non_binding.add_run(
        "This term sheet is non-binding and is intended solely as a summary of the principal terms "
        "proposed by the parties for discussion purposes. No legally binding obligations shall be created "
        "by this term sheet, except for the sections titled \"Exclusivity / No Shop,\" \"Confidentiality,\" "
        "and \"Counsel and Expenses,\" which are intended to be legally binding."
    )
    run.italic = True

    # ==== SIGNATURE BLOCKS ====
    doc.add_paragraph()
    doc.add_paragraph()

    # Company signature
    sig1 = doc.add_paragraph()
    sig1.add_run(company.upper()).bold = True
    doc.add_paragraph()
    doc.add_paragraph("By: _________________________________")
    doc.add_paragraph("Name: [●]")
    doc.add_paragraph("Title: [●]")

    doc.add_paragraph()
    doc.add_paragraph()

    # Paradigm signature
    sig2 = doc.add_paragraph()
    sig2.add_run("PARADIGM").bold = True
    doc.add_paragraph()
    doc.add_paragraph("By: _________________________________")
    doc.add_paragraph("Name: [●]")
    doc.add_paragraph("Title: [●]")

    # ---- Save ----
    output_dir = p.get("output_dir", os.getcwd())
    filename = f"Term Sheet - {company} Series {series}.docx"
    output_path = os.path.join(output_dir, filename)
    doc.save(output_path)
    print(output_path)
    return output_path


def main():
    if len(sys.argv) < 2:
        print("Usage: generate.py '<JSON>' or generate.py --file params.json", file=sys.stderr)
        sys.exit(1)

    if sys.argv[1] == "--file":
        with open(sys.argv[2]) as f:
            params = json.load(f)
    else:
        params = json.loads(sys.argv[1])

    generate(params)


if __name__ == "__main__":
    main()
