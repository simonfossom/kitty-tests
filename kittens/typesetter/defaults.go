// License: GPLv3 Copyright: 2024, Kovid Goyal, <kovid at kovidgoyal.net>

// Package typesetter provides terminal typography and spacing design defaults
// for the OSC 66 text-sizing protocol. All sizes are expressed as multiples of
// the body text visual height — no rem, px, pt, or web/print units are used.
//
// # Core math
//
// Standard typography places superscript and subscript at 0.625× body size.
// For them to stack and fill exactly one row together:
//
//	super + sub = row height
//	0.625 + 0.625 = 1.25 × body
//	∴ row = 1.25 × body
//	∴ body = row / 1.25 = 0.8 × row = 4/5 of the cell allocation
//
// In OSC 66 terms (s=2 cell rows per body line):
//
//	row    = s = 2 cells
//	body   = 2 × 4/5 = 1.6 cells   (n=4, d=5, v=2)
//	super  = 2 × 1/2 = 1.0 cells   (n=1, d=2, v=0)  →  1.0/1.6 = 0.625× body ✓
//	sub    = 2 × 1/2 = 1.0 cells   (n=1, d=2, v=1)  →  1.0/1.6 = 0.625× body ✓
//	super + sub = 2.0 = row ✓
//
// Body text is NOT full row height. The 0.2-cell padding top and bottom is the
// typographic line spacing that gives body text its natural breathing room.
//
// # Sub-unit grid
//
// 1 base cell = 10 sub-units; body = 16 sub-units (1.6 cells × 10 = 16).
// Every visual scale in the system is an even multiple of 2 sub-units:
//
//	super/sub:     10 sub-units  (1.0 cells)
//	label/caption: 12 sub-units  (1.2 cells)
//	body/h6:       16 sub-units  (1.6 cells)
//	h5:            18 sub-units  (1.8 cells)
//	h4:            20 sub-units  (2.0 cells)
//	h3:            24 sub-units  (2.4 cells)
//	h2:            28 sub-units  (2.8 cells)
//	h1:            36 sub-units  (3.6 cells)
//
// # Inline vs block layout
//
// All inline-safe levels (Inline==true) use s=2 and can share a terminal line
// with body text. PadTop/PadBot are float64 sub-row values — DO NOT round them;
// they encode the intra-element breathing room via the fractional scale.
// Block-only levels (Inline==false) use s>2 and occupy their own lines.
package typesetter

// TypographyLevel describes OSC 66 parameters for one typographic role.
//
// OSC 66 escape: \x1b]66;s=S:n=N:d=D:v=V:h=H;text\a
// Omit n/d when both are zero (full scale).
type TypographyLevel struct {
	Name string

	// OSC 66 parameters
	S int // scale: cell-row occupancy (= Rows)
	N int // subscale numerator   (0 = no fraction → full scale)
	D int // subscale denominator (0 = no fraction → full scale)
	V int // vertical alignment: 0=top, 1=bottom, 2=center
	H int // horizontal alignment: 0=left, 1=right, 2=center

	Rows int // cell rows occupied (== S)

	// ScaleCells: visual height in base cell units.  = S × N/D  (or S when N=D=0).
	// ScaleBody:  visual height as a multiple of body text.  = ScaleCells / 1.6
	//             (body = 1.6 cells = s=2, n=4/5)
	ScaleCells float64
	ScaleBody  float64

	// PadTop, PadBot: natural whitespace above/below the glyph within its cell
	// allocation, in base cell units.
	//
	//   v=2 (center):  PadTop = PadBot = (S - ScaleCells) / 2
	//   v=0 (top):     PadTop = 0,  PadBot = S - ScaleCells
	//   v=1 (bottom):  PadTop = S - ScaleCells,  PadBot = 0
	//
	// These are floats representing sub-row spacing. Never round them.
	PadTop float64
	PadBot float64

	// Inline is true when S==2: can be placed on the same terminal line as body text.
	Inline bool
}

// SpacingToken describes a spacing tier in body-relative cell units.
type SpacingToken struct {
	Name string

	// VBody: ideal size in body-row multiples (float, informational only).
	VBody float64

	// VRows: blank lines to emit for vertical block spacing (integer).
	// Sub-row gaps (VBody < 0.5× body) round to 0 — use HCols or fractional pad.
	// 1 body row = 2 cell rows (s=2), so VRows = round(VBody × 2).
	VRows int

	// HCols: space characters to emit for horizontal padding (integer).
	HCols int

	Label string
}

