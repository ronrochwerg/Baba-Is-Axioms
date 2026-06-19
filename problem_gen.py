#!/usr/bin/env python3
"""
Tkinter-based level editor for a Baba Is You-style PDDL domain.

Features:
  * Ask for level width/height first (via CLI args or small console input).
  * Show a grid of cells of that size.
  * Palette of text blocks (ROCK, BABA, WALL, FLAG, IS, PUSH, YOU, STOP, WIN).
  * Palette of sprites (baba, flag, rock, wall).
  * Multiple sprites and text blocks per cell.
  * Export to PDDL problem file (with ASCII layout comment at top).
  * Save / load the layout as JSON.
  * Optional CLI: --load-layout <file.json> to pre-load a layout on startup.

Usage examples:

  Start a fresh 6x4 editor and save PDDL to baba-test1.pddl:
    python baba_pddl_gui.py --width 6 --height 4 --name baba-test1 --output baba-test1.pddl

  Start from an existing layout (dimensions come from JSON):
    python baba_pddl_gui.py --load-layout mylevel.json --name baba-test2 --output baba-test2.pddl
"""

import argparse
import json
from typing import List, Set, Tuple
import tkinter as tk
from tkinter import messagebox, filedialog as fd

# Text block words and sprite types in the domain
TEXT_WORDS: List[str] = ["rock", "baba", "wall", "flag", "is", "push", "you", "stop", "win"]
SPRITE_TYPES: List[str] = ["baba", "flag", "rock", "wall"]

TEXTBLOCK_TYPE_NAME = "textBlocks"


def loc_name(x: int, y: int) -> str:
    return f"loc-{x}-{y}"


def format_typed_object_list(
    names: List[str],
    type_name: str,
    indent: str = "    ",
    max_per_line: int = 8,
) -> List[str]:
    """Format a list of names as grouped typed objects in PDDL."""
    if not names:
        return []
    lines: List[str] = []
    for i in range(0, len(names), max_per_line):
        chunk = names[i : i + max_per_line]
        lines.append(f"{indent}{' '.join(chunk)} - {type_name}")
    return lines


def generate_connections(width: int, height: int) -> List[str]:
    """Generate (connected ...) facts for a rectangular grid."""
    facts: List[str] = []
    for y in range(height):
        for x in range(width):
            here = loc_name(x, y)
            # East / West
            if x + 1 < width:
                east = loc_name(x + 1, y)
                facts.append(f"(connected {here} {east} east)")
                facts.append(f"(connected {east} {here} west)")
            # South / North
            if y + 1 < height:
                south = loc_name(x, y + 1)
                facts.append(f"(connected {here} {south} south)")
                facts.append(f"(connected {south} {here} north)")
    return facts


# ---------- ASCII / LABEL HELPERS ----------

def make_cell_label(contents: Set[Tuple[str, str]]) -> str:
    """
    Create the short label used both in the GUI and the ASCII comment.

    - Sprites: first letter UPPERCASE
    - Text blocks: first letter lowercase
    - Multiple entries: concatenated, trimmed to at most 4 chars, with '+' if more.
    - Empty cell: "."
    """
    if not contents:
        return "."

    abbrevs: List[str] = []
    for kind, name in sorted(contents):
        if kind == "sprite":
            abbrev = name[0].upper()
        else:  # "text"
            abbrev = name[0].lower()
        abbrevs.append(abbrev)

    if len(abbrevs) <= 4:
        return "".join(abbrevs)
    else:
        return "".join(abbrevs[:4]) + "+"


def ascii_layout_from_cells(cells: List[List[Set[Tuple[str, str]]]]) -> str:
    """
    Build an ASCII representation of the level as a PDDL comment block.

    Each line is prefixed with '; ' so it's a PDDL comment.
    """
    height = len(cells)
    if height == 0:
        return "; (empty level)"

    width = len(cells[0])
    for row in cells:
        if len(row) != width:
            raise ValueError("All rows must have the same width in ascii_layout_from_cells.")

    lines: List[str] = []
    lines.append("; ASCII level layout (sprites: UPPER, text: lower)")
    lines.append(";")

    horiz = "+" + "+".join(["----"] * width) + "+"

    for y in range(height):
        if y == 0:
            lines.append("; " + horiz)
        cell_labels = [make_cell_label(cells[y][x]).ljust(4) for x in range(width)]
        row_str = "|".join(cell_labels)
        lines.append("; |" + row_str + "|")
        lines.append("; " + horiz)

    return "\n".join(lines)


