import customtkinter as ctk
from tkinter import messagebox


class WorkDetailsDialog(ctk.CTkToplevel):
    def __init__(self, master, repository, work, on_saved):
        super().__init__(master)

        self.repository = repository
        self.work = work
        self.on_saved = on_saved

        self.title(f"Detalhes — {work.name}")
        self.geometry("560x560")
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
            anchor="w",
        ).grid(
            row=2,
            column=0,
            sticky="w",
            padx=24,
            pady=(14, 4),
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
            text="Tags",
            anchor="w",
        ).grid(
            row=4,
            column=0,
            sticky="w",
            padx=24,
            pady=(18, 4),
        )

        self.tags_entry = ctk.CTkEntry(
            self,
            placeholder_text=(
                "fantasia, ficção científica, favorito..."
            ),
        )
        self.tags_entry.grid(
            row=5,
            column=0,
            sticky="ew",
            padx=24,
        )
        self.tags_entry.insert(
            0,
            ", ".join(
                repository.get_tags(work.id)
            ),
        )

        ctk.CTkLabel(
            self,
            text="Notas pessoais",
            anchor="w",
        ).grid(
            row=6,
            column=0,
            sticky="w",
            padx=24,
            pady=(18, 4),
        )

        self.notes = ctk.CTkTextbox(
            self,
            height=180,
        )
        self.notes.grid(
            row=7,
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
            row=8,
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

        tags = [
            item.strip()
            for item in self.tags_entry.get().split(",")
            if item.strip()
        ]
        self.repository.set_tags(
            self.work.id,
            tags,
        )

        messagebox.showinfo(
            "Salvo",
            "Metadados atualizados.",
            parent=self,
        )

        self.on_saved()
        self.destroy()
