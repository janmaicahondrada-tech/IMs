"""Run `python app.py` to open the StudentHub desktop application."""

import csv
import queue
import threading
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

import storage


BG = "#f3f6fa"
INK = "#142d40"
MUTED = "#032344"
TEAL = "#007f75"
NAVY = "#112b3c"
WHITE = "#ffffff"
LINE = "#e0e7ee"
LABELS = {"students": "Students", "courses": "Courses", "departments": "Departments"}
SINGULAR = {"students": "student", "courses": "course", "departments": "department"}
COLUMNS = {
    "students": (("id", "ID", 65), ("name", "STUDENT NAME", 190), ("email", "EMAIL ADDRESS", 240),
                 ("course_title", "COURSE", 180), ("department_name", "DEPARTMENT", 175)),
    "courses": (("id", "ID", 65), ("title", "COURSE TITLE", 250),
                ("department_name", "DEPARTMENT", 240), ("student_count", "STUDENTS", 100)),
    "departments": (("id", "ID", 65), ("name", "DEPARTMENT NAME", 300),
                    ("course_count", "COURSES", 130), ("student_count", "STUDENTS", 130)),
}


class StudentHub(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("StudentHub | Academic records")
        self.geometry("1260x790")
        self.minsize(1000, 680)
        self.configure(bg=BG)
        self.option_add("*Font", ("Segoe UI", 10))
        self.data = {key: [] for key in LABELS}
        self.entity = "students"
        self.ready = False
        self.busy = False
        self.events = queue.Queue()
        self.search = tk.StringVar()
        self.filter = tk.StringVar(value="All courses")
        self.status = tk.StringVar(value="Connecting to MySQL…")
        self._styles()
        self._layout()
        self.search.trace_add("write", lambda *_: self.render())
        self.bind("<Control-f>", self.focus_search)
        self.bind("<Control-n>", lambda _: self.open_form())
        self._poll_job = self.after(80, self.poll)
        self._initial_job = self.after(150, self.refresh)

    def destroy(self):
        for job in (getattr(self, "_poll_job", None), getattr(self, "_initial_job", None)):
            if job is not None:
                self.after_cancel(job)
        super().destroy()

    def _styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TButton", font=("Segoe UI", 10), padding=(14, 9), background=WHITE,
                        foreground=INK, bordercolor=LINE, focusthickness=2, focuscolor=TEAL)
        style.map("TButton", background=[("active", "#eaf0f5")], foreground=[("disabled", "#9caab6")])
        style.configure("Primary.TButton", background=TEAL, foreground=WHITE, bordercolor=TEAL)
        style.map("Primary.TButton", background=[("active", "#00685f"), ("disabled", "#a6c9c5")],
                  foreground=[("disabled", WHITE)])
        style.configure("Danger.TButton", foreground="#b23a42")
        style.configure("TEntry", padding=10, fieldbackground=WHITE, bordercolor=LINE)
        style.configure("TCombobox", padding=9, fieldbackground=WHITE, bordercolor=LINE)
        style.map("TCombobox", fieldbackground=[("readonly", WHITE)], selectbackground=[("readonly", WHITE)],
                  selectforeground=[("readonly", INK)])
        style.configure("Treeview", background=WHITE, fieldbackground=WHITE, foreground=INK,
                        rowheight=51, borderwidth=0, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", background="#f7f9fc", foreground=MUTED,
                        padding=(12, 13), font=("Segoe UI Semibold", 9), relief="flat")
        style.map("Treeview", background=[("selected", "#d9efeb")], foreground=[("selected", INK)])
        style.map("Treeview.Heading", background=[("active", "#edf2f7")])

    def label(self, parent, text, size=10, color=INK, bg=BG, bold=False, **kwargs):
        return tk.Label(parent, text=text, font=("Segoe UI Semibold" if bold else "Segoe UI", size),
                        fg=color, bg=bg, **kwargs)

    def _layout(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        sidebar = tk.Frame(self, bg=NAVY, width=210)
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.pack_propagate(False)
        brand = tk.Frame(sidebar, bg=NAVY)
        brand.pack(fill="x", padx=23, pady=(32, 0))
        self.label(brand, "S", 21, WHITE, TEAL, True, width=2).pack(side="left")
        self.label(brand, " StudentHub", 16, WHITE, NAVY, True).pack(side="left")
        self.label(sidebar, "ACADEMIC WORKSPACE", 8, "#8ea8bb", NAVY, True).pack(anchor="w", padx=25, pady=(13, 42))
        self.label(sidebar, "MANAGE", 8, "#8ea8bb", NAVY, True).pack(anchor="w", padx=25, pady=(0, 12))
        self.nav = {}
        for key, title in LABELS.items():
            button = tk.Button(sidebar, text=f"  {title}", anchor="w", padx=18, pady=14,
                               font=("Segoe UI Semibold", 11), relief="flat", bd=0, cursor="hand2",
                               command=lambda entity=key: self.navigate(entity),
                               activebackground="#1c4658", activeforeground=WHITE)
            button.pack(fill="x", padx=13, pady=3)
            self.nav[key] = button
        footer = tk.Frame(sidebar, bg=NAVY)
        footer.pack(side="bottom", fill="x", padx=24, pady=27)
        self.label(footer, "ONE CONNECTED CAMPUS", 8, "#8ea8bb", NAVY, True).pack(anchor="w")
        self.label(footer, "People. Courses. Possibilities.", 9, "#b4c7d4", NAVY).pack(anchor="w", pady=(7, 0))

        main = tk.Frame(self, bg=BG)
        main.grid(row=0, column=1, sticky="nsew", padx=32, pady=(25, 18))
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(5, weight=1)
        topline = tk.Frame(main, bg=BG)
        topline.grid(row=0, column=0, sticky="ew", pady=(0, 25))
        self.label(topline, "WORKSPACE  /  ACADEMIC RECORDS", 9, MUTED, bold=True).pack(side="left")
        self.connection_label = self.label(topline, "●  Connecting", 9, MUTED)
        self.connection_label.pack(side="right")

        heading = tk.Frame(main, bg=BG)
        heading.grid(row=1, column=0, sticky="ew")
        copy = tk.Frame(heading, bg=BG)
        copy.pack(side="left")
        self.title_label = self.label(copy, "Students", 28, bold=True)
        self.title_label.pack(anchor="w")
        self.subtitle = self.label(copy, "A clear view of every student and their academic home.", 10, MUTED)
        self.subtitle.pack(anchor="w", pady=(5, 0))
        self.add_button = ttk.Button(heading, text="+  Add student", style="Primary.TButton", command=self.open_form)
        self.add_button.pack(side="right", anchor="center")

        cards = tk.Frame(main, bg=BG)
        cards.grid(row=2, column=0, sticky="ew", pady=25)
        self.count_labels = {}
        for index, (key, title) in enumerate(LABELS.items()):
            cards.grid_columnconfigure(index, weight=1, uniform="cards")
            card = tk.Frame(cards, bg=WHITE, highlightbackground=LINE, highlightthickness=1)
            card.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else 8, 0 if index == 2 else 8))
            self.label(card, f"TOTAL {title.upper()}", 9, MUTED, WHITE, True).pack(anchor="w", padx=19, pady=(17, 6))
            count = self.label(card, "—", 27, TEAL if index == 0 else INK, WHITE, True)
            count.pack(anchor="w", padx=19, pady=(0, 15))
            self.count_labels[key] = count

        tools = tk.Frame(main, bg=BG)
        tools.grid(row=3, column=0, sticky="ew", pady=(0, 17))
        tools.grid_columnconfigure(0, weight=1)
        self.search_entry = ttk.Entry(tools, textvariable=self.search)
        self.search_entry.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        self.filter_combo = ttk.Combobox(tools, textvariable=self.filter, state="readonly", width=23)
        self.filter_combo.grid(row=0, column=1, padx=(0, 12))
        self.filter_combo.bind("<<ComboboxSelected>>", lambda _: self.render())
        self.refresh_button = ttk.Button(tools, text="↻  Refresh", command=self.refresh)
        self.refresh_button.grid(row=0, column=2)
        self.search_hint = self.label(main, "Search by name, email, course, department, or ID", 9, MUTED)
        self.search_hint.grid(row=4, column=0, sticky="w", pady=(0, 10))

        table_frame = tk.Frame(main, bg=WHITE, highlightbackground=LINE, highlightthickness=1)
        table_frame.grid(row=5, column=0, sticky="nsew")
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)
        self.table = ttk.Treeview(table_frame, show="headings", selectmode="browse")
        self.table.grid(row=0, column=0, sticky="nsew")
        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll = ttk.Scrollbar(table_frame, orient="horizontal", command=self.table.xview)
        xscroll.grid(row=1, column=0, sticky="ew")
        self.table.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.table.tag_configure("alternate", background="#f8fafc")
        self.table.bind("<<TreeviewSelect>>", lambda _: self.update_actions())
        self.table.bind("<Double-1>", self.edit_from_table)
        self.table.bind("<Return>", lambda _: self.open_form(self.selected()))
        self.empty = tk.Frame(table_frame, bg=WHITE)
        self.empty_title = self.label(self.empty, "Your records start here", 17, INK, WHITE, True)
        self.empty_title.pack(pady=(0, 8))
        self.empty_copy = self.label(self.empty, "Add a student to build your campus directory.", 10, MUTED, WHITE,
                                     wraplength=430, justify="center")
        self.empty_copy.pack()

        bottom = tk.Frame(main, bg=BG)
        bottom.grid(row=6, column=0, sticky="ew", pady=(16, 0))
        self.result_label = self.label(bottom, "Loading records…", 9, MUTED)
        self.result_label.pack(side="left")
        self.delete_button = ttk.Button(bottom, text="Delete", style="Danger.TButton", command=self.delete_selected)
        self.delete_button.pack(side="right")
        self.edit_button = ttk.Button(bottom, text="Edit selected", command=lambda: self.open_form(self.selected()))
        self.edit_button.pack(side="right", padx=8)
        self.export_button = ttk.Button(bottom, text="Export CSV", command=self.export)
        self.export_button.pack(side="right", padx=(0, 4))
        self.status_label = tk.Label(main, textvariable=self.status, anchor="w", bg=BG, fg=MUTED,
                                     font=("Segoe UI", 9), wraplength=850, justify="left")
        self.status_label.grid(row=7, column=0, sticky="ew", pady=(15, 0))
        self.navigate("students")

    def focus_search(self, _=None):
        self.search_entry.focus_set()
        self.search_entry.selection_range(0, "end")
        return "break"

    def edit_from_table(self, event):
        if self.table.identify_region(event.x, event.y) == "cell":
            record = self.selected()
            if record:
                self.open_form(record)

    def navigate(self, entity):
        self.table.selection_remove(*self.table.selection())
        self.entity = entity
        self.search.set("")
        self.filter.set("")
        self.title_label.config(text=LABELS[entity])
        self.subtitle.config(text={
            "students": "A clear view of every student and their academic home.",
            "courses": "Keep your course offerings organized and connected.",
            "departments": "The academic homes that bring your campus together.",
        }[entity])
        self.add_button.config(text=f"+  Add {SINGULAR[entity]}")
        self.search_hint.config(text={
            "students": "Search by name, email, course, department, or ID",
            "courses": "Search by course title, department, or ID",
            "departments": "Search by department name or ID",
        }[entity])
        for key, button in self.nav.items():
            button.config(bg=TEAL if key == entity else NAVY, fg=WHITE if key == entity else "#b4c7d4")
        self.configure_filters()
        self.render()

    def configure_filters(self):
        self.filter_options = {}
        if self.entity == "departments":
            self.filter_combo.grid_remove()
            self.filter.set("")
            return
        self.filter_combo.grid()
        source = "courses" if self.entity == "students" else "departments"
        name_field = "title" if source == "courses" else "name"
        all_label = f"All {source}"
        self.filter_options = {all_label: "all", "Unassigned": None}
        self.filter_options.update({f"{row[name_field]} · #{row['id']}": row["id"] for row in self.data[source]})
        current = self.filter.get()
        self.filter_combo.config(values=list(self.filter_options))
        self.filter.set(current if current in self.filter_options else all_label)

    def visible_rows(self):
        query = self.search.get().strip().casefold()
        filtered_id = self.filter_options.get(self.filter.get(), "all")
        relation = "course_id" if self.entity == "students" else "department_id"
        fields = [column[0] for column in COLUMNS[self.entity]]
        return [row for row in self.data[self.entity]
                if (self.entity == "departments" or filtered_id == "all" or row.get(relation) == filtered_id)
                and (not query or query in " ".join(str(row.get(field) or "") for field in fields).casefold())]

    def render(self):
        if not hasattr(self, "table"):
            return
        selected = self.table.selection()
        self.table.delete(*self.table.get_children())
        columns = COLUMNS[self.entity]
        self.table.config(columns=[column[0] for column in columns])
        for key, title, width in columns:
            self.table.heading(key, text=title, anchor="w")
            self.table.column(key, width=width, minwidth=60 if key == "id" else 110,
                              stretch=key != "id", anchor="w")
        rows = self.visible_rows()
        for index, row in enumerate(rows):
            values = [row.get(key) if row.get(key) is not None else "Unassigned" for key, _, _ in columns]
            self.table.insert("", "end", iid=str(row["id"]), values=values,
                              tags=("alternate",) if index % 2 else ())
        if selected and self.table.exists(selected[0]):
            self.table.selection_set(selected[0])
        self.result_label.config(text=f"{len(rows)} of {len(self.data[self.entity])} {self.entity}")
        if rows:
            self.empty.place_forget()
        else:
            if not self.ready:
                title, copy = "Waiting for your database", "Connect to MySQL to load your academic records."
            elif self.data[self.entity]:
                title, copy = "No matching records", "Try another search or choose a different filter."
            else:
                title, copy = f"No {self.entity} yet", f"Click Add {SINGULAR[self.entity]} to create your first record."
            self.empty_title.config(text=title)
            self.empty_copy.config(text=copy)
            self.empty.place(relx=0.5, rely=0.5, anchor="center")
        self.update_actions()

    def selected(self):
        selected = self.table.selection()
        return next((row for row in self.data[self.entity] if selected and str(row["id"]) == selected[0]), None)

    def update_actions(self):
        state = "normal" if self.ready and not self.busy else "disabled"
        self.add_button.config(state=state)
        for button in (self.edit_button, self.delete_button):
            button.config(state=state if self.selected() else "disabled")
        self.refresh_button.config(state="disabled" if self.busy else "normal")
        self.export_button.config(state=state if self.visible_rows() else "disabled")

    def background(self, operation, success, failure):
        self.busy = True
        self.update_actions()

        def run():
            try:
                result = operation()
                self.events.put((success, result))
            except Exception as error:
                self.events.put((failure, str(error)))
        threading.Thread(target=run, daemon=True).start()

    def poll(self):
        try:
            callback, result = self.events.get_nowait()
        except queue.Empty:
            pass
        else:
            self.busy = False
            callback(result)
            self.update_actions()
        self._poll_job = self.after(80, self.poll)

    def refresh(self):
        if self.busy:
            return
        self.status.set("Loading academic records…")

        def load():
            if not self.ready:
                storage.initialize()
            return storage.snapshot()

        def loaded(data):
            self.data = data
            self.ready = True
            self.connection_label.config(text="●  MySQL connected", fg=TEAL)
            self.status_label.config(fg=MUTED)
            self.status.set(f"Up to date · {datetime.now():%I:%M %p}    |    Ctrl+F to search · Ctrl+N to add")
            for key, label in self.count_labels.items():
                label.config(text=f"{len(data[key]):,}")
            self.configure_filters()
            self.render()

        def failed(error):
            self.ready = False
            self.connection_label.config(text="●  Connection unavailable", fg="#b23a42")
            self.status_label.config(fg="#b23a42")
            self.status.set(error + (" Previously loaded records are still shown." if any(self.data.values()) else ""))
            self.render()
        self.background(load, loaded, failed)

    def open_form(self, record=None):
        if self.ready and not self.busy:
            RecordDialog(self, self.entity, record)

    def delete_selected(self):
        row = self.selected()
        if not row or self.busy:
            return
        entity = self.entity
        name = row.get("name") or row.get("title")
        warning = f'Delete {SINGULAR[entity]} “{name}”?'
        if entity == "courses":
            warning += f"\n\nThis also deletes every student linked to this course ({row['student_count']} currently loaded)."
        elif entity == "departments":
            warning += (f"\n\nThis also deletes all linked courses and their students "
                        f"({row['course_count']} courses and {row['student_count']} students currently loaded).")
        warning += "\n\nThis cannot be undone."
        if messagebox.askyesno("Delete record", warning, parent=self, icon="warning", default="no"):
            self.status.set("Deleting record…")
            self.background(lambda: storage.delete(entity, row["id"]), lambda _: self.refresh(),
                            lambda error: messagebox.showerror("Could not delete record", error, parent=self))

    def export(self):
        rows = self.visible_rows()
        if not rows:
            return
        path = filedialog.asksaveasfilename(parent=self, title="Export visible records", defaultextension=".csv",
                                          initialfile=f"{self.entity}.csv", filetypes=[("CSV files", "*.csv")])
        if not path:
            return
        def safe(value):
            text = "" if value is None else str(value)
            return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text
        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as output:
                writer = csv.writer(output)
                writer.writerow([label for _, label, _ in COLUMNS[self.entity]])
                writer.writerows([[safe(row.get(key)) for key, _, _ in COLUMNS[self.entity]] for row in rows])
            self.status.set(f"Exported {len(rows)} {self.entity} to {path}")
        except OSError as error:
            messagebox.showerror("Could not export", str(error), parent=self)