# ---------- PDDL GENERATION ----------

def generate_pddl_from_cells(
    cells: List[List[Set[Tuple[str, str]]]],
    problem_name: str,
    domain_name: str,
) -> str:
    """
    cells[y][x] is a set of (kind, name) where kind in {"sprite", "text"}.

    Returns full PDDL with an ASCII comment block at the top.
    """
    height = len(cells)
    if height == 0:
        raise ValueError("Grid has height 0.")
    width = len(cells[0])
    for row in cells:
        if len(row) != width:
            raise ValueError("All rows must have the same width.")

    # Locations
    locs = [loc_name(x, y) for y in range(height) for x in range(width)]

    # Connectivity
    connected_facts = generate_connections(width, height)

    # Scan cells for sprites and text blocks
    sprite_objects: List[str] = []
    sprite_at_facts: List[str] = []
    sprite_type_facts: List[str] = []
    text_at_facts: List[str] = []

    sprite_counter = 1
    for y in range(height):
        for x in range(width):
            loc = loc_name(x, y)
            for kind, name in cells[y][x]:
                if kind == "sprite":
                    sprite_name = f"x{sprite_counter}"
                    sprite_counter += 1
                    sprite_objects.append(sprite_name)
                    sprite_at_facts.append(f"(at {sprite_name} {loc})")
                    sprite_type_facts.append(f"(is-type {sprite_name} {name})")
                elif kind == "text":
                    text_at_facts.append(f"(at {name} {loc})")
                else:
                    raise ValueError(f"Unknown kind '{kind}' in cell ({x}, {y}).")

    # ASCII comment
    ascii_comment = ascii_layout_from_cells(cells)

    # Build PDDL
    lines: List[str] = []
    lines.append(ascii_comment)
    lines.append("")  # blank line between comment and define
    lines.append(f"(define (problem {problem_name})")
    lines.append(f"  (:domain {domain_name})")

    # Objects
    lines.append("  (:objects")
    lines.extend(format_typed_object_list(locs, "location", indent="    "))
    if sprite_objects:
        lines.extend(format_typed_object_list(sprite_objects, "sprite", indent="    "))
    lines.append("  )")

    # Init
    lines.append("  (:init")
    for fact in connected_facts:
        lines.append(f"    {fact}")

    for fact in text_at_facts:
        lines.append(f"    {fact}")

    for fact in sprite_at_facts:
        lines.append(f"    {fact}")

    # Text type declarations: all known text words
    for word in TEXT_WORDS:
        lines.append(f"    (is-type {word} {TEXTBLOCK_TYPE_NAME})")

    for fact in sprite_type_facts:
        lines.append(f"    {fact}")

    lines.append("  )")

    # Goal (fixed for now)
    lines.append("  (:goal (won))")
    lines.append(")")

    return "\n".join(lines)


# ---------- EDITOR CLASS ----------

