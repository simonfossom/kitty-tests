// License: GPLv3 Copyright: 2024, Kovid Goyal, <kovid at kovidgoyal.net>

package typesetter

import (
	"encoding/json"
	"fmt"
	"strings"

	"github.com/kovidgoyal/kitty/tools/cli"
	"github.com/kovidgoyal/kitty/tools/tui/loop"
)


// Options holds parsed CLI flags.
type Options struct {
	Format string
}

// osc66 returns the OSC 66 escape sequence for the given level and text.
//
// Format: \x1b]66;s=S:n=N:d=D:v=V:h=H;text\a
// When N==0 and D==0 the n/d params are omitted (full scale).
func osc66(lvl TypographyLevel, text string) string {
	var params strings.Builder
	fmt.Fprintf(&params, "s=%d", lvl.S)
	if lvl.N != 0 || lvl.D != 0 {
		fmt.Fprintf(&params, ":n=%d:d=%d", lvl.N, lvl.D)
	}
	fmt.Fprintf(&params, ":v=%d:h=%d", lvl.V, lvl.H)
	return fmt.Sprintf("\x1b]66;%s;%s\a", params.String(), text)
}

// --- JSON output ---

type jsonTypo struct {
	S          int     `json:"s"`
	N          int     `json:"n"`
	D          int     `json:"d"`
	V          int     `json:"v"`
	H          int     `json:"h"`
	Rows       int     `json:"rows"`
	ScaleBody  float64 `json:"scale_body"`
	ScaleCells float64 `json:"scale_cells"`
	PadTop     float64 `json:"pad_top"`
	PadBot     float64 `json:"pad_bot"`
	Inline     bool    `json:"inline"`
}

type jsonSpacing struct {
	VBody float64 `json:"v_body"`
	VRows int     `json:"v_rows"`
	HCols int     `json:"h_cols"`
	Label string  `json:"label"`
}

type jsonOutput struct {
	Version       string                `json:"version"`
	OSCCode       int                   `json:"osc_code"`
	Unit          string                `json:"unit"`
	Subdivision   int                   `json:"subdivision"`
	BodyBaseCells int                   `json:"body_base_cells"`
	Typography    map[string]jsonTypo   `json:"typography"`
	Spacing       map[string]jsonSpacing `json:"spacing"`
}

func outputJSON() error {
	typo := make(map[string]jsonTypo, len(TypographyLevels))
	for _, l := range TypographyLevels {
		typo[l.Name] = jsonTypo{
			S: l.S, N: l.N, D: l.D, V: l.V, H: l.H,
			Rows:       l.Rows,
			ScaleBody:  l.ScaleBody,
			ScaleCells: l.ScaleCells,
			PadTop:     l.PadTop,
			PadBot:     l.PadBot,
			Inline:     l.Inline,
		}
	}

	spacing := make(map[string]jsonSpacing, len(SpacingTokens))
	for _, s := range SpacingTokens {
		spacing[s.Name] = jsonSpacing{
			VBody: s.VBody,
			VRows: s.VRows,
			HCols: s.HCols,
			Label: s.Label,
		}
	}

	out := jsonOutput{
		Version:       "1",
		OSCCode:       66,
		Unit:          "body=1.6 cells (s=2,n=4/5); row=2 cells; super+sub=row",
		Subdivision:   CellSubunits,
		BodyBaseCells: BodyCellRows,
		Typography:    typo,
		Spacing:       spacing,
	}

	b, err := json.MarshalIndent(out, "", "  ")
	if err != nil {
		return err
	}
	fmt.Println(string(b))
	return nil
}

// --- env output ---

