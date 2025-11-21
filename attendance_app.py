"""
출석 관리 시스템 - Python GUI 버전 (PyQt5)
exe 파일로 배포 가능한 데스크톱 애플리케이션
"""

import sys
import json
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QCalendarWidget, QComboBox, QGridLayout,
    QGroupBox, QDialog, QRadioButton, QButtonGroup, QMessageBox
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QFont, QColor, QPalette


# ============================================
# 출석 상태 정의
# ============================================
class AttendanceStatus:
    PRESENT = "출석"
    ABSENT = "결석"
    LATE = "지각"
    EARLY = "조퇴"
    OUTING = "외출"
    SICK = "병결"

    ALL = [PRESENT, ABSENT, LATE, EARLY, OUTING, SICK]

    COLORS = {
        PRESENT: "#10b981",
        ABSENT: "#ef4444",
        LATE: "#f97316",
        EARLY: "#eab308",
        OUTING: "#a78bfa",
        SICK: "#6b7280"
    }


# ============================================
# 출석률 계산 로직
# ============================================
class AttendanceCalculator:
    """출석률 계산을 담당하는 클래스"""

    @staticmethod
    def calculate(data, total_weekdays):
        """
        출석률 계산

        Args:
            data: {날짜_문자열: 상태} 딕셔너리
            total_weekdays: 총 평일 수

        Returns:
            {
                'rate': 출석률,
                'counts': 각 상태별 횟수,
                'final_absences': 최종 결석 수
            }
        """
        if total_weekdays == 0:
            return {'rate': 100.0, 'counts': {}, 'final_absences': 0}

        # 상태별 카운트
        counts = {status: 0 for status in AttendanceStatus.ALL}
        for status in data.values():
            if status in counts:
                counts[status] += 1

        # 직접 결석
        direct_absent = counts[AttendanceStatus.ABSENT]

        # 동일 사유 중복 (각각 2회 = 결석 1회)
        late_pairs = counts[AttendanceStatus.LATE] // 2
        early_pairs = counts[AttendanceStatus.EARLY] // 2
        outing_pairs = counts[AttendanceStatus.OUTING] // 2
        same_type_penalty = late_pairs + early_pairs + outing_pairs

        # 상이 사유 중복 (나머지 합 3회 = 결석 1회)
        late_rem = counts[AttendanceStatus.LATE] % 2
        early_rem = counts[AttendanceStatus.EARLY] % 2
        outing_rem = counts[AttendanceStatus.OUTING] % 2
        mixed_type_penalty = (late_rem + early_rem + outing_rem) // 3

        # 최종 결석 수
        final_absences = direct_absent + same_type_penalty + mixed_type_penalty

        # 출석률 계산 (병결은 출석으로 인정)
        rate = ((total_weekdays - final_absences) / total_weekdays) * 100
        rate = max(0, round(rate, 1))

        return {
            'rate': rate,
            'counts': counts,
            'final_absences': final_absences
        }

    @staticmethod
    def count_weekdays(start_date, end_date):
        """주어진 기간의 평일(월~금) 수 계산"""
        count = 0
        current = start_date
        while current <= end_date:
            # 0=월요일, 6=일요일
            if current.dayOfWeek() in [1, 2, 3, 4, 5]:  # 월~금
                count += 1
            current = current.addDays(1)
        return count


# ============================================
# 상태 선택 다이얼로그
# ============================================
class StatusDialog(QDialog):
    """출결 상태를 선택하는 다이얼로그"""

    def __init__(self, current_status, date_str, parent=None):
        super().__init__(parent)
        self.selected_status = current_status
        self.setWindowTitle("출결 상태 변경")
        self.setModal(True)
        self.init_ui(current_status, date_str)

    def init_ui(self, current_status, date_str):
        layout = QVBoxLayout()

        # 날짜 표시
        date_label = QLabel(f"📅 {date_str}")
        date_label.setFont(QFont("", 12, QFont.Bold))
        date_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(date_label)

        layout.addSpacing(10)

        # 라디오 버튼 그룹
        self.button_group = QButtonGroup()

        for i, status in enumerate(AttendanceStatus.ALL):
            radio = QRadioButton(status)
            radio.setFont(QFont("", 11))
            if status == current_status:
                radio.setChecked(True)

            # 색상 표시
            color = AttendanceStatus.COLORS[status]
            radio.setStyleSheet(f"""
                QRadioButton {{
                    padding: 8px;
                    margin: 2px;
                }}
                QRadioButton::indicator {{
                    width: 16px;
                    height: 16px;
                }}
                QRadioButton:checked {{
                    background-color: {color}22;
                    border-left: 3px solid {color};
                    border-radius: 4px;
                }}
            """)

            self.button_group.addButton(radio, i)
            radio.toggled.connect(lambda checked, s=status: self.on_status_changed(s, checked))
            layout.addWidget(radio)

        layout.addSpacing(10)

        # 확인 버튼
        ok_button = QPushButton("확인")
        ok_button.setFont(QFont("", 11))
        ok_button.clicked.connect(self.accept)
        ok_button.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: white;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)
        layout.addWidget(ok_button)

        self.setLayout(layout)

    def on_status_changed(self, status, checked):
        if checked:
            self.selected_status = status

    def get_status(self):
        return self.selected_status


