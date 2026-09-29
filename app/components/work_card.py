
import customtkinter as ctk


class WorkCard(ctk.CTkFrame):
    def __init__(
        self,
        master,
        title,
        category,
        progress_text,
        status,
        percent=0,
        on_increment=None,
    ):
        super().__init__(master)

        self.grid_columnconfigure(1, weight=1)

        cover = ctk.CTkFrame(self, width=72, height=96)
        cover.grid(row=0, column=0, rowspan=3, padx=14, pady=14)
        cover.grid_propagate(False)
        ctk.CTkLabel(cover, text="CAPA").place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            self,
            text=title,
            font=("Arial", 17, "bold"),
            anchor="w",
        ).grid(row=0, column=1, sticky="ew", padx=(0, 14), pady=(16, 2))

        ctk.CTkLabel(
            self,
            text=f"{category} • {status}",
            anchor="w",
            text_color=("gray35", "gray70"),
        ).grid(row=1, column=1, sticky="ew", padx=(0, 14))

        progress = ctk.CTkProgressBar(self)
        progress.set(max(0, min(percent, 1)))
        progress.grid(row=2, column=1, sticky="ew", padx=(0, 14), pady=(6, 4))

        ctk.CTkLabel(
            self,
            text=progress_text,
            anchor="w",
        ).grid(row=3, column=1, sticky="w", padx=(0, 14), pady=(0, 14))

        ctk.CTkButton(
            self,
            text="+1",
            width=54,
            command=on_increment,
        ).grid(row=1, column=2, padx=14)