func outputEnv() {
	for _, l := range TypographyLevels {
		prefix := "TYPESETTER_" + strings.ToUpper(strings.ReplaceAll(l.Name, "-", "_"))
		fmt.Printf("%s_S=%d\n", prefix, l.S)
		fmt.Printf("%s_N=%d\n", prefix, l.N)
		fmt.Printf("%s_D=%d\n", prefix, l.D)
		fmt.Printf("%s_V=%d\n", prefix, l.V)
		fmt.Printf("%s_H=%d\n", prefix, l.H)
		fmt.Printf("%s_ROWS=%d\n", prefix, l.Rows)
		fmt.Printf("%s_SCALE_BODY=%.4g\n", prefix, l.ScaleBody)
		fmt.Printf("%s_SCALE_CELLS=%.4g\n", prefix, l.ScaleCells)
		fmt.Printf("%s_PAD_TOP=%.4g\n", prefix, l.PadTop)
		fmt.Printf("%s_PAD_BOT=%.4g\n", prefix, l.PadBot)
		if l.Inline {
			fmt.Printf("%s_INLINE=1\n", prefix)
		} else {
			fmt.Printf("%s_INLINE=0\n", prefix)
		}
	}
	for _, s := range SpacingTokens {
		prefix := "TYPESETTER_SPACING_" + strings.ToUpper(strings.ReplaceAll(s.Name, "-", "_"))
		fmt.Printf("%s_V_BODY=%.4g\n", prefix, s.VBody)
		fmt.Printf("%s_V_ROWS=%d\n", prefix, s.VRows)
		fmt.Printf("%s_H_COLS=%d\n", prefix, s.HCols)
	}
	fmt.Printf("TYPESETTER_BODY_BASE_CELLS=%d\n", BodyCellRows)
	fmt.Printf("TYPESETTER_SUBDIVISION=%d\n", SubdivisionBits)
}

// notationExpr renders a base character with simultaneous superscript and
// subscript: base^super_sub. All three share s=2 so they fit on the same
// terminal line. Super occupies the top cell row (v=0), sub the bottom (v=1).
//
// Layout (body = 2 rows, super = sub = 1 row each):
//
//	row 0: [base] [super...]
//	row 1: [base] [sub  ]
//
// After writing super, the cursor moves back (CSI D) to the start of super
// so that sub prints at the same horizontal columns — producing true stacking.
// All arguments must be printable ASCII (1 byte = 1 column).
func notationExpr(base, super, sub string) string {
	var b strings.Builder
	body, _ := LevelByName("body")
	supLvl, _ := LevelByName("superscript")
	subLvl, _ := LevelByName("subscript")

	b.WriteString(osc66(body, base))   // base: full body height
	b.WriteString(osc66(supLvl, super)) // super: top cell row only
	// cursor is now past super; move back to stack sub at same columns
	b.WriteString(fmt.Sprintf("\x1b[%dD", len(super)))
	b.WriteString(osc66(subLvl, sub)) // sub: bottom cell row only
	// advance cursor past the wider of the two (sub may be narrower than super)
	if advance := len(super) - len(sub); advance > 0 {
		b.WriteString(fmt.Sprintf("\x1b[%dC", advance))
	}
	return b.String()
}

// --- demo output ---

