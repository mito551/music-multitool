"""Chains: pick, edit and save presets; Add files queues one `chain` item per file."""
from __future__ import annotations

import os
from typing import Callable

from gi.repository import Adw, GLib, Gtk

from audiotoolkit.core.presets import Preset, Step, delete_preset, load_presets, save_preset, validate_preset

from . import TABS
from .base import ToolTab, combo, combo_value

ROLES = ["source", "audio", "stem:*", "stem:vocals", "stem:drums", "stem:bass", "stem:other", "midi", "lyrics", "analysis"]


def _dropdown(values: list[str], current: str, on_change: Callable[[str], None]) -> Gtk.DropDown:
    values = values if current in values else values + [current]
    dd = Gtk.DropDown.new_from_strings(values)
    dd.set_valign(Gtk.Align.CENTER)
    dd.set_selected(values.index(current))
    dd.connect("notify::selected", lambda d, _p: on_change(values[d.get_selected()]))
    return dd


class ChainsTab(ToolTab):
    kind = "chain"
    title = "Chains"
    icon = "insert-link-symbolic"

    def build(self, group) -> None:
        self.presets: dict[str, Preset] = {}
        self.steps: list[Step] = []
        self.name = ""
        self.dirty = False
        self._want = ""
        self._builtin = self._user = ""
        self._on_changed: Callable[[dict[str, Preset]], None] = lambda presets: None
        self._loading = False
        self.picker = combo("Preset", [])
        self.picker.connect("notify::selected", self._on_pick)
        group.add(self.picker)
        self.steps_box = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.steps_box.add_css_class("boxed-list")
        self.append(self.steps_box)
        self.status = Gtk.Label(xalign=0, wrap=True)
        self.append(self.status)
        row = Gtk.Box(spacing=6)
        for label, handler in (("Add step", self._add_step), ("Save as…", self._save_dialog), ("Delete", self._delete)):
            b = Gtk.Button(label=label)
            b.connect("clicked", handler)
            row.append(b)
        self.append(row)
        self.add_buttons()

    # -- wiring -------------------------------------------------------------------------------------------------

    def bind(self, builtin_dir: str, user_dir: str, on_changed: Callable[[dict[str, Preset]], None]) -> None:
        self._builtin, self._user, self._on_changed = builtin_dir, user_dir, on_changed
        self._reload(self._want)

    def get_opts(self) -> dict:
        return {"preset": self.name}

    def set_opts(self, opts: dict) -> None:
        self._want = opts.get("preset", "")
        if self.presets:
            self._select(self._want)

    def _reload(self, select: str) -> None:
        self.presets = load_presets(self._builtin, self._user)
        self._on_changed(self.presets)
        self._loading = True
        self.picker.set_model(Gtk.StringList.new(list(self.presets)))
        self._loading = False
        self._select(select if select in self.presets else next(iter(self.presets), ""))

    def _select(self, name: str) -> None:
        names = list(self.presets)
        if name in names:
            self._loading = True
            self.picker.set_selected(names.index(name))
            self._loading = False
        self.name = name
        self.steps = list(self.presets[name].steps) if name in self.presets else []
        self.dirty = False
        self._rebuild()

    def _on_pick(self, *_) -> None:
        if not self._loading and self.presets:
            self._select(combo_value(self.picker))

    # -- editing ------------------------------------------------------------------------------------------------

    def _touch(self) -> None:
        self.dirty = True
        GLib.idle_add(self._rebuild)

    def _rebuild(self) -> bool:
        while (child := self.steps_box.get_first_child()) is not None:
            self.steps_box.remove(child)
        for i, step in enumerate(self.steps):
            row = Adw.ActionRow(title=f"Step {i + 1}")
            row.add_suffix(_dropdown(list(TABS), step.kind, lambda k, i=i: self._set_kind(i, k)))
            row.add_suffix(_dropdown(ROLES, step.input, lambda r, i=i: self._set_input(i, r)))
            buttons = [("go-up-symbolic", "Move up", lambda i=i: self._move(i, -1)),
                       ("go-down-symbolic", "Move down", lambda i=i: self._move(i, 1)),
                       ("user-trash-symbolic", "Remove", lambda i=i: self._remove(i))]
            if TABS[step.kind].has_opts:
                buttons.insert(0, ("emblem-system-symbolic", "Options", lambda i=i: self._edit_opts(i)))
            for icon, tip, fn in buttons:
                b = Gtk.Button(icon_name=icon, tooltip_text=tip, valign=Gtk.Align.CENTER)
                b.connect("clicked", lambda *_, fn=fn: fn())
                row.add_suffix(b)
            self.steps_box.append(row)
        reason = self._blocking_reason()
        self.status.set_label(reason or "Ready")
        return GLib.SOURCE_REMOVE

    def _set_kind(self, i: int, kind: str) -> None:
        if self.steps[i].kind != kind:
            self.steps[i] = Step(kind, {}, self.steps[i].input)
            self._touch()

    def _set_input(self, i: int, role: str) -> None:
        if self.steps[i].input != role:
            self.steps[i] = Step(self.steps[i].kind, self.steps[i].opts, role)
            self._touch()

    def _move(self, i: int, d: int) -> None:
        j = i + d
        if 0 <= j < len(self.steps):
            self.steps[i], self.steps[j] = self.steps[j], self.steps[i]
            self._touch()

    def _remove(self, i: int) -> None:
        del self.steps[i]
        self._touch()

    def _add_step(self, *_) -> None:
        self.steps.append(Step("convert", {}, "source" if not self.steps else "audio"))
        self._touch()

    def _edit_opts(self, i: int) -> None:
        step = self.steps[i]
        form = TABS[step.kind](embedded=True)
        form.set_opts(step.opts)
        apply_btn = Gtk.Button(label="Apply", halign=Gtk.Align.END, margin_bottom=16, margin_end=24,
                               css_classes=["suggested-action"])
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_top=12, margin_start=24, margin_end=24)
        box.append(form)
        box.append(apply_btn)
        dialog = Adw.Dialog(title=f"Step {i + 1}: {step.kind}", child=box, content_width=480)

        def apply(*_):
            self.steps[i] = Step(step.kind, form.get_opts(), step.input)
            self._touch()
            dialog.close()

        apply_btn.connect("clicked", apply)
        dialog.present(self.get_root())

    # -- save / delete / run ------------------------------------------------------------------------------------

    def _errors(self) -> list[str]:
        return validate_preset(Preset(self.name, tuple(self.steps)), TABS)

    def _blocking_reason(self) -> str:
        if not self.name:
            return "Choose or save a preset first."
        if (errors := self._errors()):
            return "Fix: " + "; ".join(errors)
        if self.dirty:
            return "Unsaved changes: use Save as… before running."
        return ""

    def _save_dialog(self, *_) -> None:
        if (errors := self._errors()):
            self.status.set_label("Fix: " + "; ".join(errors))
            return
        entry = Gtk.Entry(text=self.name, activates_default=True)
        dialog = Adw.AlertDialog(heading="Save preset", body="Name for this chain")
        dialog.set_extra_child(entry)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("save", "Save")
        dialog.set_default_response("save")

        def done(_d, response):
            name = entry.get_text().strip()
            if response == "save" and name:
                save_preset(self._user, Preset(name, tuple(self.steps)))
                self._reload(name)

        dialog.connect("response", done)
        dialog.present(self.get_root())

    def _delete(self, *_) -> None:
        if delete_preset(self._user, self.name):
            self._reload("")
        else:
            self.status.set_label("Only your own presets can be deleted.")

    def _picked(self, files, result) -> None:
        if (reason := self._blocking_reason()):
            self.status.set_label(reason)
            return
        super()._picked(files, result)