class LevelEditor:
    def __init__(
        self,
        width: int,
        height: int,
        problem_name: str,
        domain_name: str,
        output_path: str,
    ) -> None:
        self.width = width
        self.height = height
        self.problem_name = problem_name
        self.domain_name = domain_name
        self.output_path = output_path

        # cells[y][x] = set of (kind, name)
        self.cells: List[List[Set[Tuple[str, str]]]] = [
            [set() for _ in range(width)] for _ in range(height)
        ]
        self.buttons: List[List[tk.Button]] = [
            [None for _ in range(width)] for _ in range(height)
        ]  # type: ignore

        self.root = tk.Tk()
        self.root.title(f"Baba PDDL Level Editor – {width}x{height}")

        # Current tool: "sprite:baba", "text:rock", or "erase"
        self.current_tool = tk.StringVar(value="sprite:baba")

        self._build_ui()

    # ---------- UI BUILDING ----------

    def _build_ui(self) -> None:
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Left: grid
        grid_frame = tk.Frame(main_frame)
        grid_frame.pack(side=tk.LEFT, padx=10, pady=10)

        for y in range(self.height):
            for x in range(self.width):
                btn = tk.Button(
                    grid_frame,
                    text=".",
                    width=4,
                    height=2,
                    command=lambda x=x, y=y: self.on_cell_click(x, y),
                )
                btn.grid(row=y, column=x, padx=1, pady=1)
                self.buttons[y][x] = btn

        # Right: palette and controls
        palette_frame = tk.Frame(main_frame)
        palette_frame.pack(side=tk.LEFT, padx=10, pady=10, fill=tk.Y)

        tk.Label(
            palette_frame,
            text="Palette",
            font=("TkDefaultFont", 10, "bold"),
        ).pack(anchor="w")

        # Sprite palette
        tk.Label(palette_frame, text="Sprites").pack(anchor="w")
        for sprite in SPRITE_TYPES:
            value = f"sprite:{sprite}"
            tk.Radiobutton(
                palette_frame,
                text=f"{sprite}",
                variable=self.current_tool,
                value=value,
                anchor="w",
                justify=tk.LEFT,
            ).pack(anchor="w")

        # Text palette
        tk.Label(palette_frame, text="Text blocks").pack(anchor="w")
        for word in TEXT_WORDS:
            value = f"text:{word}"
            tk.Radiobutton(
                palette_frame,
                text=f"{word}",
                variable=self.current_tool,
                value=value,
                anchor="w",
                justify=tk.LEFT,
            ).pack(anchor="w")

        # Erase tool
        tk.Radiobutton(
            palette_frame,
            text="Erase (clear cell)",
            variable=self.current_tool,
            value="erase",
            anchor="w",
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(5, 10))

        # Info label
        info = (
            "Click a palette item,\n"
            "then click cells to toggle\n"
            "that item in the cell.\n"
            "Multiple items per cell are allowed."
        )
        tk.Label(palette_frame, text=info, justify=tk.LEFT).pack(anchor="w", pady=(0, 10))

        # Buttons: Save Layout, Load Layout, Generate PDDL
        btn_frame = tk.Frame(palette_frame)
        btn_frame.pack(anchor="center", pady=(10, 0), fill=tk.X)

        save_btn = tk.Button(
            btn_frame,
            text="Save Layout (JSON)",
            command=self.on_save_layout,
        )
        save_btn.pack(fill=tk.X, pady=(0, 5))

        load_btn = tk.Button(
            btn_frame,
            text="Load Layout (JSON)",
            command=self.on_load_layout,
        )
        load_btn.pack(fill=tk.X, pady=(0, 5))

        generate_btn = tk.Button(
            btn_frame,
            text="Generate PDDL",
            command=self.on_generate_pddl,
        )
        generate_btn.pack(fill=tk.X, pady=(10, 0))

    # ---------- CELL HANDLING ----------

    def on_cell_click(self, x: int, y: int) -> None:
        tool = self.current_tool.get()
        if tool == "erase":
            self.cells[y][x].clear()
        else:
            if ":" not in tool:
                return
            kind, name = tool.split(":", 1)
            key = (kind, name)
            if key in self.cells[y][x]:
                self.cells[y][x].remove(key)
            else:
                self.cells[y][x].add(key)
        self._update_cell_button(x, y)

    def _update_cell_button(self, x: int, y: int) -> None:
        label = make_cell_label(self.cells[y][x])
        self.buttons[y][x]["text"] = label

    # ---------- JSON SAVE / LOAD (GUI) ----------

    def _serialize_layout(self) -> dict:
        """Serialize the current layout to a JSON-friendly dict."""
        data = {
            "width": self.width,
            "height": self.height,
            "cells": [],
        }
        for y in range(self.height):
            row_data = []
            for x in range(self.width):
                # Store each (kind, name) as [kind, name]
                cell_list = [[kind, name] for (kind, name) in sorted(self.cells[y][x])]
                row_data.append(cell_list)
            data["cells"].append(row_data)
        return data

    def _load_layout_dict(self, data: dict) -> None:
        """Load layout from a dict (expects matching width/height)."""
        width = data.get("width")
        height = data.get("height")
        cells_data = data.get("cells")

        if width != self.width or height != self.height:
            raise ValueError(
                f"Layout dimensions {width}x{height} do not match current editor "
                f"{self.width}x{self.height}."
            )

        if len(cells_data) != self.height:
            raise ValueError("JSON cells height does not match the specified height.")
        for row in cells_data:
            if len(row) != self.width:
                raise ValueError("JSON cells width does not match the specified width.")

        # Clear and repopulate
        for y in range(self.height):
            for x in range(self.width):
                self.cells[y][x].clear()
                cell_list = cells_data[y][x]
                for pair in cell_list:
                    if not isinstance(pair, list) or len(pair) != 2:
                        raise ValueError("Cell entries must be [kind, name].")
                    kind, name = pair
                    self.cells[y][x].add((kind, name))
                self._update_cell_button(x, y)

    def on_save_layout(self) -> None:
        path = fd.asksaveasfilename(
            title="Save Layout as JSON",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return  # user cancelled

        data = self._serialize_layout()
        try:
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save layout:\n{e}")
            return

        messagebox.showinfo("Layout Saved", f"Layout saved to:\n{path}")

    def on_load_layout(self) -> None:
        path = fd.askopenfilename(
            title="Load Layout from JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return  # user cancelled

        try:
            with open(path, "r") as f:
                data = json.load(f)
            self._load_layout_dict(data)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load layout:\n{e}")
            return

        messagebox.showinfo("Layout Loaded", f"Layout loaded from:\n{path}")

    # ---------- PDDL GENERATION ----------

    def on_generate_pddl(self) -> None:
        try:
            pddl = generate_pddl_from_cells(
                self.cells,
                self.problem_name,
                self.domain_name,
            )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate PDDL:\n{e}")
            return

        try:
            with open(self.output_path, "w") as f:
                f.write(pddl)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to write file:\n{e}")
            return

        messagebox.showinfo(
            "Success",
            f"Wrote PDDL problem '{self.problem_name}' to:\n{self.output_path}",
        )

    def run(self) -> None:
        self.root.mainloop()


# ---------- CLI + MAIN ----------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Tkinter GUI to create Baba Is You PDDL problem files."
    )
    parser.add_argument("--width", type=int, help="Level width (number of columns).")
    parser.add_argument("--height", type=int, help="Level height (number of rows).")
    parser.add_argument("--name", default="test_problem", help="PDDL problem name.")
    parser.add_argument(
        "--domain",
        default="baba",
        help="PDDL domain name (default: baba).",
    )
    parser.add_argument(
        "--output",
        help="Output PDDL file path (default: <name>.pddl)",
    )
    parser.add_argument(
        "--load-layout",
        help="JSON layout file to pre-load into the editor.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    layout_data = None

    # If a layout is provided, use its dimensions (unless CLI dims conflict)
    if args.load_layout:
        try:
            with open(args.load_layout, "r") as f:
                layout_data = json.load(f)
        except Exception as e:
            print(f"Error: could not read layout file '{args.load_layout}': {e}")
            return

        lw = layout_data.get("width")
        lh = layout_data.get("height")
        if not isinstance(lw, int) or not isinstance(lh, int):
            print("Error: layout JSON missing integer 'width'/'height'.")
            return

        if args.width is not None and args.width != lw:
            print(
                f"Error: --width={args.width} does not match layout width {lw}. "
                "Omit --width or fix the layout."
            )
            return
        if args.height is not None and args.height != lh:
            print(
                f"Error: --height={args.height} does not match layout height {lh}. "
                "Omit --height or fix the layout."
            )
            return

        width = lw
        height = lh
    else:
        width = args.width
        height = args.height

        if width is None:
            while True:
                try:
                    width = int(input("Enter level width (columns): "))
                    if width <= 0:
                        print("Width must be positive.")
                        continue
                    break
                except ValueError:
                    print("Please enter a valid integer for width.")

        if height is None:
            while True:
                try:
                    height = int(input("Enter level height (rows): "))
                    if height <= 0:
                        print("Height must be positive.")
                        continue
                    break
                except ValueError:
                    print("Please enter a valid integer for height.")

    problem_name = args.name
    domain_name = args.domain
    output_path = args.output or f"problem_files/{problem_name}.pddl"

    editor = LevelEditor(width, height, problem_name, domain_name, output_path)

    # If we loaded layout_data from CLI, apply it now
    if layout_data is not None:
        try:
            editor._load_layout_dict(layout_data)
        except Exception as e:
            messagebox.showerror(
                "Error", f"Failed to apply layout from {args.load_layout}:\n{e}"
            )

    editor.run()


if __name__ == "__main__":
    main()
