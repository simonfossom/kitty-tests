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
		Unit:          "1x base = 1 cell row; 1x body = 2 cell rows (s=2)",
		Subdivision:   SubdivisionBits,
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

// --- demo output ---

func runDemo() (rc int, err error) {
	lp, err := loop.New(loop.NoAlternateScreen)
	if err != nil {
		return 1, err
	}

	lp.OnInitialize = func() (string, error) {
		var b strings.Builder

		b.WriteString("\r\n")
		b.WriteString("  \x1b[1mtypesetter kitten\x1b[0m — OSC 66 typography defaults demo\r\n")
		b.WriteString("  Press any key to exit.\r\n\r\n")

		// Render each typography level
		for _, l := range TypographyLevels {
			label := fmt.Sprintf("%-12s  s=%-2d", l.Name, l.S)
			if l.N != 0 {
				label += fmt.Sprintf(" n=%-2d d=%-2d", l.N, l.D)
			} else {
				label += "           "
			}
			label += fmt.Sprintf("  %.3f× body", l.ScaleBody)
			sample := fmt.Sprintf("The quick brown fox  %s", label)
			b.WriteString("  ")
			b.WriteString(osc66(l, sample))
			b.WriteString("\r\n")
		}

		// Inline demo: body + superscript + subscript on the same line
		b.WriteString("\r\n")
		b.WriteString("  Inline demo (all s=2, same line):\r\n  ")

		body, _ := LevelByName("body")
		sup, _ := LevelByName("superscript")
		sub, _ := LevelByName("subscript")

		b.WriteString(osc66(body, "H"))
		b.WriteString(osc66(sub, "2"))
		b.WriteString(osc66(body, "O"))
		b.WriteString(osc66(sup, "2"))
		b.WriteString(osc66(body, "  (hydrogen peroxide: body + sub + sup in one s=2 row)"))
		b.WriteString("\r\n\r\n")

		// Spacing visual ruler
		b.WriteString("  Spacing tokens (horizontal):\r\n")
		for _, s := range SpacingTokens {
			pad := strings.Repeat(" ", s.HCols)
			b.WriteString(fmt.Sprintf("  %-5s |%s|  h=%d cols  v_body=%.3f\r\n",
				s.Name, pad, s.HCols, s.VBody))
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