// TypographyLevels lists every typographic role in display order (h1 → subscript).
//
// All visual sizes in base cells (ScaleCells) are multiples of 0.2 (= 2 sub-units),
// derived from the core math: body = 1.6 cells, scale × body = target cells.
//
//	n/d constraints: n < d always; n,d ∈ [0,15]; or both 0 for full scale.
var TypographyLevels = []TypographyLevel{

	// h1: 2.25× body = 3.6 cells → s=4, n=9, d=10  (4 × 9/10 = 3.6)
	// pad = (4 − 3.6) / 2 = 0.2 each side
	{Name: "h1", S: 4, N: 9, D: 10, V: 2, H: 0, Rows: 4,
		ScaleCells: 3.6, ScaleBody: 2.25,
		PadTop: 0.2, PadBot: 0.2, Inline: false},

	// h2: 1.75× body = 2.8 cells → s=4, n=7, d=10  (4 × 7/10 = 2.8)
	// pad = (4 − 2.8) / 2 = 0.6 each side
	{Name: "h2", S: 4, N: 7, D: 10, V: 2, H: 0, Rows: 4,
		ScaleCells: 2.8, ScaleBody: 1.75,
		PadTop: 0.6, PadBot: 0.6, Inline: false},

	// h3: 1.5× body = 2.4 cells → s=3, n=4, d=5    (3 × 4/5 = 2.4)  ← same n/d as body
	// pad = (3 − 2.4) / 2 = 0.3 each side
	{Name: "h3", S: 3, N: 4, D: 5, V: 2, H: 0, Rows: 3,
		ScaleCells: 2.4, ScaleBody: 1.5,
		PadTop: 0.3, PadBot: 0.3, Inline: false},

	// h4: 1.25× body = 2.0 cells → s=3, n=2, d=3   (3 × 2/3 = 2.0)
	// pad = (3 − 2.0) / 2 = 0.5 each side
	{Name: "h4", S: 3, N: 2, D: 3, V: 2, H: 0, Rows: 3,
		ScaleCells: 2.0, ScaleBody: 1.25,
		PadTop: 0.5, PadBot: 0.5, Inline: false},

	// h5: 1.125× body = 1.8 cells → s=3, n=3, d=5  (3 × 3/5 = 1.8)
	// pad = (3 − 1.8) / 2 = 0.6 each side
	{Name: "h5", S: 3, N: 3, D: 5, V: 2, H: 0, Rows: 3,
		ScaleCells: 1.8, ScaleBody: 1.125,
		PadTop: 0.6, PadBot: 0.6, Inline: false},

	// h6: same visual size as body, but as a heading it uses explicit v=2 centering
	// for the same 0.2-cell top/bottom breathing room.
	// 1.0× body = 1.6 cells → s=2, n=4, d=5        (2 × 4/5 = 1.6)
	// pad = (2 − 1.6) / 2 = 0.2 each side
	{Name: "h6", S: 2, N: 4, D: 5, V: 2, H: 0, Rows: 2,
		ScaleCells: 1.6, ScaleBody: 1.0,
		PadTop: 0.2, PadBot: 0.2, Inline: true},

	// body: 1.0× body = 1.6 cells → s=2, n=4, d=5  (2 × 4/5 = 1.6)
	// Body is NOT full row height. It occupies 80% of its 2-cell allocation,
	// leaving 0.2 cells of natural line spacing above and below.
	// pad = (2 − 1.6) / 2 = 0.2 each side
	{Name: "body", S: 2, N: 4, D: 5, V: 2, H: 0, Rows: 2,
		ScaleCells: 1.6, ScaleBody: 1.0,
		PadTop: 0.2, PadBot: 0.2, Inline: true},

	// label: 0.75× body = 1.2 cells → s=2, n=3, d=5  (2 × 3/5 = 1.2)
	// pad = (2 − 1.2) / 2 = 0.4 each side
	{Name: "label", S: 2, N: 3, D: 5, V: 2, H: 0, Rows: 2,
		ScaleCells: 1.2, ScaleBody: 0.75,
		PadTop: 0.4, PadBot: 0.4, Inline: true},

	// caption: same as label
	{Name: "caption", S: 2, N: 3, D: 5, V: 2, H: 0, Rows: 2,
		ScaleCells: 1.2, ScaleBody: 0.75,
		PadTop: 0.4, PadBot: 0.4, Inline: true},

	// footnote: target 0.6875× body = 1.1 cells.
	// Closest exact OSC 66 value with d ≤ 15: n=5, d=9 → 2×5/9 = 10/9 ≈ 1.111 cells
	// ScaleBody ≈ 0.694 (≈ 1% from target 0.6875; no exact representation exists
	// for 0.55 = 11/20 within the d ≤ 15 protocol constraint).
	// pad = (2 − 10/9) / 2 = 4/9 ≈ 0.444 each side
	{Name: "footnote", S: 2, N: 5, D: 9, V: 2, H: 0, Rows: 2,
		ScaleCells: 10.0 / 9.0, ScaleBody: 10.0 / 14.4,
		PadTop: 4.0 / 9.0, PadBot: 4.0 / 9.0, Inline: true},

	// superscript: 0.625× body = 1.0 cell → s=2, n=1, d=2, v=0 (top-aligned)
	// super + sub = 1.0 + 1.0 = 2.0 = row  ✓
	// super / body = 1.0 / 1.6 = 0.625  ✓
	// PadTop = 0 (flush to top), PadBot = 2 − 1.0 = 1.0 (bottom cell is empty)
	{Name: "superscript", S: 2, N: 1, D: 2, V: 0, H: 0, Rows: 2,
		ScaleCells: 1.0, ScaleBody: 0.625,
		PadTop: 0.0, PadBot: 1.0, Inline: true},

	// subscript: 0.625× body = 1.0 cell → s=2, n=1, d=2, v=1 (bottom-aligned)
	// PadBot = 0 (flush to bottom), PadTop = 2 − 1.0 = 1.0 (top cell is empty)
	{Name: "subscript", S: 2, N: 1, D: 2, V: 1, H: 0, Rows: 2,
		ScaleCells: 1.0, ScaleBody: 0.625,
		PadTop: 1.0, PadBot: 0.0, Inline: true},
}