func runDemo() (rc int, err error) {
	lp, err := loop.New(loop.NoAlternateScreen)
	if err != nil {
		return 1, err
	}

	lp.OnInitialize = func() (string, error) {
		var b strings.Builder
		body, _ := LevelByName("body")
		sup, _ := LevelByName("superscript")
		sub, _ := LevelByName("subscript")

		b.WriteString("\r\n")
		b.WriteString("  \x1b[1mtypesetter kitten\x1b[0m — OSC 66 typography defaults\r\n")
		b.WriteString("  Press any key to exit.\r\n")

		// ── Notation examples ────────────────────────────────────────────────
		// These are the primary use case: simultaneous super + sub on the same
		// base character. Plain text / codeblocks cannot represent them.
		// All elements share s=2; super (n=1/2, v=0) occupies the top cell row,
		// sub (n=1/2, v=1) the bottom. super + sub = 1+1 = 2 = body. ✓
		b.WriteString("\r\n")
		b.WriteString("  \x1b[2m─── Notation (OSC 66 only — codeblocks cannot render these) ───\x1b[0m\r\n\r\n")

		type example struct{ label, base, super, sub string }
		sections := []struct {
			heading  string
			examples []example
		}{
			{"Computer Science", []example{
				{"Algorithm state", "S", "(t)", "k"},
				{"Graph theory",    "v", "i",   "j"},
				{"Neural network",  "h", "(l)", "i"},
			}},
			{"Economics", []example{
				{"Indexed variable", "P", "t", "i"},
				{"Panel data",       "Y", "t", "n"},
			}},
		}

		for _, sec := range sections {
			b.WriteString(fmt.Sprintf("  \x1b[1m%s\x1b[0m\r\n", sec.heading))
			for _, ex := range sec.examples {
				b.WriteString("    ")
				b.WriteString(osc66(body, ex.label+":  "))
				b.WriteString(notationExpr(ex.base, ex.super, ex.sub))
				b.WriteString(osc66(body, "   "))
				// show params inline
				b.WriteString(osc66(body, fmt.Sprintf(
					"base s=%d  |  super s=%d n=%d/d=%d v=%d  |  sub s=%d n=%d/d=%d v=%d",
					body.S,
					sup.S, sup.N, sup.D, sup.V,
					sub.S, sub.N, sub.D, sub.V,
				)))
				b.WriteString("\r\n")
			}
			b.WriteString("\r\n")
		}

		// ── Typography scale ─────────────────────────────────────────────────
		b.WriteString("  \x1b[2m─── Typography scale ───────────────────────────────────────────\x1b[0m\r\n\r\n")
		for _, l := range TypographyLevels {
			frac := "        "
			if l.N != 0 {
				frac = fmt.Sprintf("n=%d/d=%d ", l.N, l.D)
			}
			label := fmt.Sprintf("%-12s s=%d %s %.4g× body", l.Name, l.S, frac, l.ScaleBody)
			b.WriteString("  ")
			b.WriteString(osc66(l, "Aa  "+label))
			b.WriteString("\r\n")
		}
		b.WriteString("\r\n")

		// ── Spacing ruler ────────────────────────────────────────────────────
		b.WriteString("  \x1b[2m─── Spacing tokens (horizontal cols) ──────────────────────────\x1b[0m\r\n\r\n")
		for _, s := range SpacingTokens {
			pad := strings.Repeat(" ", s.HCols)
			b.WriteString(fmt.Sprintf("  %-5s |%s|  h=%2d cols  v=%d rows  (%.3f× body)\r\n",
				s.Name, pad, s.HCols, s.VRows, s.VBody))
		}
		b.WriteString("\r\n")

		return b.String(), nil
	}

	lp.OnKeyEvent = func(event *loop.KeyEvent) error {
		event.Handled = true
		lp.Quit(0)
		return nil
	}

	err = lp.Run()
	if err != nil {
		return 1, err
	}
	return lp.ExitCode(), nil
}

// --- entry point ---

func main(cmd *cli.Command, opts *Options, args []string) (rc int, err error) {
	switch strings.ToLower(opts.Format) {
	case "json", "":
		if err = outputJSON(); err != nil {
			return 1, err
		}
	case "env":
		outputEnv()
	case "demo":
		return runDemo()
	default:
		return 1, fmt.Errorf("unknown format %q; choose json, env, or demo", opts.Format)
	}
	return 0, nil
}

// EntryPoint registers the typesetter subcommand with the kitty CLI.
func EntryPoint(parent *cli.Command) {
	sc := parent.AddSubCommand(&cli.Command{
		Name:             "typesetter",
		ShortDescription: "Output terminal typography and spacing design defaults (OSC 66)",
		HelpText: `Output the typesetter kitten's design defaults: OSC 66 parameters for a
principled typography scale plus integer cell-unit spacing values.

All sizes are expressed as multiples of the body cell unit (s=2, 2 cell rows).
No rem, px, pt, or web/print units are used.

Other terminal apps can consume this output to get consistent, accessible
typography without re-deriving the math:

    kitten typesetter | jq '.typography.h1'
    eval "$(kitten typesetter --format env)"
    kitten typesetter --format demo
`,
		Run: func(cmd *cli.Command, args []string) (rc int, err error) {
			opts := Options{}
			if err = cmd.GetOptionValues(&opts); err != nil {
				return 1, err
			}
			return main(cmd, &opts, args)
		},
	})

	sc.Add(cli.OptionSpec{
		Name:    "--format",
		Dest:    "Format",
		Type:    "string",
		Default: "json",
		Choices: "json,env,demo",
		Help:    "Output format: json (default), env (shell-sourceable), or demo (visual render in terminal).",
	})
}
