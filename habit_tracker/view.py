"""PyQt6 view for task planning, routines, timers, and calendar events.

The view is self-contained on purpose: it owns no AMADEUS chat controls and
uses only the Habit Tracker service for local task data.
"""

from __future__ import annotations

from datetime import date

from PyQt6.QtCore import QDate, Qt, QTimer
from PyQt6.QtGui import QBrush, QColor, QTextCharFormat
from PyQt6.QtWidgets import (
    QCalendarWidget,
    QApplication,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from habit_tracker.service import HabitTrackerService, WEEKDAYS


class TaskDialog(QDialog):
    """Collect a title and optional description for a task or event."""

    def __init__(self, title: str, parent: QWidget | None = None, include_time: bool = False) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(380)
        form = QFormLayout(self)
        self.title_input = QLineEdit()
        self.description_input = QTextEdit()
        self.description_input.setFixedHeight(80)
        form.addRow("Title", self.title_input)
        form.addRow("Description", self.description_input)
        self.time_input = QLineEdit()
        if include_time:
            self.time_input.setPlaceholderText("Optional time, e.g. 15:00")
            form.addRow("Time", self.time_input)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def data(self) -> dict[str, str | None]:
        return {"title": self.title_input.text().strip(), "description": self.description_input.toPlainText().strip() or None, "time": self.time_input.text().strip() or None}


class MatrixTaskDialog(TaskDialog):
    """Collect the Eisenhower quadrant alongside the normal task fields."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Add Matrix Task", parent)
        self.urgent = QCheckBox("Urgent")
        self.important = QCheckBox("Important")
        self.layout().insertRow(2, "Priority", self.urgent)
        self.layout().insertRow(3, "", self.important)

    def quadrant(self) -> str:
        if self.urgent.isChecked() and self.important.isChecked():
            return "urgent_important"
        if self.important.isChecked():
            return "important_not_urgent"
        if self.urgent.isChecked():
            return "urgent_not_important"
        return "not_urgent_not_important"


class RoutineTaskDialog(QDialog):
    """Collect a recurring task and the weekdays on which it should appear."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Routine Task")
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.title_input = QLineEdit()
        self.description_input = QTextEdit()
        self.description_input.setFixedHeight(80)
        form.addRow("Title", self.title_input)
        form.addRow("Description", self.description_input)
        layout.addLayout(form)
        layout.addWidget(QLabel("Repeat every week on:"))
        days = QGridLayout()
        self.day_checkboxes: dict[str, QCheckBox] = {}
        for index, day in enumerate(WEEKDAYS):
            checkbox = QCheckBox(day.capitalize())
            self.day_checkboxes[day] = checkbox
            days.addWidget(checkbox, index // 2, index % 2)
        layout.addLayout(days)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def data(self) -> dict[str, str | None]:
        return {
            "title": self.title_input.text().strip(),
            "description": self.description_input.toPlainText().strip() or None,
            "days_of_week": ",".join(day for day in WEEKDAYS if self.day_checkboxes[day].isChecked()),
        }


class AssignCalendarDialog(TaskDialog):
    """Collect an explicit calendar date and optional time for a matrix task."""

    def __init__(self, task_title: str, selected_date: str, parent: QWidget | None = None) -> None:
        super().__init__("Assign Matrix Task to Calendar", parent, include_time=True)
        self.title_input.setText(task_title)
        self.title_input.setReadOnly(True)
        self.date_input = QDateEdit(QDate.fromString(selected_date, "yyyy-MM-dd"))
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("yyyy-MM-dd")
        self.layout().insertRow(2, "Calendar date", self.date_input)

    def data(self) -> dict[str, str | None]:
        result = super().data()
        result["date"] = self.date_input.date().toString("yyyy-MM-dd")
        return result


class AlarmDialog(QDialog):
    """Notify the user about one due timer or alarm."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Timer / Alarm")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Timer / Alarm"))
        layout.addWidget(QLabel(f"{title} is due now."))
        stop = QPushButton("Stop alarm")
        stop.clicked.connect(self.accept)
        layout.addWidget(stop)
        self.auto_stop = QTimer(self)
        self.auto_stop.setSingleShot(True)
        self.auto_stop.timeout.connect(self.accept)
        self.auto_stop.start(60000)
        QApplication.beep()


class HabitTrackerView(QWidget):
    """Present the standalone Task Manager Personal capabilities inside AMADEUS."""

    def __init__(self, parent: QWidget | None = None, service: HabitTrackerService | None = None) -> None:
        super().__init__(parent)
        self.service = service if service is not None else HabitTrackerService()
        self.selected_date = date.today().isoformat()
        self._build_ui()
        self._apply_styles()
        self.refresh_all()
        self.alarm_checker = QTimer(self)
        self.alarm_checker.timeout.connect(self.check_due_alarms)
        self.alarm_checker.start(5000)

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)
        left = QVBoxLayout()
        right = QVBoxLayout()
        root.addLayout(left, 3)
        root.addLayout(right, 2)

        self.weekday_box = QComboBox()
        self.weekday_box.addItems([day.capitalize() for day in WEEKDAYS])
        self.weekday_box.setCurrentIndex(date.today().weekday())
        self.weekday_box.currentIndexChanged.connect(self._weekday_changed)
        left.addWidget(self.weekday_box)
        left.addWidget(self._build_day_panel(), 4)
        left.addWidget(self._build_timer_panel(), 2)
        right.addWidget(self._build_matrix_panel(), 3)
        right.addWidget(self._build_calendar_panel(), 2)

    def _panel(self) -> tuple[QFrame, QVBoxLayout]:
        panel = QFrame()
        panel.setObjectName("habitPanel")
        layout = QVBoxLayout(panel)
        layout.setSpacing(10)
        return panel, layout

    def _header(self, title: str, *buttons: QPushButton) -> QHBoxLayout:
        header = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setObjectName("habitPanelTitle")
        header.addWidget(title_label)
        header.addStretch()
        for button in buttons:
            header.addWidget(button)
        return header

    def _build_day_panel(self) -> QFrame:
        panel, layout = self._panel()
        add_task = QPushButton("+ Add task")
        add_task.clicked.connect(self.add_one_time_task)
        add_routine = QPushButton("+ Add routine")
        add_routine.clicked.connect(self.add_routine_task)
        self.day_title = QLabel()
        self.day_title.setObjectName("habitPanelTitle")
        header = QHBoxLayout()
        header.addWidget(self.day_title)
        header.addStretch()
        header.addWidget(add_routine)
        header.addWidget(add_task)
        layout.addLayout(header)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.task_container = QWidget()
        self.task_list = QVBoxLayout(self.task_container)
        self.task_list.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self.task_container)
        layout.addWidget(scroll)
        return panel

    def _build_timer_panel(self) -> QFrame:
        panel, layout = self._panel()
        layout.addLayout(self._header("Timers / Alarms"))
        controls = QHBoxLayout()
        self.timer_title = QComboBox()
        self.timer_title.setEditable(True)
        self.timer_title.setPlaceholderText("Choose task or enter a custom timer")
        self.timer_minutes = QSpinBox()
        self.timer_minutes.setRange(1, 999)
        self.timer_minutes.setValue(25)
        self.timer_minutes.setSuffix(" min")
        start = QPushButton("Start")
        start.clicked.connect(self.start_timer)
        controls.addWidget(self.timer_title, 3)
        controls.addWidget(self.timer_minutes)
        controls.addWidget(start)
        layout.addLayout(controls)
        self.alarms = QListWidget()
        layout.addWidget(self.alarms)
        delete = QPushButton("Delete selected timer")
        delete.clicked.connect(self.delete_selected_alarm)
        layout.addWidget(delete)
        return panel

    def _build_matrix_panel(self) -> QFrame:
        panel, layout = self._panel()
        add = QPushButton("+ Add")
        add.clicked.connect(self.add_matrix_task)
        assign = QPushButton("Assign to calendar")
        assign.clicked.connect(self.assign_matrix_task)
        delete = QPushButton("Delete")
        delete.clicked.connect(self.delete_selected_matrix_task)
        layout.addLayout(self._header("Eisenhower Task List", add, assign, delete))
        legend = QLabel("Sorted: urgent + important, urgent, important, then unmarked.")
        legend.setObjectName("habitMuted")
        layout.addWidget(legend)
        self.matrix = QTableWidget(0, 3)
        self.matrix.setHorizontalHeaderLabels(["Urgent", "Important", "Task"])
        self.matrix.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.matrix.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.matrix.verticalHeader().setVisible(False)
        self.matrix.horizontalHeader().setStretchLastSection(True)
        self.matrix.setColumnWidth(0, 70)
        self.matrix.setColumnWidth(1, 85)
        layout.addWidget(self.matrix)
        return panel

    def _build_calendar_panel(self) -> QFrame:
        panel, layout = self._panel()
        add = QPushButton("+ Add event")
        add.clicked.connect(self.add_calendar_event)
        layout.addLayout(self._header("Calendar", add))
        self.calendar = QCalendarWidget()
        self.calendar.selectionChanged.connect(self._calendar_changed)
        layout.addWidget(self.calendar)
        return panel

    def _apply_styles(self) -> None:
        self.setStyleSheet("""
            QWidget { background: #10151d; color: #e6edf5; font-size: 13px; }
            QFrame#habitPanel { background: #171f2a; border: 1px solid #2d3a4d; border-radius: 12px; }
            QLabel#habitPanelTitle { font-size: 18px; font-weight: 700; }
            QLabel#habitMuted { color: #9cadc1; }
            QPushButton { background: #253348; border: 1px solid #3a4e68; border-radius: 7px; padding: 7px 10px; }
            QPushButton:hover { background: #30435c; }
            QLineEdit, QTextEdit, QComboBox, QSpinBox, QListWidget, QTableWidget { background: #0f151e; border: 1px solid #34455c; border-radius: 7px; padding: 6px; }
            QHeaderView::section { background: #253348; border: 0; border-right: 1px solid #34455c; padding: 6px; font-weight: 700; }
            QScrollArea { border: 0; } QCalendarWidget QWidget { background: #171f2a; }
            QCalendarWidget QToolButton { background: #253348; border-radius: 5px; padding: 5px; }
        """)

    def refresh_all(self) -> None:
        self.refresh_day_tasks()
        self.refresh_matrix()
        self.refresh_alarms()
        self.refresh_timer_options()
        self.refresh_calendar_highlights()

    def refresh_day_tasks(self) -> None:
        self._clear_layout(self.task_list)
        overview = self.service.day_overview(self.selected_date)
        self.day_title.setText(f"{overview['weekday'].capitalize()} - {overview['date']}")
        self._add_task_section("Routine Tasks", overview["routine_tasks"], "is_completed_today", self.service.set_routine_completion, self.delete_routine_task, is_routine=True)
        self._add_task_section("One-Time Tasks", overview["one_time_tasks"], "is_completed", self.service.set_one_time_completion, self.delete_one_time_task)
        label = QLabel("Calendar Events")
        label.setStyleSheet("font-weight: 700; margin-top: 10px;")
        self.task_list.addWidget(label)
        for event in overview["calendar_events"]:
            self._add_event_row(event)
        if not overview["calendar_events"]:
            self.task_list.addWidget(QLabel("No calendar events."))
        self.task_list.addStretch()

    def _add_task_section(self, title: str, tasks: list[dict], completion_key: str, completer, deleter, *, is_routine: bool = False) -> None:
        label = QLabel(title)
        label.setStyleSheet("font-weight: 700; margin-top: 8px;")
        self.task_list.addWidget(label)
        if not tasks:
            self.task_list.addWidget(QLabel(f"No {title.lower()}."))
            return
        for task in tasks:
            row = QHBoxLayout()
            checkbox = QCheckBox(task["title"])
            checkbox.setChecked(bool(task[completion_key]))
            if is_routine:
                checkbox.stateChanged.connect(lambda state, item_id=task["id"], method=completer: method(item_id, self.selected_date, state == Qt.CheckState.Checked.value))
            else:
                checkbox.stateChanged.connect(lambda state, item_id=task["id"], method=completer: method(item_id, state == Qt.CheckState.Checked.value))
            remove = QPushButton("x")
            remove.setFixedWidth(30)
            remove.clicked.connect(lambda _checked=False, item_id=task["id"], method=deleter: method(item_id))
            row.addWidget(checkbox)
            row.addStretch()
            row.addWidget(remove)
            self.task_list.addLayout(row)

    def _add_event_row(self, event: dict) -> None:
        row = QHBoxLayout()
        row.addWidget(QLabel(f"{event['title']} at {event['event_time'] or 'No time'}"))
        row.addStretch()
        remove = QPushButton("x")
        remove.setFixedWidth(30)
        remove.clicked.connect(lambda _checked=False, event_id=event["id"]: self.delete_calendar_event(event_id))
        row.addWidget(remove)
        self.task_list.addLayout(row)

    def refresh_matrix(self) -> None:
        self.matrix.setRowCount(0)
        tasks = self.service.matrix_tasks()
        if not tasks:
            self.matrix.setRowCount(1)
            self.matrix.setItem(0, 2, QTableWidgetItem("No matrix tasks."))
            return
        for task in sorted(tasks, key=lambda item: ({"urgent_important": 0, "urgent_not_important": 1, "important_not_urgent": 2, "not_urgent_not_important": 3}.get(item["quadrant"], 4), item["is_completed"], item["id"])):
            row = self.matrix.rowCount()
            self.matrix.insertRow(row)
            urgent = QTableWidgetItem()
            urgent.setCheckState(Qt.CheckState.Checked if task["quadrant"] in {"urgent_important", "urgent_not_important"} else Qt.CheckState.Unchecked)
            important = QTableWidgetItem()
            important.setCheckState(Qt.CheckState.Checked if task["quadrant"] in {"urgent_important", "important_not_urgent"} else Qt.CheckState.Unchecked)
            task_item = QTableWidgetItem(task["title"])
            task_item.setData(Qt.ItemDataRole.UserRole, task)
            for column, item in enumerate((urgent, important, task_item)):
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                self.matrix.setItem(row, column, item)

    def refresh_alarms(self) -> None:
        self.alarms.clear()
        alarms = self.service.active_alarms()
        if not alarms:
            self.alarms.addItem("No active timers or alarms.")
        for alarm in alarms:
            item = QListWidgetItem(f"{alarm['title']} - {alarm['target_datetime']}")
            item.setData(Qt.ItemDataRole.UserRole, alarm["id"])
            self.alarms.addItem(item)

    def refresh_timer_options(self) -> None:
        current = self.timer_title.currentText()
        self.timer_title.clear()
        self.timer_title.addItem("Custom timer")
        overview = self.service.day_overview(self.selected_date)
        self.timer_title.addItems([task["title"] for group in (overview["routine_tasks"], overview["one_time_tasks"], overview["calendar_events"]) for task in group])
        self.timer_title.setEditText(current)

    def refresh_calendar_highlights(self) -> None:
        self._clear_calendar_formats()
        format_for_tasks = QTextCharFormat()
        format_for_tasks.setBackground(QBrush(QColor("#4e789e")))
        format_for_tasks.setForeground(QBrush(QColor("#ffffff")))
        for value in self.service.calendar_dates():
            self.calendar.setDateTextFormat(QDate.fromString(value, "yyyy-MM-dd"), format_for_tasks)
        today_format = QTextCharFormat()
        today_format.setBackground(QBrush(QColor("#8ed9a4")))
        today_format.setForeground(QBrush(QColor("#102419")))
        today_format.setFontWeight(700)
        self.calendar.setDateTextFormat(QDate.currentDate(), today_format)

    def _clear_calendar_formats(self) -> None:
        neutral = QTextCharFormat()
        for day in range(1, QDate(self.calendar.yearShown(), self.calendar.monthShown(), 1).daysInMonth() + 1):
            self.calendar.setDateTextFormat(QDate(self.calendar.yearShown(), self.calendar.monthShown(), day), neutral)

    def _weekday_changed(self) -> None:
        today = date.today()
        offset = self.weekday_box.currentIndex() - today.weekday()
        if offset < 0:
            offset += 7
        self._set_selected_date(date.fromordinal(today.toordinal() + offset).isoformat())

    def _calendar_changed(self) -> None:
        self._set_selected_date(self.calendar.selectedDate().toString("yyyy-MM-dd"), update_calendar=False)

    def _set_selected_date(self, selected: str, update_calendar: bool = True) -> None:
        self.selected_date = selected
        weekday = date.fromisoformat(selected).weekday()
        self.weekday_box.blockSignals(True)
        self.weekday_box.setCurrentIndex(weekday)
        self.weekday_box.blockSignals(False)
        if update_calendar:
            self.calendar.setSelectedDate(QDate.fromString(selected, "yyyy-MM-dd"))
        self.refresh_day_tasks()
        self.refresh_timer_options()

    def add_one_time_task(self) -> None:
        dialog = TaskDialog("Add One-Time Task", self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._run_action(lambda: self.service.add_one_time_task(**{ "title": dialog.data()["title"] or "", "task_date": self.selected_date, "description": dialog.data()["description"] }), self.refresh_all)

    def add_routine_task(self) -> None:
        """Save one weekly routine whose selected weekdays recur indefinitely."""
        dialog = RoutineTaskDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.data()
            self._run_action(
                lambda: self.service.add_routine_task(
                    title=data["title"] or "",
                    description=data["description"],
                    repeat_type="custom_days",
                    days_of_week=data["days_of_week"],
                ),
                self.refresh_all,
            )

    def add_calendar_event(self) -> None:
        dialog = TaskDialog("Add Calendar Event", self, include_time=True)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.data()
            self._run_action(lambda: self.service.add_calendar_event(data["title"] or "", self.selected_date, data["description"], data["time"]), self.refresh_all)

    def add_matrix_task(self) -> None:
        dialog = MatrixTaskDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.data()
            self._run_action(lambda: self.service.add_matrix_task(data["title"] or "", data["description"], dialog.quadrant()), self.refresh_matrix)

    def start_timer(self) -> None:
        title = self.timer_title.currentText().strip()
        self._run_action(lambda: self.service.create_timer(title if title and title != "Custom timer" else "Timer", self.timer_minutes.value()), self.refresh_alarms)

    def check_due_alarms(self) -> None:
        for alarm in self.service.due_alarms():
            AlarmDialog(alarm["title"], self).exec()
            self.service.deactivate_alarm(alarm["id"])
        self.refresh_alarms()

    def delete_routine_task(self, task_id: int) -> None:
        if self._confirm("Archive routine task", "Archive this routine task? Its completion history is retained."):
            self.service.archive_routine_task(task_id)
            self.refresh_all()

    def delete_one_time_task(self, task_id: int) -> None:
        if self._confirm("Delete one-time task", "Delete this one-time task permanently?"):
            self.service.delete_one_time_task(task_id)
            self.refresh_all()

    def delete_calendar_event(self, event_id: int) -> None:
        if self._confirm("Delete calendar event", "Delete this calendar event permanently?"):
            self.service.delete_calendar_event(event_id)
            self.refresh_all()

    def delete_selected_matrix_task(self) -> None:
        task = self._selected_matrix_task()
        if task and self._confirm("Delete matrix task", "Delete this matrix task permanently?"):
            self.service.delete_matrix_task(task["id"])
            self.refresh_matrix()

    def assign_matrix_task(self) -> None:
        task = self._selected_matrix_task()
        if task is None:
            return
        dialog = AssignCalendarDialog(task["title"], self.selected_date, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.data()
            self._run_action(lambda: self.service.add_calendar_event(data["title"] or "", data["date"] or self.selected_date, data["description"] or task["description"], data["time"]), self.refresh_all)

    def delete_selected_alarm(self) -> None:
        item = self._selected_item(self.alarms, "Please select an alarm or timer first.")
        if item and self._confirm("Delete timer", "Delete this timer permanently?"):
            alarm_id = item.data(Qt.ItemDataRole.UserRole)
            if alarm_id is not None:
                self.service.delete_alarm(alarm_id)
                self.refresh_alarms()

    def _run_action(self, action, refresh) -> None:
        try:
            action()
        except ValueError as error:
            QMessageBox.warning(self, "Cannot save", str(error))
            return
        refresh()

    def _confirm(self, title: str, message: str) -> bool:
        return QMessageBox.question(self, title, message, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes

    def _selected_item(self, widget: QListWidget, message: str) -> QListWidgetItem | None:
        selected = widget.selectedItems()
        if selected:
            return selected[0]
        QMessageBox.information(self, "No task selected", message)
        return None

    def _selected_matrix_task(self) -> dict | None:
        """Return the source task attached to the selected read-only table row."""
        selected_rows = self.matrix.selectionModel().selectedRows()
        if selected_rows:
            task_item = self.matrix.item(selected_rows[0].row(), 2)
            task = task_item.data(Qt.ItemDataRole.UserRole) if task_item is not None else None
            if isinstance(task, dict):
                return task
        QMessageBox.information(self, "No task selected", "Please select a matrix task first.")
        return None

    @staticmethod
    def _clear_layout(layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
            elif item.layout() is not None:
                HabitTrackerView._clear_layout(item.layout())
