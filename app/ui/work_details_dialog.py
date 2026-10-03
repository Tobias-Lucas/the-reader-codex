import customtkinter as ctk
from tkinter import messagebox


class WorkDetailsDialog(ctk.CTkToplevel):
    def __init__(self, master, repository, work, on_saved):
        super().__init__(master)

        self.repository = repository
        self.work = work
        self.on_saved = on_saved

        self.title(f"Detalhes — {work.name}")
        self.geometry("580x680")
        self.transient(master)
        self.grab_set()

        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self,
            text=work.name,
            font=("Arial", 24, "bold"),
        ).grid(
            row=0,
            column=0,
            sticky="w",
            padx=24,
            pady=(24, 4),
        )

        self.favorite_var = ctk.BooleanVar(
            value=work.favorite
        )

        ctk.CTkCheckBox(
            self,
            text="⭐ Favorito",
            variable=self.favorite_var,
        ).grid(
            row=1,
            column=0,
            sticky="w",
            padx=24,
            pady=8,
        )

        ctk.CTkLabel(
            self,
            text="Avaliação",
        ).grid(
            row=2,
            column=0,
            sticky="w",
            padx=24,
            pady=(12, 4),
        )

        self.rating_var = ctk.StringVar(
            value=str(work.rating or 1)
        )

        ctk.CTkOptionMenu(
            self,
            values=["1", "2", "3", "4", "5"],
            variable=self.rating_var,
        ).grid(
            row=3,
            column=0,
            sticky="w",
            padx=24,
        )

        ctk.CTkLabel(
            self,
            text="Data de início (AAAA-MM-DD)",
        ).grid(
            row=4,
            column=0,
            sticky="w",
            padx=24,
            pady=(16, 4),
        )

        self.start_entry = ctk.CTkEntry(self)
        self.start_entry.grid(
            row=5,
            column=0,
            sticky="ew",
            padx=24,
        )
        if work.start_date:
            self.start_entry.insert(0, work.start_date)

        ctk.CTkLabel(
            self,
            text="Data de conclusão (AAAA-MM-DD)",
        ).grid(
            row=6,
            column=0,
            sticky="w",
            padx=24,
            pady=(16, 4),
        )

        self.end_entry = ctk.CTkEntry(self)
        self.end_entry.grid(
            row=7,
            column=0,
            sticky="ew",
            padx=24,
        )
        if work.end_date:
            self.end_entry.insert(0, work.end_date)

        ctk.CTkLabel(
            self,
            text="Tags",
        ).grid(
            row=8,
            column=0,
            sticky="w",
            padx=24,
            pady=(16, 4),
        )

        self.tags_entry = ctk.CTkEntry(self)
        self.tags_entry.grid(
            row=9,
            column=0,
            sticky="ew",
            padx=24,
        )
        self.tags_entry.insert(
            0,
            ", ".join(repository.get_tags(work.id)),
        )

        ctk.CTkLabel(
            self,
            text="Notas pessoais",
        ).grid(
            row=10,
            column=0,
            sticky="w",
            padx=24,
            pady=(16, 4),
        )

        self.notes = ctk.CTkTextbox(
            self,
            height=180,
        )
        self.notes.grid(
            row=11,
            column=0,
            sticky="nsew",
            padx=24,
        )
        self.notes.insert(
            "1.0",
            work.personal_notes or "",
        )

        ctk.CTkButton(
            self,
            text="Salvar alterações",
            command=self.save,
        ).grid(
            row=12,
            column=0,
            sticky="e",
            padx=24,
            pady=24,
        )

    def save(self):
        self.repository.set_favorite(
            self.work.id,
            self.favorite_var.get(),
        )
        self.repository.set_rating(
            self.work.id,
            int(self.rating_var.get()),
        )
        self.repository.set_notes(
            self.work.id,
            self.notes.get("1.0", "end").strip(),
        )
        self.repository.set_tags(
            self.work.id,
            [
                item.strip()
                for item in self.tags_entry.get().split(",")
                if item.strip()
            ],
        )
        self.repository.set_reading_dates(
            self.work.id,
            self.start_entry.get().strip() or None,
            self.end_entry.get().strip() or None,
        )

        messagebox.showinfo(
            "Salvo",
            "Dados da obra atualizados.",
            parent=self,
        )
        self.on_saved()
        self.destroy()
