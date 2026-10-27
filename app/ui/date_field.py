from __future__ import annotations

import calendar
from datetime import date, datetime

import customtkinter as ctk

from app.ui.theme import AMBER, AMBER_BRIGHT, BLACK_TEXT, BORDER, SURFACE_LOW, SURFACE_RAISED, TEXT, TEXT_DIM, sans
from app.utils.dates import br_to_iso, iso_to_br


class DateField(ctk.CTkFrame):
    """Brazilian date entry with an inline calendar (no secondary window)."""

    MONTHS_PT = (
        "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
    )
    WEEK_HEADER = ("S", "T", "Q", "Q", "S", "S", "D")

    def __init__(self, master, *, value=None, placeholder="DD/MM/AAAA", **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self._calendar_visible = False
        today = date.today()
        self._year = today.year
        self._month = today.month

        self.value_var = ctk.StringVar(value=iso_to_br(value))
        self.entry = ctk.CTkEntry(
            self,
            textvariable=self.value_var,
            placeholder_text=placeholder,
            height=42,
            font=sans(13),
        )
        self.entry.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(
            self,
            text="▦",
            width=44,
            height=42,
            command=self.toggle_calendar,
            fg_color=SURFACE_RAISED,
            hover_color=BORDER,
            text_color=TEXT,
            font=sans(16, "bold"),
        ).grid(row=0, column=1, padx=(6, 0))

        self.calendar_panel = ctk.CTkFrame(
            self, fg_color=SURFACE_LOW, border_width=1, border_color=BORDER, corner_radius=10
        )

    def get(self):
        return self.value_var.get().strip()

    def get_iso(self, field_name="Data"):
        return br_to_iso(self.get(), field_name)

    def set_iso(self, value):
        self.value_var.set(iso_to_br(value))
        if value:
            try:
                chosen = datetime.strptime(value, "%Y-%m-%d").date()
                self._year, self._month = chosen.year, chosen.month
            except ValueError:
                pass

    def toggle_calendar(self):
        if self._calendar_visible:
            self.hide_calendar()
        else:
            self.show_calendar()

    def show_calendar(self):
        # If the user already typed a valid date, open that month.
        try:
            current = datetime.strptime(self.get(), "%d/%m/%Y").date()
            self._year, self._month = current.year, current.month
        except ValueError:
            pass
        self._calendar_visible = True
        self.calendar_panel.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        self._render_calendar()

    def hide_calendar(self):
        self._calendar_visible = False
        self.calendar_panel.grid_forget()

    def _shift_month(self, delta):
        month = self._month + delta
        year = self._year
        if month < 1:
            month = 12
            year -= 1
        elif month > 12:
            month = 1
            year += 1
        self._year, self._month = year, month
        self._render_calendar()

    def _render_calendar(self):
        for child in self.calendar_panel.winfo_children():
            child.destroy()
        for col in range(7):
            self.calendar_panel.grid_columnconfigure(col, weight=1)

        ctk.CTkButton(
            self.calendar_panel, text="‹", width=32, height=30,
            command=lambda: self._shift_month(-1),
            fg_color="transparent", hover_color=SURFACE_RAISED, text_color=TEXT,
        ).grid(row=0, column=0, padx=4, pady=5)
        ctk.CTkLabel(
            self.calendar_panel,
            text=f"{self.MONTHS_PT[self._month - 1]} {self._year}",
            font=sans(12, "bold"), text_color=TEXT,
        ).grid(row=0, column=1, columnspan=5, sticky="ew")
        ctk.CTkButton(
            self.calendar_panel, text="›", width=32, height=30,
            command=lambda: self._shift_month(1),
            fg_color="transparent", hover_color=SURFACE_RAISED, text_color=TEXT,
        ).grid(row=0, column=6, padx=4, pady=5)

        for col, label in enumerate(self.WEEK_HEADER):
            ctk.CTkLabel(
                self.calendar_panel, text=label, font=sans(9, "bold"), text_color=TEXT_DIM
            ).grid(row=1, column=col, pady=(1, 3))

        month = calendar.Calendar(firstweekday=0).monthdayscalendar(self._year, self._month)
        today = date.today()
        for row_idx, week in enumerate(month, start=2):
            for col_idx, day in enumerate(week):
                if not day:
                    continue
                selected = date(self._year, self._month, day)
                is_today = selected == today
                ctk.CTkButton(
                    self.calendar_panel,
                    text=str(day),
                    width=32,
                    height=29,
                    command=lambda d=selected: self._select(d),
                    fg_color=AMBER if is_today else "transparent",
                    hover_color=AMBER_BRIGHT if is_today else SURFACE_RAISED,
                    text_color=BLACK_TEXT if is_today else TEXT,
                    font=sans(10, "bold" if is_today else "normal"),
                ).grid(row=row_idx, column=col_idx, padx=2, pady=2, sticky="ew")

    def _select(self, selected: date):
        self.value_var.set(selected.strftime("%d/%m/%Y"))
        self.hide_calendar()