# ============================================
# 메인 윈도우
# ============================================
class AttendanceMainWindow(QMainWindow):
    """출석 관리 시스템 메인 윈도우"""

    def __init__(self):
        super().__init__()

        # 데이터: {날짜_문자열: 상태}
        self.attendance_data = {}
        self.start_date = QDate.currentDate()
        self.end_date = self.start_date.addMonths(1)
        self.target_rate = 90

        self.init_ui()
        self.initialize_data()
        self.update_display()

    def init_ui(self):
        """UI 초기화"""
        self.setWindowTitle("출석 관리 시스템")
        self.setGeometry(100, 100, 1000, 700)

        # 메인 위젯
        main_widget = QWidget()
        self.setCentralWidget(main_widget)

        # 메인 레이아웃
        main_layout = QVBoxLayout()

        # === 헤더 ===
        header = self.create_header()
        main_layout.addWidget(header)

        # === 통계 카드 ===
        stats = self.create_stats_cards()
        main_layout.addWidget(stats)

        # === 캘린더 ===
        calendar = self.create_calendar()
        main_layout.addWidget(calendar)

        main_widget.setLayout(main_layout)

        # 스타일 적용
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f8fafc;
            }
            QGroupBox {
                background-color: white;
                border-radius: 10px;
                padding: 15px;
                margin: 5px;
                font-weight: bold;
            }
            QLabel {
                color: #1e293b;
            }
        """)

    def create_header(self):
        """헤더 생성"""
        group = QGroupBox("📊 출석 관리 대시보드")
        layout = QHBoxLayout()

        # 기간 표시
        self.period_label = QLabel()
        self.period_label.setFont(QFont("", 11))
        layout.addWidget(self.period_label)

        layout.addStretch()

        # 현재 출석률
        self.rate_label = QLabel("100.0%")
        self.rate_label.setFont(QFont("", 24, QFont.Bold))
        self.rate_label.setStyleSheet("color: #10b981;")
        layout.addWidget(self.rate_label)

        # 목표 출석률 선택
        layout.addWidget(QLabel("목표:"))
        self.target_combo = QComboBox()
        self.target_combo.addItems(["100%", "95%", "90%", "85%", "80%", "75%"])
        self.target_combo.setCurrentText("90%")
        self.target_combo.currentTextChanged.connect(self.on_target_changed)
        self.target_combo.setFont(QFont("", 11))
        layout.addWidget(self.target_combo)

        group.setLayout(layout)
        return group

    def create_stats_cards(self):
        """통계 카드 생성"""
        group = QGroupBox("📈 출결 현황")
        layout = QGridLayout()

        # 각 상태별 카드
        self.stat_labels = {}
        for i, status in enumerate(AttendanceStatus.ALL):
            card = QWidget()
            card_layout = QVBoxLayout()
            card_layout.setAlignment(Qt.AlignCenter)

            # 숫자
            count_label = QLabel("0")
            count_label.setFont(QFont("", 20, QFont.Bold))
            count_label.setStyleSheet(f"color: {AttendanceStatus.COLORS[status]};")
            count_label.setAlignment(Qt.AlignCenter)
            self.stat_labels[status] = count_label

            # 라벨
            name_label = QLabel(status)
            name_label.setFont(QFont("", 10))
            name_label.setAlignment(Qt.AlignCenter)

            card_layout.addWidget(count_label)
            card_layout.addWidget(name_label)
            card.setLayout(card_layout)

            # 배경색
            card.setStyleSheet(f"""
                background-color: {AttendanceStatus.COLORS[status]}15;
                border-radius: 8px;
                padding: 10px;
            """)

            layout.addWidget(card, 0, i)

        group.setLayout(layout)
        return group

    def create_calendar(self):
        """캘린더 생성"""
        group = QGroupBox("📅 출석 캘린더")
        layout = QVBoxLayout()

        # 캘린더 위젯
        self.calendar = QCalendarWidget()
        self.calendar.setFont(QFont("", 10))
        self.calendar.setGridVisible(True)
        self.calendar.clicked.connect(self.on_date_clicked)

        # 캘린더 스타일
        self.calendar.setStyleSheet("""
            QCalendarWidget QTableView {
                selection-background-color: #10b981;
            }
        """)

        layout.addWidget(self.calendar)

        # 설명
        info = QLabel("💡 평일 날짜를 클릭하여 출결 상태를 변경하세요")
        info.setFont(QFont("", 9))
        info.setStyleSheet("color: #64748b; padding: 5px;")
        layout.addWidget(info)

        group.setLayout(layout)
        return group

    def initialize_data(self):
        """데이터 초기화 (평일은 모두 출석으로)"""
        self.attendance_data.clear()
        current = self.start_date

        while current <= self.end_date:
            # 평일만 (월~금)
            if current.dayOfWeek() in [1, 2, 3, 4, 5]:
                date_str = current.toString("yyyy-MM-dd")
                self.attendance_data[date_str] = AttendanceStatus.PRESENT
            current = current.addDays(1)

    def on_date_clicked(self, qdate):
        """날짜 클릭 이벤트"""
        date_str = qdate.toString("yyyy-MM-dd")

        # 평일인지 확인
        if qdate.dayOfWeek() not in [1, 2, 3, 4, 5]:
            QMessageBox.information(self, "주말", "주말은 출결 처리를 할 수 없습니다.")
            return

        # 현재 상태
        current_status = self.attendance_data.get(date_str, AttendanceStatus.PRESENT)

        # 다이얼로그 표시
        dialog = StatusDialog(current_status, qdate.toString("yyyy년 M월 d일"), self)
        if dialog.exec_() == QDialog.Accepted:
            new_status = dialog.get_status()
            self.attendance_data[date_str] = new_status
            self.update_display()
            self.highlight_calendar_dates()

    def on_target_changed(self, text):
        """목표 출석률 변경"""
        self.target_rate = int(text.replace("%", ""))
        self.update_display()

    def update_display(self):
        """화면 업데이트"""
        # 기간 표시
        period_text = f"단위기간: {self.start_date.toString('yyyy-MM-dd')} ~ {self.end_date.toString('yyyy-MM-dd')}"
        self.period_label.setText(period_text)

        # 출석률 계산
        total_weekdays = AttendanceCalculator.count_weekdays(self.start_date, self.end_date)
        result = AttendanceCalculator.calculate(self.attendance_data, total_weekdays)

        # 출석률 표시
        rate = result['rate']
        self.rate_label.setText(f"{rate:.1f}%")

        # 색상 변경
        if rate >= 90:
            color = "#10b981"
        elif rate >= 80:
            color = "#f59e0b"
        else:
            color = "#ef4444"
        self.rate_label.setStyleSheet(f"color: {color};")

        # 통계 카드 업데이트
        counts = result['counts']
        for status, label in self.stat_labels.items():
            label.setText(str(counts.get(status, 0)))

        # 캘린더 하이라이트
        self.highlight_calendar_dates()

    def highlight_calendar_dates(self):
        """캘린더에 색상 표시"""
        # QCalendarWidget은 기본적으로 날짜별 색상을 직접 지정하기 어려움
        # 대신 텍스트 포맷을 사용
        for date_str, status in self.attendance_data.items():
            qdate = QDate.fromString(date_str, "yyyy-MM-dd")
            color = QColor(AttendanceStatus.COLORS[status])

            # 텍스트 포맷 설정
            text_format = self.calendar.dateTextFormat(qdate)
            text_format.setBackground(color)
            text_format.setForeground(QColor("white"))
            self.calendar.setDateTextFormat(qdate, text_format)


# ============================================
# 메인 실행
# ============================================
def main():
    app = QApplication(sys.argv)

    # 한글 폰트 설정
    app.setFont(QFont("맑은 고딕", 10))

    window = AttendanceMainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
