// License: GPLv3 Copyright: 2024, Kovid Goyal, <kovid at kovidgoyal.net>

// Package typesetter provides terminal typography and spacing design defaults
// for the OSC 66 text-sizing protocol. All sizes are expressed as multiples of
// the body cell unit — no rem, px, pt, or web/print units are used.
//
// # Unit system
//
// 1× base unit = 1 terminal cell row height.
// Body text = s=2 (2 cell rows, full visual height = 2 base units = "1× body").
//
// This allows superscript and subscript to stack vertically within the same
// inline row as body text: super occupies the top 1.25 cells of the 2-row
// block (v=0), sub occupies the bottom 1.25 cells (v=1). Both share s=2 with
// body text so they fit on the same terminal line.
//
// # Inline vs block layout
//
// Inline-safe levels (Inline==true) all use s=2 and can appear on the same
// terminal line as body text. The Pad values are fractional cell heights —
// they represent sub-row breathing room and must never be rounded to integers.
//
// Block-only levels (Inline==false) use s>2 and occupy their own lines.
// Spacing between block elements uses the integer VRows / HCols values.
package typesetter

// TypographyLevel describes OSC 66 parameters for one typographic role.
//
// OSC 66 escape sequence: \x1b]66;s=S:n=N:d=D:v=V:h=H;text\a
// When N==0 and D==0 the fraction is omitted (full scale).
type TypographyLevel struct {
	Name string

	// OSC 66 parameters
	S int // scale: cell-row occupancy (= Rows)
	N int // subscale numerator   (0 = no fraction)
	D int // subscale denominator (0 = no fraction)
	V int // vertical alignment: 0=top, 1=bottom, 2=center
	H int // horizontal alignment: 0=left, 1=right, 2=center

	Rows int // cell rows occupied (== S)

	// ScaleBody is the visual scale in body multiples (body=1.0).
	// ScaleCells is the visual scale in base cell heights (1 cell = 1.0).
	// ScaleCells = S * N/D  (or S when no fraction).
	// ScaleBody  = ScaleCells / 2.0  (since body = 2 base cells).
	ScaleBody  float64
	ScaleCells float64

	// PadTop and PadBot are the natural whitespace above/below the glyph
	// within its cell allocation, in base cell heights.
	//
	//   For v=2 (center):  PadTop = PadBot = (S - ScaleCells) / 2
	//   For v=0 (top):     PadTop = 0, PadBot = S - ScaleCells
	//   For v=1 (bottom):  PadTop = S - ScaleCells, PadBot = 0
	//
	// These are float64 values representing sub-row spacing. DO NOT round them.
	// They encode the intra-element breathing room automatically — no explicit
	// blank lines are needed around inline elements.
	PadTop float64
	PadBot float64

	// Inline is true when S==2: the level can be placed on the same terminal
	// line as body text (all inline levels share s=2).
	Inline bool
}

// SpacingToken describes a spacing tier in body-relative cell units.
type SpacingToken struct {
	Name string

	// VBody is the ideal vertical size in body-row multiples (float,
	// informational). Use VRows for actual blank-line emission.
	VBody float64

	// VRows is the number of blank lines to emit for vertical block spacing.
	// Sub-row gaps (VBody < 0.5) round to 0 — use HCols or fractional pad.
	VRows int

	// HCols is the number of space characters to emit for horizontal padding.
	HCols int

	Label string
}