class RecordDialog(tk.Toplevel):
    def __init__(self, app, entity, record):
        super().__init__(app)
        self.app, self.entity, self.record = app, entity, record
        self.saving = False
        self.title(f"{'Edit' if record else 'Add'} {SINGULAR[entity]}")
        self.configure(bg=WHITE)
        self.resizable(False, False)
        self.transient(app)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Escape>", lambda _: self.close())
        self.bind("<Return>", lambda _: self.save())
        frame = tk.Frame(self, bg=WHITE, padx=30, pady=27)
        frame.pack(fill="both", expand=True)
        app.label(frame, self.title(), 21, bg=WHITE, bold=True).pack(anchor="w")
        app.label(frame, "Keep your academic records accurate and connected.", 10, MUTED, WHITE).pack(anchor="w", pady=(6, 22))
        self.fields = {}
        self.links = {}
        fields = {
            "students": (("name", "Full name *"), ("email", "Email address *"), ("course_id", "Course")),
            "courses": (("title", "Course title *"), ("department_id", "Department")),
            "departments": (("name", "Department name *"),),
        }[entity]
        first = None
        for field, label in fields:
            app.label(frame, label, 10, bg=WHITE, bold=True).pack(anchor="w", pady=(0, 7))
            variable = tk.StringVar()
            self.fields[field] = variable
            if field.endswith("_id"):
                source = "courses" if field == "course_id" else "departments"
                display = "title" if source == "courses" else "name"
                options = {"Unassigned": None}
                options.update({f"{row[display]} · #{row['id']}": row["id"] for row in app.data[source]})
                self.links[field] = options
                widget = ttk.Combobox(frame, textvariable=variable, values=list(options), state="readonly", width=47)
                current = record.get(field) if record else None
                variable.set(next((label for label, value in options.items() if value == current), "Unassigned"))
            else:
                widget = ttk.Entry(frame, textvariable=variable, width=49)
                variable.set(record.get(field, "") if record else "")
            widget.pack(fill="x", pady=(0, 18))
            first = first or widget
        app.label(frame, "* Required fields", 9, MUTED, WHITE).pack(anchor="w")
        self.error = app.label(frame, "", 10, "#b23a42", WHITE, wraplength=410, justify="left")
        self.error.pack(anchor="w", pady=(12, 15))
        actions = tk.Frame(frame, bg=WHITE)
        actions.pack(fill="x")
        self.save_button = ttk.Button(actions, text="Save changes" if record else f"Add {SINGULAR[entity]}",
                                      style="Primary.TButton", command=self.save)
        self.save_button.pack(side="right")
        self.cancel_button = ttk.Button(actions, text="Cancel", command=self.close)
        self.cancel_button.pack(side="right", padx=9)
        self.update_idletasks()
        x = app.winfo_x() + (app.winfo_width() - self.winfo_width()) // 2
        y = app.winfo_y() + (app.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        first.focus_set()

    def close(self):
        if not self.saving:
            self.destroy()

    def save(self):
        if self.saving:
            return
        values = {key: self.links[key][variable.get()] if key in self.links else variable.get()
                  for key, variable in self.fields.items()}
        try:
            values = storage.validate(self.entity, values)
        except storage.StorageError as error:
            self.error.config(text=str(error))
            return
        self.saving = True
        self.save_button.config(state="disabled", text="Saving…")
        self.cancel_button.config(state="disabled")
        self.error.config(text="")

        def saved(_):
            self.destroy()
            self.app.refresh()

        def failed(error):
            self.saving = False
            self.save_button.config(state="normal", text="Save changes" if self.record else f"Add {SINGULAR[self.entity]}")
            self.cancel_button.config(state="normal")
            self.error.config(text=error)
        self.app.background(lambda: storage.save(self.entity, values, self.record["id"] if self.record else None), saved, failed)


if __name__ == "__main__":
    StudentHub().mainloop()