// SpacingTokens lists the 10-tier spacing scale.
//
// VRows = round(VBody × BodyCellRows). One body row = 2 cell rows (s=2).
// Sub-row vertical gaps (2xs, xs) round to 0 — expressed via PadTop/PadBot.
var SpacingTokens = []SpacingToken{
	{Name: "2xs", VBody: 0.125, VRows: 0, HCols: 0, Label: "hairline; sub-row only"},
	{Name: "xs", VBody: 0.25, VRows: 0, HCols: 1, Label: "icon-to-label gap"},
	{Name: "sm", VBody: 0.5, VRows: 1, HCols: 2, Label: "tight element gap"},
	{Name: "md", VBody: 0.75, VRows: 1, HCols: 3, Label: "input / button padding"},
	{Name: "base", VBody: 1.0, VRows: 2, HCols: 4, Label: "component padding"},
	{Name: "lg", VBody: 1.5, VRows: 3, HCols: 6, Label: "section-inner gap"},
	{Name: "xl", VBody: 2.0, VRows: 4, HCols: 8, Label: "between components"},
	{Name: "2xl", VBody: 3.0, VRows: 6, HCols: 12, Label: "between major sections"},
	{Name: "3xl", VBody: 4.0, VRows: 8, HCols: 16, Label: "layout-level gaps"},
	{Name: "4xl", VBody: 5.0, VRows: 10, HCols: 20, Label: "page margins"},
}

// BodyCellRows is the s value for body text (cell rows allocated per body line).
const BodyCellRows = 2

// BodyVisualCells is the actual rendered height of body text in base cell units.
// = BodyCellRows × 4/5 = 1.6 cells.  Body does NOT fill the full row.
const BodyVisualCells = 1.6

// CellSubunits is the number of sub-units per base cell row in the grid.
// body (1.6 cells) × CellSubunits = 16 sub-units.
const CellSubunits = 10

// SubdivisionBits is kept for API compatibility; use CellSubunits for new code.
const SubdivisionBits = CellSubunits

// LevelByName returns the TypographyLevel with the given name, or (zero, false).
func LevelByName(name string) (TypographyLevel, bool) {
	for _, l := range TypographyLevels {
		if l.Name == name {
			return l, true
		}
	}
	return TypographyLevel{}, false
}

// SpacingByName returns the SpacingToken with the given name, or (zero, false).
func SpacingByName(name string) (SpacingToken, bool) {
	for _, s := range SpacingTokens {
		if s.Name == name {
			return s, true
		}
	}
	return SpacingToken{}, false
}