// TypographyLevels lists all typographic roles in display order (h1 … subscript).
//
// Mathematical derivation of each entry:
//
//	body = s=2 full (visual 2 cells = 1× body)
//	ScaleCells = s × (n/d)   [n/d=1 when n=d=0]
//	ScaleBody  = ScaleCells / 2
//	n/d constraint: n < d (always), n,d ∈ [0,15], or both 0 for full scale
//	16 sub-unit grid: each cell = 16 sub-units; all ScaleCells × 16 are integers
var TypographyLevels = []TypographyLevel{
	// h1: 2.25× body = 4.5 cells → s=5, n=9, d=10  (5×9/10=4.5)
	{Name: "h1", S: 5, N: 9, D: 10, V: 2, H: 0, Rows: 5,
		ScaleBody: 2.25, ScaleCells: 4.5,
		PadTop: 0.25, PadBot: 0.25, Inline: false},

	// h2: 1.75× body = 3.5 cells → s=4, n=7, d=8   (4×7/8=3.5)
	{Name: "h2", S: 4, N: 7, D: 8, V: 2, H: 0, Rows: 4,
		ScaleBody: 1.75, ScaleCells: 3.5,
		PadTop: 0.25, PadBot: 0.25, Inline: false},

	// h3: 1.5× body = 3.0 cells → s=3, full (no fraction)
	{Name: "h3", S: 3, N: 0, D: 0, V: 0, H: 0, Rows: 3,
		ScaleBody: 1.5, ScaleCells: 3.0,
		PadTop: 0.0, PadBot: 0.0, Inline: false},

	// h4: 1.25× body = 2.5 cells → s=3, n=5, d=6   (3×5/6=2.5)
	{Name: "h4", S: 3, N: 5, D: 6, V: 2, H: 0, Rows: 3,
		ScaleBody: 1.25, ScaleCells: 2.5,
		PadTop: 0.25, PadBot: 0.25, Inline: false},

	// h5: 1.125× body = 2.25 cells → s=3, n=3, d=4  (3×3/4=2.25)
	{Name: "h5", S: 3, N: 3, D: 4, V: 2, H: 0, Rows: 3,
		ScaleBody: 1.125, ScaleCells: 2.25,
		PadTop: 0.375, PadBot: 0.375, Inline: false},

	// h6: same as body
	{Name: "h6", S: 2, N: 0, D: 0, V: 0, H: 0, Rows: 2,
		ScaleBody: 1.0, ScaleCells: 2.0,
		PadTop: 0.0, PadBot: 0.0, Inline: true},

	// body: 1× body = 2 cells → s=2, full
	{Name: "body", S: 2, N: 0, D: 0, V: 0, H: 0, Rows: 2,
		ScaleBody: 1.0, ScaleCells: 2.0,
		PadTop: 0.0, PadBot: 0.0, Inline: true},

	// label/caption: 0.75× body = 1.5 cells → s=2, n=3, d=4  (2×3/4=1.5)
	{Name: "label", S: 2, N: 3, D: 4, V: 2, H: 0, Rows: 2,
		ScaleBody: 0.75, ScaleCells: 1.5,
		PadTop: 0.25, PadBot: 0.25, Inline: true},

	{Name: "caption", S: 2, N: 3, D: 4, V: 2, H: 0, Rows: 2,
		ScaleBody: 0.75, ScaleCells: 1.5,
		PadTop: 0.25, PadBot: 0.25, Inline: true},

	// footnote: 0.6875× body = 1.375 cells → s=2, n=11, d=16  (2×11/16=1.375)
	{Name: "footnote", S: 2, N: 11, D: 16, V: 2, H: 0, Rows: 2,
		ScaleBody: 0.6875, ScaleCells: 1.375,
		PadTop: 0.3125, PadBot: 0.3125, Inline: true},

	// superscript: 0.625× body = 1.25 cells → s=2, n=5, d=8, v=0 (top)
	// PadTop=0 (flush top), PadBot = 2 - 1.25 = 0.75 cells
	{Name: "superscript", S: 2, N: 5, D: 8, V: 0, H: 0, Rows: 2,
		ScaleBody: 0.625, ScaleCells: 1.25,
		PadTop: 0.0, PadBot: 0.75, Inline: true},

	// subscript: 0.625× body = 1.25 cells → s=2, n=5, d=8, v=1 (bottom)
	// PadBot=0 (flush bottom), PadTop = 2 - 1.25 = 0.75 cells
	{Name: "subscript", S: 2, N: 5, D: 8, V: 1, H: 0, Rows: 2,
		ScaleBody: 0.625, ScaleCells: 1.25,
		PadTop: 0.75, PadBot: 0.0, Inline: true},
}

// SpacingTokens lists the 10-tier spacing scale in body-relative units.
//
// VRows and HCols are integers: blank lines and space characters to emit.
// VBody is the ideal fractional body-row size (informational float).
//
// Spacing in body rows (body = 2 cell rows):
//
//	sm  (0.5 body)  → 1 row  (minimum visible vertical gap)
//	lg  (1.5 body)  → 3 rows (1.5 × 2 = 3 cell rows)
//	xl  (2.0 body)  → 4 rows (2.0 × 2 = 4 cell rows)
var SpacingTokens = []SpacingToken{
	{Name: "2xs", VBody: 0.125, VRows: 0, HCols: 0, Label: "hairline; sub-grid only"},
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

// BodyCellRows is the number of terminal cell rows occupied by body text.
// All inline-safe typography levels share this s value.
const BodyCellRows = 2

// SubdivisionBits is the number of sub-units per cell row in the 16-grid.
// All ScaleCells values × SubdivisionBits are integers.
const SubdivisionBits = 16

// LevelByName returns the TypographyLevel with the given name, or false.
func LevelByName(name string) (TypographyLevel, bool) {
	for _, l := range TypographyLevels {
		if l.Name == name {
			return l, true
		}
	}
	return TypographyLevel{}, false
}

// SpacingByName returns the SpacingToken with the given name, or false.
func SpacingByName(name string) (SpacingToken, bool) {
	for _, s := range SpacingTokens {
		if s.Name == name {
			return s, true
		}
	}
	return SpacingToken{}, false
}
